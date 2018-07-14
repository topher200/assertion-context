import logging
import json

import requests


from .. import config_util
from ..traceback import Traceback

WEBHOOK_URL = config_util.get('SLACK_WEBHOOK')

logger = logging.getLogger()


def post_traceback(traceback:Traceback):
    slack_data = {'text': traceback.traceback_plus_context_text}

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
