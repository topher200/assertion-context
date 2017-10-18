import logging

from elasticsearch import Elasticsearch
import celery

from app import (
    jira_issue_db,
    jira_issue_aservice,
    traceback_database,
    logging_util,
    tasks_util,
    s3,
)
from app.ddl import api_call_db
from instance import config

app = celery.Celery('tasks', broker='redis://redis')  # redis is a hostname that Docker populates

# set up database
ES = Elasticsearch([config.ES_ADDRESS])

logger = logging.getLogger()


@app.task
def update_jira_issue(issue_key):
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
        update_jira_issue.delay(issue.key)
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
    count = 0
    for call in api_calls:
        count += 1
        api_call_db.save(ES, call)
    logger.info("saved %s api_calls. bucket: %s, key: %s", count, bucket, key)


@celery.signals.setup_logging.connect
def setup_logging(*_, **__):
    logging_util.setup_logging()
