from typing import Optional
import logging

import requests

from ..traceback import Traceback
from .. import (
    config_util,
)

__FULLSTORY_AUTH_TOKEN = config_util.get('FULLSTORY_AUTH_TOKEN')

__EIGHT_HOURS_IN_SECONDS = 60 * 60 * 8

__FULLSTORY_SESSIONS_GET_API = 'https://www.fullstory.com/api/v1/sessions?uid={profile_name}&limit={limit}'
"""
    Link to get the sessions for a given profile name.

    Caller must provide these parameters:
        - profile_name: the profile name of the fullstory user. corresponds to the fullstory 'uid'
        - limit: the number of sessions to get for the given user

    ref: https://help.fullstory.com/develop-rest/137382-rest-api-retrieving-a-list-of-sessions-for-a-given-user-after-the-fact
"""

__FULLSTORY_SESSIONS_LIMIT = 100000
"""
    Number of sessions to retrieve for the given user.

    Fullstory API doesn't seem to have real pagination. We'll use an unreasonably high number to
    make sure we get all the sessions.
"""

logger = logging.getLogger()


def get_link_to_session_at_traceback_time(t:Traceback) -> Optional[str]:
    """
        Calls out to fullstory to get the session which includes this error.

        Returns None if...
        - t.profile_name is None
        - we can't find a session that happened before the error
        - the error time and the session start time are more than __EIGHT_HOURS_IN_SECONDS
    """
    if not t.profile_name: return None

    # figure out which session was the most recent before our error
    epoch_timestamp_seconds = t.origin_timestamp.timestamp()
    most_recent_session = {}
    for session in __get_sessions(t.profile_name):
        if session['CreatedTime'] < epoch_timestamp_seconds:
            # this session started before our timestamp; it could include our timestamp
            if (
                    not most_recent_session or
                    most_recent_session['CreatedTime'] < session['CreatedTime']
            ):
                # this session is more recent than any other qualified ones we've seen
                most_recent_session = session

    if not most_recent_session:
        logger.info('No eligible sessions found')
        return None # unable to find a qualified session

    if epoch_timestamp_seconds - most_recent_session['CreatedTime'] > __EIGHT_HOURS_IN_SECONDS:
        logger.info(
            'The closest session start time (%s) was too far in the past of error time (%s)',
            most_recent_session['CreatedTime'],
            epoch_timestamp_seconds
        )
        return None

    timestamp_in_millis = epoch_timestamp_seconds * 1000 # fullstory URL timestamps are millis
    link_to_session = '%s:%d' % (most_recent_session['FsUrl'], timestamp_in_millis)
    return link_to_session

def __get_sessions(profile_name:str) -> list:
    """
        Returns the fullstory sessions for this profile

        Returns an empty list if the profile name is not found in fullstory.

        Example of the response dict from fullstory:
        [
            {
                'CreatedTime': 1541780000, # <---- this is seconds since epoch
                'FsUrl': 'https://www.fullstory.com/ui/AZ1TC/session/5721895350000000:5668600000000000',
                'SessionId': 5668600000000000,
                'UserId': 5721800000000000
            }
        ]
    """
    url = __FULLSTORY_SESSIONS_GET_API.format(
        profile_name=profile_name, limit=__FULLSTORY_SESSIONS_LIMIT)
    headers = {'Authorization': 'Basic %s' % __FULLSTORY_AUTH_TOKEN}
    try:
        sessions = None
        response = requests.get(url, headers=headers)
        if 'no such user' in response.text:
            return []
        sessions = response.json()
        assert isinstance(sessions, list), sessions
        assert all(isinstance(s, dict) for s in sessions), sessions
        assert all('CreatedTime' in s for s in sessions), sessions
    except Exception:
        logging.error(
            'Made request %s, received response "%s", tried to parse sessions but got "%s"',
            url, response, sessions
        )
        raise

    logger.info('Found %s sessions for %s', len(sessions), profile_name)
    return sessions
