"""
    Run our web server.

    Provides endpoints for saving data to DB and for analyzing the data that's been saved.
"""
import datetime
import logging
import json
import os
import time
import traceback
import urllib

import certifi
import flask
import opentracing
import redis
from flask_bootstrap import Bootstrap
from flask_env import MetaFlaskEnv
from flask_kvsession import KVSessionExtension
from elasticsearch import Elasticsearch
from simplekv.memory.redisstore import RedisStore
from simplekv.decorator import PrefixDecorator

from opentracing_instrumentation.request_context import span_in_context

from app import (
    api_aservice,
    es_util,
    healthz,
    jira_issue_aservice,
    jira_issue_db,
    logging_util,
    realtime_updater,
    tasks,
    text_keys,
    traceback_database,
    traceback_formatter,
    tracing,
)
from app.services import (
    slack_poster,
)


# create app
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
app = flask.Flask(__name__)

# get config from env vars
class EnvironmentVarConfig(metaclass=MetaFlaskEnv):
    ENV_LOAD_ALL = True # load all env variables

app.config.from_object(EnvironmentVarConfig)

logging_util.setup_logging()
logger = logging.getLogger()

# add bootstrap
Bootstrap(app)

# set up database
ES = Elasticsearch([app.config['ES_ADDRESS']], ca_certs=certifi.where())

# use redis for our session storage (ie: server side cookies)
REDIS = redis.StrictRedis(host=app.config['REDIS_ADDRESS'])
store = RedisStore(REDIS)
prefixed_store = PrefixDecorator('sessions_', store)
KVSessionExtension(prefixed_store, app)

# config
DEBUG_TIMING = True

# add tracing
tracing.initialize_tracer()

# add route to /healthz healthchecks
healthz.add_healthcheck_endpoint(app, ES, REDIS)

FILTERS = ['All Tracebacks', 'Has Ticket', 'Has Open Ticket', 'No Ticket', 'No Recent Ticket']


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

    # create a set of traceback ids that match all the traceback texts the user has hidden
    span = flask.g.tracer_root_span
    tracer = opentracing.tracer
    with span_in_context(span):
        # TODO: do we need to set something to declare what this span block is doing?
        hidden_traceback_ids = set()
        if flask.session.get(text_keys.HIDDEN_TRACEBACK) is not None:
            for traceback_text in flask.session.get(text_keys.HIDDEN_TRACEBACK):
                for tb in traceback_database.get_matching_tracebacks(
                        ES, tracer, traceback_text, es_util.EXACT_MATCH, 10000
                ):
                    hidden_traceback_ids.add(tb.origin_papertrail_id)
            logger.info('found %s traceback ids we need to hide', len(hidden_traceback_ids))

    with span_in_context(span):
        span.set_tag('filter', filter_text)
        return api_aservice.render_main_page(ES, tracer, days_ago_int, filter_text, set())


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

    # this isn't exactly the best time to post to slack (since it won't include anything from this
    # realtime_update call), but it's as good a time as any
    tasks.post_unticketed_tracebacks_to_slack.delay()
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
        - origin_papertrail_id: id of the traceback for which to create an issue

        The frontend is expecting this API to return a human readable string in the event of
        success (200 response code)
    """
    # get traceback id
    json_request = flask.request.get_json()
    if json_request is None or 'origin_papertrail_id' not in json_request:
        logger.warning('invalid json detected: %s', json_request)
        return 'invalid json', 400
    origin_papertrail_id = json_request['origin_papertrail_id']

    ticket_key = api_aservice.create_ticket(
        ES, origin_papertrail_id, None, reject_if_ticket_exists=False
    )

    # send toast message to user with the JIRA url
    url = jira_issue_aservice.get_link_to_issue(ticket_key)
    return 'Created ticket <a href="%s" class="alert-link">%s</a>' % (url, ticket_key)


@app.route("/jira_comment", methods=['POST'])
def jira_comment():
    """
        Save a comment in jira with the latest hits on this traceback

        Takes a json payload with these fields:
        - origin_papertrail_id: the id of the traceback to find papertrail matches for
        - issue_key: the jira issue key on which to leave the comment

        The frontend is expecting this API to return a human readable string in the event of
        success (200 response code)
    """
    # get the payload
    json_request = flask.request.get_json()
    if json_request is None:
        logger.warning('no json detected: %s', json_request)
        return 'missing json', 400
    if 'origin_papertrail_id' not in json_request:
        logger.warning('missing json field detected: %s', json_request)
        return 'missing origin_papertrail_id', 400
    if 'issue_key' not in json_request:
        logger.warning('missing json field detected: %s', json_request)
        return 'missing issue_key', 400
    origin_papertrail_id = json_request['origin_papertrail_id']
    issue_key = json_request['issue_key']

    api_aservice.create_comment_on_existing_ticket(ES, issue_key, origin_papertrail_id)
    url = jira_issue_aservice.get_link_to_issue(issue_key)
    return 'Created a comment on <a href="%s" class="alert-link">%s</a>' % (url, issue_key)


@app.route("/jira_formatted_list/<traceback_origin_id>", methods=['GET'])
def jira_formatted_list(traceback_origin_id):
    """
        Retrieves a formatted list fit for jira, with the latest hits on this traceback

        Takes a query param with these fields:
        - traceback_origin_id: the traceback to find papertrail matches for

        The frontend is expecting this API to return a human readable string in the event of
        success (200 response code)
    """
    try:
        traceback_id = int(traceback_origin_id)
    except ValueError:
        return 'bad traceback id', 400
    if not traceback_id:
        return 'missing traceback id', 400

    # get the referenced traceback
    tb = traceback_database.get_traceback(ES, traceback_id)

    # find a list of tracebacks that use the given traceback text
    tracebacks = traceback_database.get_matching_tracebacks(
        ES, opentracing.tracer, tb.traceback_text, es_util.EXACT_MATCH, 10000
    )
    tracebacks.sort(key=lambda tb: int(tb.origin_papertrail_id), reverse=True)

    return (
        traceback_formatter.create_hits_list(tracebacks, traceback_formatter.jira_formatted_string),
        200,
        {'Content-Type': 'text/plain'}
    )


@app.route("/slack-callback", methods=['POST'])
def slack_callback():
    data = flask.request.get_data()
    if data is None:
        return 'empty data', 400

    parsed_data = urllib.parse.parse_qs(data)
    payload = json.loads(parsed_data[b'payload'][0])
    if 'actions' in payload:
        # it's a request to do an action
        action = payload['actions'][0]['name']
        if action == 'create_ticket':
            origin_papertrail_id = payload['callback_id']
            assign_to = payload['actions'][0]['selected_options'][0]['value']
            try:
                new_ticket_id = api_aservice.create_ticket(
                    ES, origin_papertrail_id, assign_to, reject_if_ticket_exists=True
                )

                # replace the slack message's CTA with a "done!" message
                original_message = payload['original_message']
                original_message['attachments'].pop() # destructive!
                original_message['attachments'].append(
                    {
                        "text": "%s created!" % new_ticket_id
                    }
                )
                return flask.jsonify(original_message)
            except api_aservice.IssueAlreadyExistsError as e:
                # we must post the message as a real user so Jirabot picks it up
                slack_poster.post_message_to_slack_as_real_user(str(e))
        elif action == 'add_to_existing_ticket':
            selected_ticket_key = payload['actions'][0]['selected_options'][0]['value']
            origin_papertrail_id = payload['callback_id']
            selected_ticket_key = payload['actions'][0]['selected_options'][0]['value']
            api_aservice.create_comment_on_existing_ticket(
                ES, selected_ticket_key, origin_papertrail_id
            )

            # replace the slack message's CTA with a "done!" message
            original_message = payload['original_message']
            original_message['attachments'].pop() # destructive!
            original_message['attachments'].append(
                {
                    "text": "%s updated!" % selected_ticket_key
                }
            )
            return flask.jsonify(original_message)
        else:
            logger.error('unexpected slack callback action: %s', action)
            logger.warning('slack payload: %s', payload)
    elif 'name' in payload:
        # it's a request to get more info for a dropdown menu
        action = payload['name']
        if action == 'add_to_existing_ticket':
            search_phrase = payload['value']
            options = {
                "options": list(jira_issue_aservice.search_matching_jira_tickets(ES, search_phrase))
            }
            return flask.Response(json.dumps(options), mimetype='application/json')
        else:
            logger.error('unexpected slack callback action: %s', action)
            logger.warning('slack payload: %s', payload)
    else:
        logger.error('unexpected slack callback json: %s', payload)
    return 'ok'


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


@app.before_request
def start_request():
    # log the request
    json_request = flask.request.get_json()
    json_str = '. json: %s' % str(json_request)[:100] if json_request is not None else ''
    logger.info(
        "received %s '%s' request from %s%s",
        flask.request.method,
        flask.request.full_path,
        flask.request.remote_addr,
        json_str,
    )

    # start an opentracing span
    headers = {}
    for k, v in flask.request.headers:
        headers[k.lower()] = v
    try:
        tracer = opentracing.tracer
        span_ctx = tracer.extract(opentracing.Format.HTTP_HEADERS, headers)
        span = tracer.start_span(operation_name='server', child_of=span_ctx)
    except (opentracing.InvalidCarrierException, opentracing.SpanContextCorruptedException) as e:
        span = tracer.start_span(operation_name='server', tags={"Extract failed": str(e)})
    span.set_tag('path', flask.request.full_path)
    span.set_tag('method', flask.request.method)
    flask.g.tracer_root_span = span

    # record the start time so we can calculate timing info after the request is done
    flask.g.start_time = time.time()


@app.after_request
def after_request(response):
    """ End tracing and record a log after every request. """
    flask.g.tracer_root_span.finish()

    # figure out how long the request took
    try:
        time_diff = time.time() - flask.g.start_time
        time_diff_str = '%.2fs' % time_diff
    except AttributeError:
        logger.warning('unable to log request timing')
        time_diff_str = 'UNKNOWN'

    # This 'if' avoids the duplication of registry in the log, since that 500 is already logged via
    # @app.errorhandler.
    if response.status_code != 500:
        logger.info(
            "finished %s '%s' request from %s in %s. %s",
            flask.request.method,
            flask.request.full_path,
            flask.request.remote_addr,
            time_diff_str,
            response.status,
        )
    return response


@app.errorhandler(Exception)
def exceptions(_):
    """ Logging after every Exception. """
    tb = traceback.format_exc()
    logger.error(
        "error %s '%s' request from %s. 5xx internal server error\n%s",
        flask.request.method,
        flask.request.full_path,
        flask.request.remote_addr,
        tb,
    )

    return "Internal Server Error", 500


if __name__ == "__main__":
    app.config['LOGGER_HANDLER_POLICY'] = 'never'
    app.run(debug=True, host='0.0.0.0', port=8000)
