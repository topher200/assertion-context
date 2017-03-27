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
from flask_cors import CORS
from flask_kvsession import KVSessionExtension
from flask_oauthlib.client import OAuth
from elasticsearch import Elasticsearch
from simplekv.memory.redisstore import RedisStore

from app import database
from app import s3


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT_DIR, '.es_credentials')) as f:
    ES_ADDRESS = str.strip(f.readline())
OAUTH_CLIENT_ID = 'XXX'
OAUTH_CLIENT_SECRET = 'XXX'

# to work around https://github.com/pallets/flask/issues/1907
class AutoReloadingFlask(flask.Flask):
    def create_jinja_environment(self):
        self.config['TEMPLATES_AUTO_RELOAD'] = True
        return flask.Flask.create_jinja_environment(self)

# create app
app = AutoReloadingFlask(__name__)
app.secret_key = ES_ADDRESS
CORS(app)

# set up database
ES = Elasticsearch([ES_ADDRESS])

# add bootstrap
Bootstrap(app)

# use redis for our session storage (ie: server side cookies)
store = RedisStore(redis.StrictRedis(host='redis'))
KVSessionExtension(store, app)

TRACEBACK_TEXT_KV_PREFIX = 'hide-'

# config
DEBUG_TIMING = True

# oauth setup
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
oauth = OAuth()
google = oauth.remote_app(
    'google',
    request_token_params={
        'scope': 'email',
        'state': 'skdfjsdkjfsdkfsdjkf'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    consumer_key=OAUTH_CLIENT_ID,
    consumer_secret=OAUTH_CLIENT_SECRET,
)


@app.route("/hide_traceback", methods=['POST'])
def hide_traceback():

    # make sure we're logged in
    if get_google_oauth_token() is None:
        return flask.redirect(flask.url_for('login'))

    # get user
    user = google.get('userinfo')
    app.logger.error('oauth: %s' % flask.jsonify({"data": user.data}))

    json_request = flask.request.get_json()
    app.logger.info('hide_traceback POST: %s', json_request)
    if json_request is None or 'traceback_text' not in json_request:
        return 'invalid json', 400
    traceback_text = json_request['traceback_text']
    flask.session[TRACEBACK_TEXT_KV_PREFIX + traceback_text] = True
    return 'success'


@app.route("/restore_all", methods=['POST'])
def restore_all_tracebacks():
    for key in flask.session:
        if key.startswith(TRACEBACK_TEXT_KV_PREFIX):
            flask.session[key] = False
    return 'success'


@app.route("/", methods=['GET'])
def index():
    app.logger.debug('handling index request')
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


@app.before_first_request
def setup_logging():
    # add log handler to sys.stderr.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] | %(levelname)s | %(pathname)s:%(lineno)d | %(funcName)s | %(message)s"
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)


@app.before_request
def before_request():
    # save the start_time and endpoint hit for logging purposes
    flask.g.start_time = time.time()
    flask.g.endpoint = flask.request.endpoint


@app.route('/login')
def login():
    response = google.authorize(callback=flask.url_for('authorized', _external=True))
    response.headers['Access-Control-Allow-Origin'] = "localhost"
    return response


@app.route('/logout')
def logout():
    flask.session.pop('google_token', None)
    return flask.redirect(flask.url_for('login'))


@app.route('/login/authorized')
def authorized():
    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            flask.request.args['error_reason'],
            flask.request.args['error_description']
        )
    flask.session['google_token'] = (resp['access_token'], '')
    me = google.get('userinfo')
    return flask.jsonify({"data": me.data})


@google.tokengetter
def get_google_oauth_token():
    return flask.session.get('google_token')


@app.teardown_request
def profile_request(_):
    try:
        time_diff = time.time() - flask.g.start_time
        app.logger.debug('"%s" request took %.2fs', flask.g.endpoint, time_diff)
        if DEBUG_TIMING:
            app.logger.debug(
                'get tracebacks: %.2fs, get similar_tracebacks: %.2fs',
                flask.g.time_tracebacks, flask.g.time_meta
            )
    except AttributeError:
        app.logger.warn('expected profiling data missing. flask.g keys: "%s"',
                        ', '.join(key for key in flask.g))


if __name__ == "__main__":
    app.config['LOGGER_HANDLER_POLICY'] = 'never'
    app.run(debug=True, host='0.0.0.0', port=8000)
