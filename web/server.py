"""
    Run our API.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import collections
import logging
import os
import time

import flask
import redis
from flask_bootstrap import Bootstrap
from flask_kvsession import KVSessionExtension
from flask_login import login_required
from elasticsearch import Elasticsearch
from simplekv.memory.redisstore import RedisStore
from simplekv.decorator import PrefixDecorator


class UsernameLogFilter(logging.Filter):
    def filter(self, record):
        record.username = flask_login.current_user
        return True


import app.log
from app import authentication
from app import database
from app import s3


# to work around https://github.com/pallets/flask/issues/1907
class AutoReloadingFlask(flask.Flask):
    def create_jinja_environment(self):
        self.config['TEMPLATES_AUTO_RELOAD'] = True
        return flask.Flask.create_jinja_environment(self)

# create app
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)
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


@app.route("/hide_traceback", methods=['POST'])
@login_required
def hide_traceback():
    json_request = flask.request.get_json()
    app.logger.info('hide_traceback POST: %s', json_request)
    if json_request is None or 'traceback_text' not in json_request:
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


@app.route("/", methods=['GET'])
@login_required
def index():
    logger.error('handling index request')
    if DEBUG_TIMING:
        db_start_time = time.time()
    tracebacks = database.get_tracebacks(ES)
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
    return flask.render_template('index.html',
                                 tb_meta=tb_meta,
                                 show_restore_button=__user_has_hidden_tracebacks()
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
    app.logger.info('parse s3 request: %s', json_request)
    if json_request is None or not all(k in json_request for k in ('bucket', 'key')):
        return 'missing params', 400

    # use our powerful parser to run checks on the requested file
    traceback_generator = s3.parse_s3_file(json_request['bucket'], json_request['key'])
    if traceback_generator is None:
        return 'error accessing s3', 502

    # save the parser output to the database
    for traceback in traceback_generator:
        app.logger.debug('saving traceback: %s', traceback)
        database.save_traceback(ES, traceback)

    return 'success'


@app.route("/api/tracebacks", methods=['GET'])
def get_tracebacks():
    data = [tb.document() for tb in database.get_tracebacks(ES)]
    return flask.jsonify({'tracebacks': data})


# @app.before_first_request
# def setup_logging():
#     # add log handler to sys.stderr.
#     handler = logging.StreamHandler()
#     formatter = logging.Formatter(
#         "[%(asctime)s] | %(levelname)s | %(pathname)s:%(lineno)d | %(funcName)s | %(message)s"
#     )
#     handler.setFormatter(formatter)
#     app.logger.addHandler(handler)
#     app.logger.setLevel(logging.DEBUG)


@app.before_request
def before_request():
    # save the start_time and endpoint hit for logging purposes
    flask.g.start_time = time.time()
    flask.g.endpoint = flask.request.endpoint


@app.teardown_request
def profile_request(_):
    time_diff = time.time() - flask.g.start_time
    app.logger.debug('"%s" request took %.2fs', flask.g.endpoint, time_diff)
    try:
        app.logger.debug(
            'get tracebacks: %.2fs, get similar_tracebacks: %.2fs',
            flask.g.time_tracebacks, flask.g.time_meta
        )
    except AttributeError:
        pass  # info not present on this one


if __name__ == "__main__":
    app.config['LOGGER_HANDLER_POLICY'] = 'never'
    app.run(debug=True, host='0.0.0.0', port=8000)
