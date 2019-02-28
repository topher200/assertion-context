from ..traceback import Traceback
from .. import (
    config_util,
)

TRACEBACKS_CHANNEL_NAME = 'tracebacks'
TRACEBACKS_CHANNEL_NAME_ADWORDS = 'tracebacks-adwords'
TRACEBACKS_CHANNEL_NAME_SOCIAL = 'tracebacks-social'
SLACK_WEBHOOK_TRACEBACKS = config_util.get('SLACK_WEBHOOK_TRACEBACKS')
SLACK_WEBHOOK_TRACEBACKS_ADWORDS = config_util.get('SLACK_WEBHOOK_TRACEBACKS_ADWORDS')
SLACK_WEBHOOK_TRACEBACKS_SOCIAL = config_util.get('SLACK_WEBHOOK_TRACEBACKS_SOCIAL')


def get_webhook_url(traceback:Traceback):
    """
        Given a traceback, returns the Slack App webhook to post to the appropriate slack channel.
    """
    channel_name = get_channel_name(traceback)
    if channel_name == TRACEBACKS_CHANNEL_NAME:
        return SLACK_WEBHOOK_TRACEBACKS
    elif channel_name == TRACEBACKS_CHANNEL_NAME_ADWORDS:
        return SLACK_WEBHOOK_TRACEBACKS_ADWORDS
    elif channel_name == TRACEBACKS_CHANNEL_NAME_SOCIAL:
        return SLACK_WEBHOOK_TRACEBACKS_SOCIAL
    else:
        assert False, 'unknown channel %s' % channel_name
        return None


def get_channel_name(traceback:Traceback):
    """
        Given a traceback, returns the name of the slack channel it belongs in.

        We look in the traceback's text for certain trigger words.
    """
    # TEMP: send everything to my channel, to not spam other users
    return TRACEBACKS_CHANNEL_NAME

    if 'facebook' in traceback.traceback_text.lower():
        return TRACEBACKS_CHANNEL_NAME_SOCIAL
    elif 'adwords' in traceback.traceback_text.lower():
        return TRACEBACKS_CHANNEL_NAME_ADWORDS
    else:
        return TRACEBACKS_CHANNEL_NAME
