from .traceback import Traceback

from . import (
    config_util,
)


KIBANA_ADDRESS=config_util.get('KIBANA_ADDRESS')
PRODUCT_URL=config_util.get('PRODUCT_URL')

TIMESTAMP_TEMPLATE = '%b %d %Y %H:%M:%S'
"""
    A template for human-readable timestamps. Timezone info is ignored.

    To be used by datetime a datetime object like this: `dt.strftime(TIMESTAMP_TEMPLATE)`
"""

PAPERTRAIL_LINK_TEMPLATE = "[{timestamp}|https://papertrailapp.com/systems/{instance_id}/events?focus={papertrail_id}]"
"""
    A template for a link to papertrail, with the timestamp as the human-readable string.

    Requires these strings:
    - timestamp, from TIMESTAMP_TEMPLATE
    - papertrail instance id. example: i-029b0000000000000
    - papertrail log line id. example: 926921020000000000
"""

KIBANA_TEMPLATE = "{kibana_address}/_plugin/kibana/app/kibana#/discover?_g=(time:(from:now-50y))&_a=(query:(language:lucene,query:'{papertrail_id}'))"
"""
    A template for linking to a papertrail object in kibana.

    Caller must provide:
    - a link to the kibana domain, no trailing slash. example: 'https://kibana.company.com'
    - the papertrail id to highlight on. example: '926890000000000000'
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
    # timestamp and link to papertrail
    timestamp_str = PAPERTRAIL_LINK_TEMPLATE.format(
        timestamp=t.origin_timestamp.strftime(TIMESTAMP_TEMPLATE),
        instance_id=t.instance_id,
        papertrail_id=t.origin_papertrail_id,
    )

    # link to profile

    # link to kibana archive
    kibana_link = KIBANA_TEMPLATE.format(kibana_address=KIBANA_ADDRESS, papertrail_id=t.origin_papertrail_id)
    archive_str = "[Archive|%s]" % (kibana_link)

    # put it all together
    combined_str = ', '.join(
        s for s in (
            timestamp_str,
            archive_str,
        ) if s is not None
    )
    return ' - %s' % combined_str
