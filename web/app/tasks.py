import logging

from celery import Celery
from elasticsearch import Elasticsearch

from web.app import (
    jira_issue_db,
    jira_util,
)
from web.instance import config

app = Celery('tasks', broker='redis://redis')  # redis is a hostname that Docker populates

# set up database
ES = Elasticsearch([config.ES_ADDRESS])

logger = logging.getLogger()


@app.task
def update_jira_issue_db():
    """
        iterate through all JIRA issues and save them to the database
    """
    logger.info("updating jira issue db")
    count = 0
    for issue in jira_util.get_all_issues():
        count += 1
        jira_issue_db.save_jira_issue(ES, jira_util.get_issue(issue))
    logger.info("saved %s issues", count)
