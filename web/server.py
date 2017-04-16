"""
    Run our API.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import collections
import datetime
import json
import logging
import os
import time

import flask
import pytz
import redis
from flask_bootstrap import Bootstrap
from flask_kvsession import KVSessionExtension
from flask_login import current_user, login_required
from elasticsearch import Elasticsearch
from simplekv.memory.redisstore import RedisStore
from simplekv.decorator import PrefixDecorator

from app import authentication
from app import database
from app import jira_util
from app import s3
from app import traceback


# to work around https://github.com/pallets/flask/issues/1907
class AutoReloadingFlask(flask.Flask):
    def create_jinja_environment(self):
        self.config['TEMPLATES_AUTO_RELOAD'] = True
        return flask.Flask.create_jinja_environment(self)

# create app
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
app = AutoReloadingFlask(__name__, instance_path=os.path.join(ROOT_DIR, 'instance'))
app.config.from_pyfile('instance/config.py')
app.secret_key = app.config['OAUTH_CLIENT_SECRET']

# set up database
ES = Elasticsearch([app.config['ES_ADDRESS']])

# add bootstrap
Bootstrap(app)

# use redis for our session storage (ie: server side cookies)
store = RedisStore(redis.StrictRedis(host='redis'))
prefixed_store = PrefixDecorator('sessions_', store)
KVSessionExtension(prefixed_store, app)
TRACEBACK_TEXT_KV_PREFIX = 'hide_traceback:'

# config
DEBUG_TIMING = True

# add a login handler
authentication.add_login_handling(app)

logger = logging.getLogger()


@app.route("/", methods=['GET'])
@login_required
def index():
    # use the query params to determine the date_to_analyze
    days_ago_raw = flask.request.args.get('days_ago')
    if days_ago_raw is not None:
        try:
            days_ago_int = int(days_ago_raw)
        except ValueError:
            return 'bad params', 400
    else:
        days_ago_int = 0
    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    date_to_analyze = today - datetime.timedelta(days=days_ago_int)

    if DEBUG_TIMING:
        db_start_time = time.time()
    tracebacks = database.get_tracebacks(ES, date_to_analyze, date_to_analyze)
    if DEBUG_TIMING:
        flask.g.time_tracebacks = time.time() - db_start_time
    # get all tracebacks that the user hasn't hidden
    tracebacks = (
        t for t in tracebacks
        if not flask.session.get(TRACEBACK_TEXT_KV_PREFIX + t.traceback_text, False)
    )
    TracebackMetadata = collections.namedtuple(
        'TracebackMetadata', 'traceback, similar_tracebacks'
    )

    if DEBUG_TIMING:
        meta_start_time = time.time()
    tb_meta = [
        TracebackMetadata(t, database.get_similar_tracebacks(ES, t.traceback_text))
        for t in tracebacks
    ]
    if DEBUG_TIMING:
        flask.g.time_meta = time.time() - meta_start_time
    return flask.render_template(
        'index.html',
        tb_meta=tb_meta,
        show_restore_button=__user_has_hidden_tracebacks(),
        date_to_analyze=date_to_analyze,
        days_ago=days_ago_int
    )


def __user_has_hidden_tracebacks():
    """
        Returns True if the user has hidden any tracebacks using /hide_traceback this session
    """
    for key in flask.session:
        if key.startswith(TRACEBACK_TEXT_KV_PREFIX) and flask.session[key]:
            return True
    return False


@app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    """
        POST request to parse the data from a Papertrail log hosted on s3.

        Takes a JSON containing these fields:
        - bucket: the name of the s3 bucket containing the file. string
        - key: the filename of the file we should parse. must be in `bucket`. string

        All fields are required.

        Returns a 400 error on bad input. Returns a 502 if we get an error accessing s3. Returns a
        200 on success.
    """
    # parse our input
    json_request = flask.request.get_json()
    if json_request is None or not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400
    logger.debug("parsing s3 file. bucket: '%s', key: '%s'",
                     json_request['bucket'], json_request['key'])

    # use our powerful parser to run checks on the requested file
    traceback_generator = s3.parse_s3_file(json_request['bucket'], json_request['key'])
    if traceback_generator is None:
        return 'error accessing s3', 502

    # save the parser output to the database
    for traceback in traceback_generator:
        database.save_traceback(ES, traceback)

    return 'success'


@app.route("/hide_traceback", methods=['POST'])
@login_required
def hide_traceback():
    json_request = flask.request.get_json()
    if json_request is None or 'traceback_text' not in json_request:
        logger.warning('invalid json detected: %s', json_request)
        return 'invalid json', 400
    traceback_text = json_request['traceback_text']
    flask.session[TRACEBACK_TEXT_KV_PREFIX + traceback_text] = True
    return 'success'


@app.route("/restore_all", methods=['POST'])
@login_required
def restore_all_tracebacks():
    for key in flask.session:
        if key.startswith(TRACEBACK_TEXT_KV_PREFIX):
            flask.session[key] = False
    return 'success'


@app.route("/create_jira_ticket", methods=['POST'])
@login_required
def create_jira_ticket():
    # get the traceback text
    json_request = flask.request.get_json()
    if json_request is None or 'traceback_text' not in json_request:
        logger.warning('invalid json detected: %s', json_request)
        return 'invalid json', 400
    traceback_text = json_request['traceback_text']

    # find a list of tracebacks that use that text
    similar_tracebacks = database.get_similar_tracebacks(ES, traceback_text)

    # create a description using the list of tracebacks
    description = jira_util.create_description(similar_tracebacks)

    # create a title using the traceback text
    title = jira_util.create_title(traceback_text)

    # make API call to jira
    ticket = jira_util.create_jira_issue(title, description)

    # send flash message to user with the JIRA url
    url = jira_util.get_link_to_issue(ticket)
    flask.flash(flask.Markup(
        'Created ticket <a href="%s" class="alert-link">%s</a>' % (url, ticket.key)
    ))
    return 'success'


@app.route("/api/tracebacks", methods=['GET'])
@login_required
def get_tracebacks():
    data = [tb.document() for tb in database.get_tracebacks(ES)]
    return flask.jsonify({'tracebacks': data})


@app.before_first_request
def setup_logging():
    # add log handler to sys.stderr.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] | %(levelname)s | %(pathname)s.%(funcName)s:%(lineno)d | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


@app.before_request
def before_request():
    # save the start_time and endpoint hit for logging purposes
    flask.g.start_time = time.time()
    flask.g.endpoint = flask.request.endpoint
    user = current_user.email if not current_user.is_anonymous else 'anonymous user'
    json_request = flask.request.get_json()
    json_str = '. json: %s' % str(json_request)[:100] if json_request is not None else ''
    logger.debug(
        "handling '%s' request from '%s'%s", flask.request.full_path, user, json_str
    )


@app.teardown_request
def profile_request(_):
    time_diff = time.time() - flask.g.start_time
    logger.debug('/%s request took %.2fs', flask.g.endpoint, time_diff)
    try:
        logger.debug(
            'get tracebacks: %.2fs, get similar_tracebacks: %.2fs',
            flask.g.time_tracebacks, flask.g.time_meta
        )
    except AttributeError:
        pass  # info not present on this one


if __name__ == "__main__":
    app.config['LOGGER_HANDLER_POLICY'] = 'never'
    app.run(debug=True, host='0.0.0.0', port=8000)
