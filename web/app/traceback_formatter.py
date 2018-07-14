from typing import Optional
import logging

from .traceback import Traceback

from . import (
    config_util,
)

logger = logging.getLogger()

KIBANA_REDIRECT_URL=config_util.get('KIBANA_REDIRECT_URL')
PRODUCT_URL=config_util.get('PRODUCT_URL')

TIMESTAMP_TEMPLATE = '%b %d %Y %H:%M:%S'
"""
    A template for human-readable timestamps. Timezone info is ignored.

    To be used by datetime a datetime object like this: `dt.strftime(TIMESTAMP_TEMPLATE)`
"""

PAPERTRAIL_LINK_JIRA_TEMPLATE = "[{{{{{timestamp}}}}}|{kibana_redirect_url}/api/traceback/{papertrail_id}]"
PAPERTRAIL_LINK_SLACK_TEMPLATE = "<{kibana_redirect_url}/api/traceback/{papertrail_id}|{timestamp}>"
"""
    A template for a link to papertrail, with the timestamp as the human-readable string.

    Instead of linking directly to papertrail, we include a redirect service. This lets us
    dynamically link to the Elasticsearch archive after the papertrail link has been recycled.

    Caller must provide:
    - timestamp, from TIMESTAMP_TEMPLATE
    - a link to a service that redirects to kibana. example: 'https://kibana-redirect.company.com'
    - the papertrail id document to open. example: '926890000000000000'
"""

PROFILE_NAME_JIRA_TEMPLATE = "[{profile_name}|{product_url}/admin/profile/{profile_name}]"
PROFILE_NAME_SLACK_TEMPLATE = "<{product_url}/admin/profile/{profile_name}|{profile_name}>"
"""
    A template for the profile name, with a link to that profile in the product.

    Requires these strings:
    - profile_name
    - product_url, with no trailing slash
"""

USERNAME_JIRA_TEMPLATE = "[{username}|{product_url}/admin/user/{username}]"
USERNAME_SLACK_TEMPLATE = "<{product_url}/admin/user/{username}|{username}>"
"""
    A template for the username, with a link to that user in the product.

    Requires these strings:
    - username
    - product_url, with no trailing slash
"""


def jira_formatted_string(t: Traceback, include_profile_link: bool, include_user_link: bool) -> str:
    """
        Given a traceback, returns a well formatting string in Jira's bad formatting

        We have four parts to our formatted string:
        - a timestamp, with a link to our papertrail/kibana redirect service
        - a profile name, with a link to the product's profile. may not exist
        - a user name, with a link to the product's user. may not exist

        We include two booleans to control extra links. The reason we do that is because we easily
        run up against Jira's max comment size. Adding these booleans lets us reduce comment size.
    """
    # timestamp and link to papertrail
    timestamp_str = PAPERTRAIL_LINK_JIRA_TEMPLATE.format(
        timestamp=t.origin_timestamp.strftime(TIMESTAMP_TEMPLATE),
        kibana_redirect_url=KIBANA_REDIRECT_URL,
        papertrail_id=t.origin_papertrail_id
    )

    # link to profile and user
    profile_str = None
    if t.profile_name:
        if include_profile_link:
            profile_str = PROFILE_NAME_JIRA_TEMPLATE.format(
                profile_name=t.profile_name,
                product_url=PRODUCT_URL
            )
        else:
            profile_str = t.profile_name
    user_str = None
    if t.username:
        if include_user_link:
            user_str = USERNAME_JIRA_TEMPLATE.format(
                username=t.username,
                product_url=PRODUCT_URL
            )
        else:
            user_str = t.username

    # put it all together
    combined_str = ', '.join(
        s for s in (
            timestamp_str,
            profile_str,
            user_str,
        ) if s is not None
    )
    return ' - %s' % combined_str



def slack_formatted_string(t: Traceback, include_profile_link: bool, include_user_link: bool) -> str:
    """
        Given a traceback, returns a well formatting string in Slacks bad formatting

        We have four parts to our formatted string:
        - a timestamp, with a link to our papertrail/kibana redirect service
        - a profile name, with a link to the product's profile. may not exist
        - a user name, with a link to the product's user. may not exist
    """
    # timestamp and link to papertrail
    timestamp_str = PAPERTRAIL_LINK_SLACK_TEMPLATE.format(
        timestamp=t.origin_timestamp.strftime(TIMESTAMP_TEMPLATE),
        kibana_redirect_url=KIBANA_REDIRECT_URL,
        papertrail_id=t.origin_papertrail_id
    )

    # link to profile and user
    profile_str = None
    if t.profile_name:
        if include_profile_link:
            profile_str = PROFILE_NAME_SLACK_TEMPLATE.format(
                profile_name=t.profile_name,
                product_url=PRODUCT_URL
            )
        else:
            profile_str = t.profile_name
    user_str = None
    if t.username:
        if include_user_link:
            user_str = USERNAME_SLACK_TEMPLATE.format(
                username=t.username,
                product_url=PRODUCT_URL
            )
        else:
            user_str = t.username

    # put it all together
    combined_str = ', '.join(
        s for s in (
            timestamp_str,
            profile_str,
            user_str,
        ) if s is not None
    )
    return ' - %s' % combined_str


def create_hits_list(tracebacks, formatter:callable, max_number_hits:Optional[int]=None):
    """
        Creates a well formatted list of strings, given a list of tracebacks

        Jira has a limit of 32767 characters per comment. We will try to keep it under 25000.

        @param formatter: one of (slack_formatted_string, jira_formatted_string)
    """
    seen_profile_names = set()
    seen_usernames = set()
    hits_list = []
    for t in tracebacks:
        # if it's the first time seeing this profile or username, include links to them
        if t.profile_name and t.profile_name not in seen_profile_names:
            include_profile_link = True
            if t.profile_name.isdigit():
                # it's not a profile name, it's a profile id. don't include a link
                include_profile_link = False
            seen_profile_names.add(t.profile_name)
        else:
            include_profile_link = False
        if t.username and t.username not in seen_usernames:
            include_username_link = True
            seen_usernames.add(t.username)
        else:
            include_username_link = False

        # don't include links to admin users
        if t.username and t.username.startswith('@'):
            include_username_link = False

        hits_list.append(formatter(t, include_profile_link, include_username_link))

    # keep trying fewer and fewer comments until we fit
    index = len(hits_list)
    if max_number_hits:
        index = min(index, max_number_hits)
    for index in range(index, 0, -1):
        comment_string = '\n'.join(hits_list[:index])
        if len(comment_string) < 25000:
            break

    logger.info(
        'for %s tracebacks, built %s hits and took the first %s for a %s char comment',
        len(tracebacks), len(hits_list), index, len(comment_string)
    )

    return comment_string
