import datetime
import json
import logging
from pprint import pprint

import requests


logger = logging.getLogger()

__EIGHT_HOURS_IN_SECONDS = 60 * 60 * 8

FULLSTORY_AUTH_TOKEN = "Basic XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

def get_fullstory_link(profile_name:str, timestamp_string:str):
    # We get the datetime as a string, we need to parse it out. timestamp becomes "seconds since
    # epoch"
    try:
        timestamp = datetime.datetime.strptime(
            timestamp_string,
            '%Y-%m-%dT%H:%M:%S%z'
        ).timestamp()
    except ValueError:
        # no timezone info on this one
        timestamp = datetime.datetime.strptime(
            timestamp_string,
            '%Y-%m-%dT%H:%M:%S'
        ).timestamp()

    # get available fullstory sessions for this profile
    url = 'https://www.fullstory.com/api/v1/sessions?uid=%s' % profile_name
    headers = {'Authorization': FULLSTORY_AUTH_TOKEN}
    sessions = requests.get(url, headers=headers).json()

    logger.debug('Found %s sessions for %s', len(sessions), profile_name)
    # Example of the 'sessions' object from fullstory:
    #     [{
    #         'CreatedTime': 1541780000,
    #         'FsUrl': 'https://www.fullstory.com/ui/AZ1TC/session/5721895350000000:5668600000000000',
    #         'SessionId': 5668600000000000,
    #         'UserId': 5721800000000000
    #     }]

    # figure out which session was the most recent before our error
    most_recent_session = None
    for session in sessions:
        # session['CreatedTime'] is in seconds since epoch
        if session['CreatedTime'] < timestamp:
            # this session started before our timestamp; it could include our timestamp
            if (
                    most_recent_session is None or
                    most_recent_session['CreatedTime'] < session['CreatedTime']
            ):
                # this session is more recent than any other qualified ones we've seen
                most_recent_session = session

    if not most_recent_session:
        logger.debug('No eligible sessions found')
        return None # unable to find a qualified session

    if timestamp - most_recent_session['CreatedTime'] > __EIGHT_HOURS_IN_SECONDS:
        logger.debug(
            'The closest session start time (%s) was too far in the past of error time (%s)',
            most_recent_session['CreatedTime'],
            timestamp
        )
        return None

    timestamp_in_millis = timestamp * 1000 # fullstory URL timestamps are millis
    link_to_session = '%s:%d' % (most_recent_session['FsUrl'], timestamp_in_millis)

    return link_to_session

pprint(get_fullstory_link('example_username', '2018-11-16T10:23:44-0500'))
