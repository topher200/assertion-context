import datetime
import logging

import pytz
import redis

from elasticsearch import Elasticsearch
import celery
import certifi

from common_util import (
    config_util,
    logging_util,
)
from lib.api_call import api_call_db
from lib.common import (
    cache_util,
)
from lib.jira import (
    jira_issue_aservice,
    jira_issue_db,
)
from lib.papertrail import (
    realtime_updater,
)
from lib.parser import (
    s3,
)
from lib.slack import (
    slack_poster,
)
from lib.traceback import (
    traceback_db,
)
from webapp import (
    api_aservice,
)

REDIS_ADDRESS = config_util.get('REDIS_ADDRESS')
ES_ADDRESS = config_util.get('ES_ADDRESS')

app = celery.Celery('tasks', broker='redis://'+REDIS_ADDRESS)

# set up database
ES = Elasticsearch([ES_ADDRESS], ca_certs=certifi.where())
REDIS = redis.StrictRedis(host=REDIS_ADDRESS)

logger = logging.getLogger()


@app.task
def update_jira_issue(issue_key, do_invalidate_cache):
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

    if do_invalidate_cache:
        cache_util.invalidate_cache('jira')


@app.task
def update_all_jira_issues():
    """
        iterate through all JIRA issues and save them to the database
    """
    logger.info("updating all jira issues")
    count = 0
    for issue in jira_issue_aservice.get_all_issues():
        count += 1
        update_jira_issue.delay(issue.key, do_invalidate_cache=False)
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
        traceback_db.save_traceback(ES, tb)
    logger.info("saved %s tracebacks. bucket: %s, key: %s", count, bucket, key)
    cache_util.invalidate_cache('traceback')

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
    _ = api_aservice.get_tracebacks_for_day(ES, None, datetime.date.today(), 'Has Ticket', set())


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
def create_jira_ticket(origin_papertrail_id:int, assign_to:str):
    """
        Given a traceback id and a Jira user, create a new Jira ticket and assign it to that user.
    """
    api_aservice.create_ticket(
        ES, origin_papertrail_id, assign_to, reject_if_ticket_exists=True
    )


@app.task
def create_comment_on_existing_ticket(selected_ticket_key:str, origin_papertrail_id:int):
    """
        Given a Jira ticket key and a traceback id, update the ticket with that traceback.
    """
    api_aservice.create_comment_on_existing_ticket(ES, selected_ticket_key, origin_papertrail_id)


@app.task
def tell_slack_about_new_jira_ticket(channel:str, ticket_id:str):
    # we must post this message as a real user so that Jirabot picks up on it
    slack_poster.post_message_to_slack_as_real_user(channel, 'Created %s' % ticket_id)


@app.task
def tell_slack_about_updated_jira_ticket(channel:str, ticket_id:str):
    # we must post this message as a real user so that Jirabot picks up on it
    slack_poster.post_message_to_slack_as_real_user(channel, 'Updated %s' % ticket_id)


@app.task
def tell_slack_about_error(channel:str, error):
    # we must post this message as a real user so that Jirabot picks up on it
    slack_poster.post_message_to_slack_as_real_user(channel, error)


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
