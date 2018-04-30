from .traceback import Traceback

from . import (
    config_util,
)


KIBANA_REDIRECT_URL=config_util.get('KIBANA_REDIRECT_URL')
PRODUCT_URL=config_util.get('PRODUCT_URL')

TIMESTAMP_TEMPLATE = '%b %d %Y %H:%M:%S'
"""
    A template for human-readable timestamps. Timezone info is ignored.

    To be used by datetime a datetime object like this: `dt.strftime(TIMESTAMP_TEMPLATE)`
"""

PAPERTRAIL_LINK_TEMPLATE = "[{{{{{timestamp}}}}}|https://papertrailapp.com/systems/{instance_id}/events?focus={papertrail_id}]"
"""
    A template for a link to papertrail, with the timestamp as the human-readable string.

    Requires these strings:
    - timestamp, from TIMESTAMP_TEMPLATE
    - papertrail instance id. example: i-029b0000000000000
    - papertrail log line id. example: 926921020000000000
"""

PROFILE_NAME_TEMPLATE = "[{profile_name}|{product_url}/admin/profile/{profile_name}]"
"""
    A template for the profile name, with a link to that profile in the product.

    Requires these strings:
    - profile_name
    - product_url, with no trailing slash
"""

USERNAME_TEMPLATE = "[{username}|{product_url}/admin/user/{username}]"
"""
    A template for the username, with a link to that user in the product.

    Requires these strings:
    - username
    - product_url, with no trailing slash
"""

ARCHIVE_TEMPLATE = "[Archive|https://{kibana_redirect_url}/api/traceback/{papertrail_id}"
"""
    A template for linking to a papertrail object archive.

    Caller must provide:
    - a link to a service that redirects to kibana. example: 'https://kibana-redirect.company.com'
    - the papertrail id document to open. example: '926890000000000000'
"""


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

    # link to profile and user
    profile_str = None
    if t.profile_name:
        profile_str = PROFILE_NAME_TEMPLATE.format(
            profile_name=t.profile_name,
            product_url=PRODUCT_URL
        )
    user_str = None
    if t.username:
        user_str = USERNAME_TEMPLATE.format(
            username=t.username,
            product_url=PRODUCT_URL
        )

    # link to kibana archive
    archive_str = ARCHIVE_TEMPLATE.format(
        kibana_redirect_url=KIBANA_REDIRECT_URL,
        papertrail_id=t.origin_papertrail_id
    )

    # put it all together
    combined_str = ', '.join(
        s for s in (
            timestamp_str,
            profile_str,
            user_str,
            archive_str,
        ) if s is not None
    )
    return ' - %s' % combined_str
