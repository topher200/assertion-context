from common_util import (
    elasticsearch_config,
)
from lib.jira import (
    jira_issue_db,
)

ES = elasticsearch_config.get_db()


def test_refresh():
    jira_issue_db.refresh(ES)
