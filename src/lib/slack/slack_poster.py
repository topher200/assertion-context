from typing import List
import logging
import json

import requests

from common_util import (
    config_util,
)
from lib.jira import (
    jira_issue_aservice,
)
from lib.jira.jira_issue import JiraIssue
from lib.slack import slack_channel
from lib.traceback import (
    traceback_formatter,
)
from lib.traceback.traceback import Traceback


SLACK_REAL_USER_TOKEN = config_util.get('SLACK_REAL_USER_TOKEN')

logger = logging.getLogger()

MESSAGE_TEMPLATE = """
```
{traceback_text}```"""

JIRA_ISSUE_TEMPLATE = """
- <{issue_link}|{issue_key}>, {issue_status}, {issue_assignee}: {issue_summary}
"""
"""
    a template for rendering a single jira issue in slack

    requires:
    - issue_link: a url link to this issue
    - issue_key: the key for this issue
    - issue_status: the current status for this issue
    - issue_assignee: name of who the issue is currently assigned to
    - issue_summary: the summary for this issue
"""

NUM_LINES_TO_POST = 5
"""
    How many lines of the traceback to post. Do too many and slack splits up the message.
"""

MAX_CHARS_PER_LINE = 200
"""
    How many chars of each traceback line to post. Do too many and slack splits up the message.
"""


def post_traceback(traceback, similar_tracebacks:List[Traceback], jira_issues:List[JiraIssue]):
    last_N_lines = "\n".join(
        text[:MAX_CHARS_PER_LINE] for text in
        traceback.traceback_plus_context_text.splitlines()[-NUM_LINES_TO_POST:]
    )
    traceback_text = MESSAGE_TEMPLATE.format(traceback_text=last_N_lines)
    hits = traceback_formatter.create_hits_list(
        similar_tracebacks,
        traceback_formatter.slack_formatted_string,
        max_number_hits=40
    )
    jira_issue_text = '\n'.join(
        JIRA_ISSUE_TEMPLATE.format(
            issue_link=jira_issue_aservice.get_link_to_issue(issue.key),
            issue_key=issue.key,
            issue_status=issue.status.upper(),
            issue_assignee=issue.assignee if issue.assignee else 'Unassigned',
            issue_summary=issue.summary,
        ) for issue in jira_issues
    )

    slack_data = {
        "text": traceback_text,
        "attachments": [
            {
                "text": MESSAGE_TEMPLATE.format(
                    traceback_text=traceback.traceback_plus_context_text
                ),
            },
            {
                "text": hits,
                "short": True,
            },
            {
                "text": jira_issue_text,
                "short": True,
            },
            {
                "callback_id": "%s" % traceback.origin_papertrail_id,
                "color": "#007ABD",
                "attachment_type": "default",
                "fallback": "Create Jira Ticket",
                "actions": [
                    {
                        "name": "create_ticket",
                        "text": "Create a Jira ticket...",
                        "type": "select",
                        "options": [
                            {
                                "text": "Unassigned",
                                "value": "UNASSIGNED"
                            },
                            {
                                "text": "Adwords (assign to Joe)",
                                "value": "ADWORDS"
                            },
                            {
                                "text": "Bing (assign to Peter)",
                                "value": "BING"
                            },
                            {
                                "text": "Social (assign to Sam G.)",
                                "value": "SOCIAL"
                            },
                            {
                                "text": "Grader (assign to Gary)",
                                "value": "GRADER"
                            },
                        ]
                    },
                    {
                        "name": "add_to_existing_ticket",
                        "text": "Add to existing ticket",
                        "type": "select",
                        "data_source": "external",
                        "options": [
                            {
                                "text": "PPC-12345", # dummy option to start
                                "value": "PPC-12345"
                            }
                        ]
                    },
                ],
                "short": True,
            }
        ]
    }

    webhook_url = slack_channel.get_webhook_url(traceback)
    return __send_message_to_slack(slack_data, webhook_url)


def __send_message_to_slack(slack_data:dict, webhook_url:str):
    logger.debug('sending message to slack: %s', json.dumps(slack_data))

    response = requests.post(
        webhook_url,
        data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code != 200:
        logger.error(
            'Request to slack returned an error %s, the response is:\n%s',
            response.status_code, response.text
        )

    return response


def post_message_to_slack_as_real_user(channel:str, message:str):
    """
        Normal messages are posted as a bot user.

        To interact with other bots, it's sometimes helpful to post as a true user. This method
        does so.
    """
    assert SLACK_REAL_USER_TOKEN

    url = 'https://slack.com/api/chat.postMessage'
    params = {
        'token': SLACK_REAL_USER_TOKEN,
        'channel': channel,
        'as_user': True,
        'text': message,
    }
    response = requests.post(
        url,
        params=params,
    )
    if response.status_code == 200:
        logger.info('posted to slack channel %s', channel)
    else:
        logger.error(
            'Request to slack returned an error %s, the response is:\n%s',
            response.status_code, response.text
        )
