import datetime
import logging

import pytz
import redis

from elasticsearch import Elasticsearch
import celery
import certifi
import requests

from app import (
    api_aservice,
    config_util,
    jira_issue_aservice,
    jira_issue_db,
    logging_util,
    realtime_updater,
    s3,
    tasks_util,
    traceback_database,
    tracing,
)
from .services import (
    slack_poster,
)
from app.ddl import api_call_db

REDIS_ADDRESS = config_util.get('REDIS_ADDRESS')
ES_ADDRESS = config_util.get('ES_ADDRESS')

app = celery.Celery('tasks', broker='redis://'+REDIS_ADDRESS)

# set up database
ES = Elasticsearch([ES_ADDRESS], ca_certs=certifi.where())
REDIS = redis.StrictRedis(host=REDIS_ADDRESS)

# add tracing
tracer = tracing.initialize_tracer()

logger = logging.getLogger()


@app.task
def update_jira_issue(issue_key, invalidate_cache):
    """
        update a jira issue in our database, given its key

        we do this out of band since the jira API can sometimes take a few tries
    """
    issue = None
    num_tries = 0
    while issue is None and num_tries < 5:
        num_tries += 1
        issue = jira_issue_aservice.get_issue(issue_key)
    if issue is None:
        # the issue must be deleted
        logger.info('removing %s - issue not found', issue_key)
        jira_issue_db.remove_jira_issue(ES, issue_key)
    else:
        jira_issue_db.save_jira_issue(ES, issue)
        logger.info("updated jira issue %s", issue_key)

    if invalidate_cache:
        tasks_util.invalidate_cache('jira')


@app.task
def update_all_jira_issues():
    """
        iterate through all JIRA issues and save them to the database
    """
    logger.info("updating all jira issues")
    count = 0
    for issue in jira_issue_aservice.get_all_issues():
        count += 1
        update_jira_issue.delay(issue.key, invalidate_cache=False)
    logger.info("queued %s jira issues", count)


@app.task
def parse_log_file(bucket, key):
    """
        takes a bucket and key refering to a logfile on s3 and parses that file
    """
    logger.info("parsing log file. bucket: %s, key: %s", bucket, key)

    # use our powerful parser to run checks on the requested file
    tracebacks, api_calls = s3.parse_s3_file(bucket, key)
    if tracebacks is None:
        logger.error("unable to download log file from s3. bucket: %s, key: %s", bucket, key)
        return

    # save the tracebacks to the database
    count = 0
    for tb in tracebacks:
        count += 1
        traceback_database.save_traceback(ES, tb)
    logger.info("saved %s tracebacks. bucket: %s, key: %s", count, bucket, key)
    tasks_util.invalidate_cache('traceback')

    # save the api calls to the database
    logger.info("found %s api_calls. bucket: %s, key: %s", len(api_calls), bucket, key)
    if api_call_db.save(ES, api_calls):
        logger.info("saved %s api_calls. bucket: %s, key: %s", len(api_calls), bucket, key)
    else:
        logger.error('failed to save api_calls. %s, key: %s', bucket, key)


@app.task
def realtime_update(start_time, end_time):
    logger.info("running realtime updater. %s to %s", start_time, end_time)
    realtime_updater.run(ES, start_time, end_time)


@app.task
def hydrate_cache():
    """
        Calls the server's hydrate API.

        This will speed up subsequent requests from real humans. No data is sent back.
    """
    requests.put('http://nginx/api/hydrate_cache')


@app.task
def post_unticketed_tracebacks_to_slack():
    """
        Post any unticketed tracebacks to slack.

        Only posts if we've never posted about that specific Traceback before.
    """
    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()

    # get today's tracebacks
    tracebacks = api_aservice.get_tracebacks_for_day(ES, None, today, 'No Ticket')

    for tb_to_post in (
            tb for tb in tracebacks
            if tb.origin_papertrail_id
            not in REDIS.sismember(__SEEN_TRACEBACKS_KEY, tb.origin_papertrail_id)
    ):
        slack_poster.post_traceback(tb_to_post)
        # TODO: this set will grow to infinity
        REDIS.sadd(__SEEN_TRACEBACKS_KEY, tb_to_post.origin_papertrail_id)
        break


@celery.signals.setup_logging.connect
def setup_logging(*_, **__):
    logging_util.setup_logging()


__SEEN_TRACEBACKS_KEY = 'seen_tracebacks'
"""
    redis key to store our set of tracebacks we've seen
"""
