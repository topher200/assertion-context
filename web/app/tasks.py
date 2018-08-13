import datetime
import logging

import pytz
import redis

from elasticsearch import Elasticsearch
import celery
import certifi

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
from app.ddl import api_call_db
from .services import (
    slack_poster,
)

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
    _ = api_aservice.render_main_page(ES, None, days_ago=0, filter_text='Has Ticket')


@app.task
def post_unticketed_tracebacks_to_slack():
    """
        Post any unticketed tracebacks to slack.

        Only posts if we've never posted about that specific Traceback before.
    """
    # our papertrail logs are saved in Eastern Time
    today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()

    # get today's tracebacks
    tracebacks_with_metadata = api_aservice.get_tracebacks_for_day(
        ES, None, today, 'No Recent Ticket', set()
    )
    tracebacks_with_metadata.reverse() # post in order by time, with latest coming last

    # for each traceback, post it if we haven't seen it already today
    for tb_meta in (
            tb_meta for tb_meta in tracebacks_with_metadata
            if not REDIS.get(
                    __SEEN_TRACEBACKS_KEY.format(
                        traceback_id=tb_meta.traceback.origin_papertrail_id
                    )
            )
    ):
        REDIS.setex(
            __SEEN_TRACEBACKS_KEY.format(traceback_id=tb_meta.traceback.origin_papertrail_id),
            __TWO_DAYS_IN_SECONDS,
            "true"
        )
        slack_poster.post_traceback(
            tb_meta.traceback, tb_meta.similar_tracebacks, tb_meta.jira_issues
        )


@app.task
def tell_slack_about_new_jira_ticket(ticket_id:str):
    # we must post this message as a real user so that Jirabot picks up on it
    slack_poster.post_message_to_slack_as_real_user('Created %s' % ticket_id)


@app.task
def tell_slack_about_updated_jira_ticket(ticket_id:str):
    # we must post this message as a real user so that Jirabot picks up on it
    slack_poster.post_message_to_slack_as_real_user('Updated %s' % ticket_id)


@celery.signals.setup_logging.connect
def setup_logging(*_, **__):
    logging_util.setup_logging()


__SEEN_TRACEBACKS_KEY = 'seen_tracebacks:{traceback_id}'
"""
    redis key to store our set of tracebacks we've seen

    requires the "date" of the traceback so that we can set a ttl on the set (and ensure that it gets
    garbage collected).
"""


__TWO_DAYS_IN_SECONDS = 60 * 60 * 24 * 2
"""
    Two days, in seconds
"""
