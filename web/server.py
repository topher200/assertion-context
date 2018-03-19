"""
    Run our web server.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import datetime
import logging
import os
import time
import urllib

import certifi
import flask
import redis
from flask_bootstrap import Bootstrap
from flask_env import MetaFlaskEnv
from flask_kvsession import KVSessionExtension
from elasticsearch import Elasticsearch
from simplekv.memory.redisstore import RedisStore
from simplekv.decorator import PrefixDecorator

from app import api_aservice
from app import es_util
from app import healthz
from app import jira_issue_aservice
from app import jira_issue_db
from app import logging_util
from app import realtime_updater
from app import tasks
from app import text_keys
from app import traceback_database


# create app
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
app = flask.Flask(__name__)

# get config from env vars
class EnvironmentVarConfig(metaclass=MetaFlaskEnv):
    ENV_LOAD_ALL = True # load all env variables

app.config.from_object(EnvironmentVarConfig)

# add bootstrap
Bootstrap(app)

# set up database
ES = Elasticsearch([app.config['ES_ADDRESS']], ca_certs=certifi.where())

# use redis for our session storage (ie: server side cookies)
REDIS = redis.StrictRedis(host=app.config['REDIS_ADDRESS'])
store = RedisStore(REDIS)
prefixed_store = PrefixDecorator('sessions_', store)
KVSessionExtension(prefixed_store, app)

# add route to /healthz healthchecks
healthz.add_healthcheck_endpoint(app, ES, REDIS)

# config
DEBUG_TIMING = True

logger = logging.getLogger()

FILTERS = ['All Tracebacks', 'Has Ticket', 'Has Open Ticket', 'No Ticket']


@app.route("/", methods=['GET'])
def index():
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

    return api_aservice.render_main_page(ES, days_ago_int, filter_text)


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

    logger.info("adding to s3 parse queue. bucket: '%s', key: '%s'", bucket, key)
    tasks.parse_log_file.delay(bucket, key)
    return 'job queued', 202


@app.route("/api/parse_s3_day", methods=['POST'])
def parse_s3_day():
    """
        POST request to parse the data from all Papertrail logs for one day

        Takes a JSON containing these fields:
        - date: day to parse. string, in YYYY-MM-DD form

        All fields are required.

        Returns a 400 error on bad input. Returns a 202 after we queue the jobs to be run
        asyncronously.
    """
    # parse our input
    json_request = flask.request.get_json()
    if json_request is None or not 'date' in json_request:
        return 'missing params', 400
    date_ = json_request['date']

    api_aservice.parse_s3_for_date(date_, app.config['S3_BUCKET'], app.config['S3_KEY_PREFIX'])
    return 'jobs queued', 202


@app.route("/api/parse_s3_date_range", methods=['POST'])
def parse_s3_date_range():
    """
        POST request to parse the data from all Papertrail logs for a date range

        Takes a JSON containing these fields:
        - start_date: starting day to parse. string, in YYYY-MM-DD form
        - end_date: starting day to parse. string, in YYYY-MM-DD form

        All fields are required.

        Returns a 400 error on bad input. Returns a 202 after we queue the jobs to be run
        asyncronously.
    """
    # parse our input
    json_request = flask.request.get_json()
    if (
            json_request is None
            or not 'start_date' in json_request
            or not 'end_date' in json_request
    ):
        return 'missing params', 400
    start_date_str = json_request['start_date']
    end_date_str   = json_request['end_date']

    # dates come in as a string - convert to datetime.date
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date   = datetime.datetime.strptime(end_date_str,   '%Y-%m-%d').date()
    except ValueError:
        return 'failed to parse date from params', 400

    # iterate through all dates between start_date and end_date
    date_ = start_date
    while date_ <= end_date:
        api_aservice.parse_s3_for_date(date_, app.config['S3_BUCKET'], app.config['S3_KEY_PREFIX'])
        date_ += datetime.timedelta(days=1)

    return 'jobs queued', 202


@app.route("/realtime_update", methods=['POST'])
def realtime_update():
    """
        POST request to parse data directly from Papertrail in real time.

        Takes a JSON containing these fields:
        - end_time: datetime to parse. string, in '%Y-%m-%d %H:%M:%S' form

        All fields are optional.

        Returns a 400 error on bad input. Returns a 202 after we queue the job to be run
        asyncronously.
    """
    # parse our input. it's optional!
    end_time = None
    json_request = flask.request.get_json()
    if json_request is not None and 'end_time' in json_request:
        end_time = json_request['end_time']

    realtime_updater.enqueue(end_time)
    return 'job queued', 202


@app.route("/hide_traceback", methods=['POST'])
def hide_traceback():
    json_request = flask.request.get_json()
    if json_request is None or 'traceback_text' not in json_request:
        logger.warning('invalid json detected: %s', json_request)
        return 'invalid json', 400
    traceback_text = json_request['traceback_text']
    our_set = flask.session.get(text_keys.HIDDEN_TRACEBACK)
    if our_set is None:
        our_set = set()
    # NOTE: changing the session implictly with session_object.add doesn't seem to work
    our_set.add(traceback_text)
    flask.session[text_keys.HIDDEN_TRACEBACK] = our_set
    return 'success'


@app.route("/restore_all", methods=['POST'])
def restore_all_tracebacks():
    flask.session[text_keys.HIDDEN_TRACEBACK] = None
    return 'success'


@app.route("/create_jira_ticket", methods=['POST'])
def create_jira_ticket():
    """
        Create a jira ticket with tracebacks that share the given traceback text

        Takes a json payload with these fields:
        - traceback_text: text of the traceback for which to create an issue

        The frontend is expecting this API to return a human readable string in the event of
        success (200 response code)
    """
    # get the traceback text
    json_request = flask.request.get_json()
    if json_request is None or 'traceback_text' not in json_request:
        logger.warning('invalid json detected: %s', json_request)
        return 'invalid json', 400
    traceback_text = json_request['traceback_text']

    # find a list of tracebacks that use that text
    similar_tracebacks = traceback_database.get_matching_tracebacks(
        ES, traceback_text, es_util.EXACT_MATCH, 50
    )

    # create a description using the list of tracebacks
    description = jira_issue_aservice.create_description(similar_tracebacks)

    # create a title using the traceback text
    title = jira_issue_aservice.create_title(traceback_text)

    # make API call to jira
    ticket = jira_issue_aservice.create_jira_issue(title, description)

    # send toast message to user with the JIRA url
    url = jira_issue_aservice.get_link_to_issue(ticket.key)
    return 'Created ticket <a href="%s" class="alert-link">%s</a>' % (url, ticket.key)


@app.route("/jira_comment", methods=['POST'])
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
        ES, traceback_text, es_util.EXACT_MATCH, 10000
    )

    # filter out any tracebacks that are after the latest one already on that ticket
    latest = jira_issue_aservice.find_latest_referenced_id(issue)
    if latest is not None:
        tracebacks_to_comment = [tb for tb in similar_tracebacks
                                 if int(tb.origin_papertrail_id) > latest][:50]
    else:
        # just take the them all
        tracebacks_to_comment = similar_tracebacks
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
    url = jira_issue_aservice.get_link_to_issue(issue_key)
    return 'Created a comment on <a href="%s" class="alert-link">%s</a>' % (url, issue_key)


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
        issue_key = json_request['issue_key']
        tasks.update_jira_issue.delay(issue_key, invalidate_cache=True)
        return 'job queued', 202
    else:
        if json_request['all'] != True:
            return 'invalid "all" json', 400
        # offload task onto our queue
        tasks.update_all_jira_issues.delay()
        return 'job queued', 202


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
    tasks.hydrate_cache.apply_async(tuple(), expires=60) # expire after a minute
    return 'success'


@app.route("/api/hydrate_cache", methods=['PUT'])
def hydrate_cache():
    """
        Invalidate all the dogpile function caches
    """
    _ = api_aservice.render_main_page(ES, days_ago=0, filter_text=FILTERS[0])
    return 'success'


@app.route("/api/purge_celery_queue", methods=['PUT'])
def purge_celery_queue():
    num_tasks = REDIS.llen('celery')
    REDIS.delete('celery')
    logger.info('purged %s tasks', num_tasks)
    return 'success'


@app.route("/admin", methods=['GET'])
def admin():
    error = False
    num_jira_issues = None
    try:
        num_jira_issues = jira_issue_db.get_num_jira_issues(ES)
    except Exception:
        logger.warning('unable to find number of jira issues', exc_info=True)
        error = True
    num_celery_tasks = None
    try:
        num_celery_tasks = REDIS.llen('celery')
    except Exception:
        logger.warning('unable to find number of celery tasks', exc_info=True)
        error = True
    return flask.render_template(
        'admin.html',
        num_jira_issues=num_jira_issues,
        num_celery_tasks=num_celery_tasks,
        error=error,
    )


@app.before_first_request
def setup_logging():
    logging_util.setup_logging()


@app.before_request
def before_request():
    # save the start_time and endpoint hit for logging purposes
    flask.g.start_time = time.time()
    flask.g.endpoint = flask.request.endpoint
    json_request = flask.request.get_json()
    json_str = '. json: %s' % str(json_request)[:100] if json_request is not None else ''
    logger.info(
        "handling %s '%s' request%s",
        flask.request.method, flask.request.full_path, json_str
    )

@app.after_request
def after_request(response):
    """ Logging after every request. """
    # This avoids the duplication of registry in the log,
    # since that 500 is already logged via @app.errorhandler.
    if response.status_code != 500:
        ts = time.strftime('[%Y-%b-%d %H:%M]')
        logger.error(
            '%s %s %s %s %s %s',
            ts,
            flask.request.remote_addr,
            flask.request.method,
            flask.request.scheme,
            flask.request.full_path,
            response.status
        )
    return response


@app.errorhandler(Exception)
def exceptions(e):
    """ Logging after every Exception. """
    ts = time.strftime('[%Y-%b-%d %H:%M]')
    tb = traceback.format_exc()
    logger.error(
        '%s %s %s %s %s 5xx INTERNAL SERVER ERROR\n%s',
        ts,
        flask.request.remote_addr,
        flask.request.method,
        flask.request.scheme,
        flask.request.full_path,
        tb
    )
    return "Internal Server Error", 500

@app.teardown_request
def profile_request(_):
    time_diff = time.time() - flask.g.start_time
    logger.info('/%s request took %.2fs', flask.g.endpoint, time_diff)
    timings = []
    for t in (
            'time_tracebacks',
            'time_hidden_tracebacks',
            'jira_issues_time',
            'similar_tracebacks_time',
            'render_time'
    ):
        try:
            timings.append('%s: %.2fs' % (t, flask.g.get(t)))
        except TypeError:
            pass  # info not present on this one
    if timings:
        logger.info(', '.join(timings))


if __name__ == "__main__":
    app.config['LOGGER_HANDLER_POLICY'] = 'never'
    app.run(debug=True, host='0.0.0.0', port=8000)
