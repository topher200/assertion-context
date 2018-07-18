from typing import List
import logging
import json

import requests


from .. import (
    config_util,
    traceback_formatter,
)
from ..traceback import Traceback

WEBHOOK_URL = config_util.get('SLACK_WEBHOOK')
SLACK_REAL_USER_TOKEN = config_util.get('SLACK_REAL_USER_TOKEN')

logger = logging.getLogger()

MESSAGE_TEMPLATE = """
```
{traceback_text}```"""

NUM_LINES_TO_POST = 5
"""
    How many lines of the traceback to post. Do too many and slack splits up the message.
"""


def post_traceback(traceback, similar_tracebacks:List[Traceback]):
    last_N_lines = "\n".join(
        traceback.traceback_plus_context_text.splitlines()[-NUM_LINES_TO_POST:]
    )
    traceback_text = MESSAGE_TEMPLATE.format(traceback_text=last_N_lines)
    hits = traceback_formatter.create_hits_list(
        similar_tracebacks,
        traceback_formatter.slack_formatted_string,
        max_number_hits=50
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
                                "text": "Adwords (assign to Al)",
                                "value": "ADWORDS"
                            },
                            {
                                "text": "Bing (assign to Peter)",
                                "value": "BING"
                            },
                            {
                                "text": "Social (assign to Jay)",
                                "value": "SOCIAL"
                            },
                        ]
                    }
                ],
                "short": True,
            }
        ]
    }

    return __send_message_to_slack(slack_data)


def post_message_to_slack(message:str):
    slack_data = {
        'text': message,
    }
    __send_message_to_slack(slack_data)


def __send_message_to_slack(slack_data:dict):
    logger.debug('sending message to slack: %s', json.dumps(slack_data))

    response = requests.post(
        WEBHOOK_URL,
        data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code != 200:
        logger.error(
            'Request to slack returned an error %s, the response is:\n%s',
            response.status_code, response.text
        )

    return response


def post_message_to_slack_as_real_user(message:str):
    """
        Normal messages are posted as a bot user.

        To interact with other bots, it's sometimes helpful to post as a true user. This method
        does so.
    """
    assert SLACK_REAL_USER_TOKEN

    url = 'https://slack.com/api/chat.postMessage'
    params = {
        'token': SLACK_REAL_USER_TOKEN,
        'channel': 'tracebacks',
        'as_user': True,
        'text': message,
    }
    response = requests.post(
        url,
        params=params,
    )
    if response.status_code != 200:
        logger.error(
            'Request to slack returned an error %s, the response is:\n%s',
            response.status_code, response.text
        )