"""
    Run our API.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import datetime
import logging
import os
import time
import types
import urllib

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
from app import es_util
from app import jira_issue_aservice
from app import jira_issue_db
from app import s3
from app import tasks
from app import traceback
from app import traceback_database


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
HIDDEN_TRACEBACK_TEXT_KEY = 'hide_tracebacks'

# config
DEBUG_TIMING = True

# add a login handler
authentication.add_login_handling(app)

logger = logging.getLogger()


@app.route("/", methods=['GET'])
@login_required
def index():
    FILTERS = ['Has Ticket', 'Has Open Ticket', 'No Ticket', 'All Tracebacks']

    # parse the query params
    days_ago_raw = flask.request.args.get('days_ago')
    if days_ago_raw is not None:
        try:
            days_ago_int = int(days_ago_raw)
        except ValueError:
            return 'bad params', 400
    else:
        days_ago_int = 0
    filter_text = flask.request.args.get('filter')
    if filter_text is not None:
        filter_text = urllib.parse.unquote_plus(filter_text)
        if filter_text not in FILTERS:
            return 'bad filter: %s' % filter_text, 400
    if filter_text is None:
        filter_text = 'All Tracebacks'

    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
    date_to_analyze = today - datetime.timedelta(days=days_ago_int)

    # get all tracebacks
    if DEBUG_TIMING:
        db_start_time = time.time()
    tracebacks = traceback_database.get_tracebacks(ES, date_to_analyze, date_to_analyze)
    if DEBUG_TIMING:
        flask.g.time_tracebacks = time.time() - db_start_time

    # create a set of tracebacks that match all the traceback texts the user has hidden
    hidden_tracebacks = set()
    if flask.session.get(HIDDEN_TRACEBACK_TEXT_KEY) is not None:
        for traceback_text in flask.session.get(HIDDEN_TRACEBACK_TEXT_KEY):
            for tb in traceback_database.get_matching_tracebacks(
                ES, traceback_text, es_util.EXACT_MATCH
            ):
                hidden_tracebacks.add(tb.origin_papertrail_id)
        logger.info('found %s traceback ids we need to hide', len(hidden_tracebacks))

    # filter out tracebacks the user has hidden. we use a SimpleNamespace to store each traceback +
    # some metadata we'll use when rendering the html page
    tb_meta = [
        types.SimpleNamespace(traceback=t) for t in tracebacks
        if t.origin_papertrail_id not in hidden_tracebacks
    ]
    if len(tracebacks) - len(tb_meta) > 0:
        logger.info('hid %s tracebacks', len(tracebacks) - len(tb_meta))

    # get a list of matching jira issues
    if DEBUG_TIMING:
        jira_issues_start_time = time.time()
    for tb in tb_meta:
        tb.jira_issues = jira_issue_db.get_matching_jira_issues(
            ES, tb.traceback.traceback_text, es_util.EXACT_MATCH
        )
        matching_jira_keys = set(jira_issue.key for jira_issue in tb.jira_issues)
        similar_jira_issues = jira_issue_db.get_matching_jira_issues(
            ES, tb.traceback.traceback_text, es_util.SIMILAR_MATCH
        )
        tb.similar_jira_issues = [similar_jira_issue for similar_jira_issue in similar_jira_issues
                                  if similar_jira_issue.key not in matching_jira_keys]
    if DEBUG_TIMING:
        flask.g.jira_issues_time = time.time() - jira_issues_start_time

    # apply user's filters
    if filter_text == 'Has Ticket':
        tb_meta = [tb for tb in tb_meta if len(tb.jira_issues) > 0]
    elif filter_text == 'No Ticket':
        tb_meta = [tb for tb in tb_meta if len(tb.jira_issues) == 0]
    elif filter_text == 'Has Open Ticket':
        tb_meta = [
            tb for tb in tb_meta if len(
                [issue for issue in tb.jira_issues if issue.status != 'Closed']
            ) > 0
        ]

    # for each traceback, get all similar tracebacks
    if DEBUG_TIMING:
        similar_tracebacks_start_time = time.time()
    for tb in tb_meta:
        tb.similar_tracebacks = traceback_database.get_matching_tracebacks(
            ES, tb.traceback.traceback_text, es_util.EXACT_MATCH
        )[:100]
    if DEBUG_TIMING:
        flask.g.similar_tracebacks_time = time.time() - similar_tracebacks_start_time

    if DEBUG_TIMING:
        render_start_time = time.time()
    render = flask.render_template(
        'index.html',
        tb_meta=tb_meta,
        show_restore_button=__user_has_hidden_tracebacks(),
        date_to_analyze=date_to_analyze,
        days_ago=days_ago_int,
        filter_text=filter_text
    )
    if DEBUG_TIMING:
        flask.g.render_time = time.time() - render_start_time

    return render


def __user_has_hidden_tracebacks():
    """
        Returns True if the user has hidden any tracebacks using /hide_traceback this session
    """
    return flask.session.get(HIDDEN_TRACEBACK_TEXT_KEY) is not None


@app.route("/api/parse_s3", methods=['POST'])
def parse_s3():
    """
        POST request to parse the data from a Papertrail log hosted on s3.

        Takes a JSON containing these fields:
        - bucket: the name of the s3 bucket containing the file. string
        - key: the filename of the file we should parse. must be in `bucket`. string

        All fields are required.

        Returns a 400 error on bad input. Returns a 202 after we queue the job to be run
        asyncronously.
    """
    # parse our input
    json_request = flask.request.get_json()
    if json_request is None or not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400
    bucket = json_request['bucket']
    key = json_request['key']

    logger.info("parsing s3 file. bucket: '%s', key: '%s'", bucket, key)
    tasks.parse_log_file.delay(bucket, key)
    return 'job queued', 202


@app.route("/hide_traceback", methods=['POST'])
@login_required
def hide_traceback():
    json_request = flask.request.get_json()
    if json_request is None or 'traceback_text' not in json_request:
        logger.warning('invalid json detected: %s', json_request)
        return 'invalid json', 400
    traceback_text = json_request['traceback_text']
    our_set = flask.session.get(HIDDEN_TRACEBACK_TEXT_KEY)
    if our_set is None:
        our_set = set()
    # NOTE: changing the session implictly with session_object.add doesn't seem to work
    our_set.add(traceback_text)
    flask.session[HIDDEN_TRACEBACK_TEXT_KEY] = our_set
    return 'success'


@app.route("/restore_all", methods=['POST'])
@login_required
def restore_all_tracebacks():
    flask.session[HIDDEN_TRACEBACK_TEXT_KEY] = None
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
    similar_tracebacks = traceback_database.get_matching_tracebacks(
        ES, traceback_text, es_util.EXACT_MATCH
    )

    # create a description using the list of tracebacks
    description = jira_issue_aservice.create_description(similar_tracebacks)

    # create a title using the traceback text
    title = jira_issue_aservice.create_title(traceback_text)

    # make API call to jira
    ticket = jira_issue_aservice.create_jira_issue(title, description)

    # send flash message to user with the JIRA url
    url = jira_issue_aservice.get_link_to_issue(ticket)
    flask.flash(flask.Markup(
        'Created ticket <a href="%s" class="alert-link">%s</a>' % (url, ticket.key)
    ))
    return 'success'


@app.route("/jira_comment", methods=['POST'])
@login_required
def jira_comment():
    """
        Save a comment in jira with the latest hits on this traceback

        Takes a json payload with these fields:
        - traceback_text: the text to find papertrail matches for
        - issue_key: the jira issue key on which to leave the comment

        The frontend is expecting this API to return a human readable string in the event of
        success (200 response code)
    """
    # get the payload
    json_request = flask.request.get_json()
    if json_request is None:
        logger.warning('no json detected: %s', json_request)
        return 'missing json', 400
    if 'traceback_text' not in json_request:
        logger.warning('missing json field detected: %s', json_request)
        return 'missing traceback_text', 400
    if 'issue_key' not in json_request:
        logger.warning('missing json field detected: %s', json_request)
        return 'missing issue_key', 400
    traceback_text = json_request['traceback_text']
    issue_key = json_request['issue_key']
    issue = jira_issue_aservice.get_issue(issue_key)

    # find a list of tracebacks that use the given traceback text
    similar_tracebacks = traceback_database.get_matching_tracebacks(
        ES, traceback_text, es_util.EXACT_MATCH
    )

    # filter out any tracebacks that are after the latest one already on that ticket
    latest = jira_issue_aservice.find_latest_referenced_id(issue)
    tracebacks_to_comment = [tb for tb in similar_tracebacks
                             if int(tb.origin_papertrail_id) > latest]
    if len(tracebacks_to_comment) <= 0:
        logger.info('not saving comment - found %s hits but none were newer than %s',
                    len(similar_tracebacks),
                    latest)
        return 'No comment created on %s. That ticket is already up to date' % issue_key
    else:
        logger.info('commenting with %s/%s hits',
                    len(tracebacks_to_comment),
                    len(similar_tracebacks))

    # create a comment using the list of tracebacks
    comment = jira_issue_aservice.create_comment_with_hits_list(tracebacks_to_comment)
    jira_issue_aservice.create_comment(issue, comment)
    return 'Created a comment on %s' % issue_key


@app.route("/api/tracebacks", methods=['GET'])
@login_required
def get_tracebacks():
    data = [tb.document() for tb in traceback_database.get_tracebacks(ES)]
    return flask.jsonify({'tracebacks': data})


@app.route("/api/update_jira_db", methods=['PUT'])
def update_jira_db():
    """
        Update our database of jira issues.

        Takes a JSON payload with the following fields:
        - issue_key: if included, must be the key of the issue to update. if we see this key we
          only update the specified issue. example: SAN-1234
        - all: if included, must be the boolean value of True. if we see this key (and not
          issue_key) we update all jira issues.

        The JSON payload must have at least one field.
    """
    # parse our input
    json_request = flask.request.get_json()
    if json_request is None or not any(k in json_request for k in ('issue_key', 'all')):
        return 'invalid json', 400

    if 'issue_key' in json_request:
        # save the given issue to ES
        issue = json_request['issue_key']
        jira_issue_db.save_jira_issue(ES, jira_issue_aservice.get_issue(issue))
    else:
        if json_request['all'] != True:
            return 'invalid "all" json', 400
        # offload task onto our queue
        tasks.update_jira_issue_db.delay()
        return 'job queued', 202

    return 'success'


@app.route("/api/invalidate_cache", methods=['PUT'])
@app.route("/api/invalidate_cache/<cache>", methods=['PUT'])
def invalidate_cache(cache=None):
    """
        Invalidate all the dogpile function caches
    """
    if cache is None or cache == 'traceback':
        logger.info('invalidating traceback cache')
        traceback_database.invalidate_cache()
    if cache is None or cache == 'jira':
        logger.info('invalidating jira cache')
        jira_issue_db.invalidate_cache()
    return 'success'



@app.before_first_request
def setup_logging():
    # add log handler to sys.stderr.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        (
            "[%(asctime)s] | %(levelname)s | %(process)d | "
            "%(pathname)s.%(funcName)s:%(lineno)d | %(message)s"
        )
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@app.before_request
def before_request():
    # save the start_time and endpoint hit for logging purposes
    flask.g.start_time = time.time()
    flask.g.endpoint = flask.request.endpoint
    user = current_user.email if not current_user.is_anonymous else 'anonymous user'
    json_request = flask.request.get_json()
    json_str = '. json: %s' % str(json_request)[:100] if json_request is not None else ''
    logger.info(
        "handling %s '%s' request from '%s'%s",
        flask.request.method, flask.request.full_path, user, json_str
    )


@app.teardown_request
def profile_request(_):
    time_diff = time.time() - flask.g.start_time
    logger.info('/%s request took %.2fs', flask.g.endpoint, time_diff)
    timings = []
    for t in ('time_tracebacks', 'similar_tracebacks_time', 'jira_issues_time', 'render_time'):
        try:
            timings.append('%s: %.2fs' % (t, flask.g.get(t)))
        except TypeError:
            pass  # info not present on this one
    if len(timings) > 0:
        logger.info(', '.join(timings))


if __name__ == "__main__":
    app.config['LOGGER_HANDLER_POLICY'] = 'never'
    app.run(debug=True, host='0.0.0.0', port=8000)
