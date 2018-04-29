from .traceback import Traceback

from . import (
    config_util,
)


PRODUCT_URL=config_util.get('PRODUCT_URL')

TIMESTAMP_TEMPLATE = '%b %d %Y %H:%M:%S'
"""
    A template for human-readable timestamps. Timezone info is ignored.

    To be used by datetime a datetime object like this: `dt.strftime(TIMESTAMP_TEMPLATE)`
"""

def human_readable_string(traceback: Traceback) -> str:
    """ Given a traceback, returns a well formatted string for presentation """
    pass


def jira_formatted_string(t: Traceback) -> str:
    """
        Given a traceback, returns a wall formatting string in Jira's bad formatting

        We have four parts to our formatted string:
        - a timestamp, with a link to papertrail
        - a profile name, with a link to the product's profile. may not exist
        - a user name, with a link to the product's user. may not exist
        - a link to the kibana archive of the traceback
    """
    timestamp_str = (
        "[{timestamp}|"
        "https://papertrailapp.com/systems/{instance_id}/events?focus={papertrail_id}]"
    ).format(
        timestamp=t.origin_timestamp.strftime(TIMESTAMP_TEMPLATE),
        instance_id=t.instance_id,
        papertrail_id=t.origin_papertrail_id,
    )
    return ' - %s' % timestamp_str
