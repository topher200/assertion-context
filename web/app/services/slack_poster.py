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

logger = logging.getLogger()

MESSAGE_TEMPLATE = """
```
{traceback_text}```
{hits}
"""


def post_traceback(traceback, similar_tracebacks:List[Traceback]):
    message = MESSAGE_TEMPLATE.format(
        traceback_text=traceback.traceback_plus_context_text,
        hits=traceback_formatter.create_hits_list(
            similar_tracebacks,
            traceback_formatter.slack_formatted_string,
            max_number_hits=10
        ),
    )
    slack_data = {
        'text': message,
        'attachments': [
            {
                'callback_id': traceback.origin_papertrail_id,
                'actions': [
                    {
                        'name': 'create_ticket',
                        'text': 'Create Ticket',
                        'type': 'button',
                        'value': 'default',
                    },
                ]
            },
        ]
    }

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
