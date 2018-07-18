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


def __generate_slack_data_to_post_traceback(
        traceback:Traceback, similar_tracebacks:List[Traceback]
) -> dict:
    """
        Generates the JSON package to post to slack to create a "Tracebacks" slack message.

        Includes...
        - the last few lines of the Traceback text
        - the entire traceback text, behind a 'read more' link
        - a list of hits
    """

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
        ]
    }

    return slack_data


def post_traceback(traceback, similar_tracebacks:List[Traceback]):
    """
        Posts a traceback to slack.

        Includes...
        - everything from L{__generate_slack_data_to_post_traceback}
        - PLUS a button to create a ticket for the traceback
    """
    slack_data = __generate_slack_data_to_post_traceback(traceback, similar_tracebacks)
    slack_data['attachments'].append(
        {
            "callback_id": "%s" % traceback.origin_papertrail_id,
            "color": "#007ABD",
            "attachment_type": "default",
            "fallback": "Create Jira Ticket",
            "actions": [
                {
                    "name": "create_ticket",
                    "text": "Create Jira Ticket",
                    "type": "button",
                    "value": "default"
                }
            ],
            "short": True,
        }
    )

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
