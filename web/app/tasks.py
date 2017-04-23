import logging

from elasticsearch import Elasticsearch
import celery

from app import (
    jira_issue_db,
    jira_util,
)
from instance import config

app = celery.Celery('tasks', broker='redis://redis')  # redis is a hostname that Docker populates

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


@celery.signals.setup_logging.connect
def setup_logging(*_, **__):
    # add log handler to sys.stderr.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] | %(levelname)s | %(pathname)s.%(funcName)s:%(lineno)d | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
