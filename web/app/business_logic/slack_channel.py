from ..traceback import Traceback
from .. import (
    config_util,
)

SLACK_WEBHOOK_TRACEBACKS = config_util.get('SLACK_WEBHOOK_TRACEBACKS')
SLACK_WEBHOOK_TRACEBACKS_ADWORDS = config_util.get('SLACK_WEBHOOK_TRACEBACKS_ADWORDS')
SLACK_WEBHOOK_TRACEBACKS_SOCIAL = config_util.get('SLACK_WEBHOOK_TRACEBACKS_SOCIAL')


def get(traceback:Traceback):
    """
        Given a traceback, returns the name of the slack channel it belongs in.

        We look in the traceback's text for certain trigger words.
    """
    if 'facebook' in traceback.traceback_text.lower():
        return SLACK_WEBHOOK_TRACEBACKS_SOCIAL
    elif 'adwords' in traceback.traceback_text.lower():
        return SLACK_WEBHOOK_TRACEBACKS_ADWORDS
    else:
        return SLACK_WEBHOOK_TRACEBACKS
