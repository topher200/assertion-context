from .traceback import Traceback

from . import (
    config_util,
)


ES_ADDRESS=config_util.get('ES_ADDRESS')
PRODUCT_URL=config_util.get('PRODUCT_URL')

TIMESTAMP_TEMPLATE = '%b %d %Y %H:%M:%S'
"""
    A template for human-readable timestamps. Timezone info is ignored.

    To be used by datetime a datetime object like this: `dt.strftime(TIMESTAMP_TEMPLATE)`
"""

KIBANA_TEMPLATE = "{kibana_address}/_plugin/kibana/app/kibana#/discover?_g=(time:(from:now-50y))&_a=(query:(language:lucene,query:'{papertrail_id}'))"
"""
    A template for linking to a papertrail object in kibana.

    Caller must provide:
    - a link to the kibana domain, no trailing slash. example: 'https://kibana.company.com'
    - the papertrail id to highlight on. example: '926899256000330036'
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
    kibana_link = KIBANA_TEMPLATE.format(kibana_address=ES_ADDRESS, papertrail_id=t.origin_papertrail_id)
    archive_str = "[Archive|%s" % (kibana_link)
    combined_str = ', '.join((
        timestamp_str,
        archive_str,
    ))
    return ' - %s' % combined_str
