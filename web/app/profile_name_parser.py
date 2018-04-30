""" Finds the relevant profile and/or username name for a given Traceback """

import logging
import re
import typing

from .traceback import Traceback


logger = logging.getLogger()


def parse(traceback: Traceback) -> Traceback:
    """
        Parses the profile name from the Traceback's log lines.

        If we find a profile name, returns the original Traceback (the same object) with the
        profile_name field updated. Otherwise, returns None.
    """
    log_lines = traceback.raw_full_text.splitlines()
    precursor_lines = __strip_traceback_text(log_lines)

    # look backwards until we find the first ERROR line
    index = __find_first_error_line(precursor_lines)
    if index is None: return None

    profile_name = None
    username = None
    if 'update.debug' in traceback.program_name:
        # Apr 16 23:37:09 i-dskfj-j update.debug:  16/Apr/2018:23:37:09.674 23502/#upd:qa-jgon_0918-aws2:3fab             : ERROR    w.update: Failed to update profile `qa-jgon_0918-aws2' (145 of 226)
        # Apr 16 23:37:09 i-dskfj-j update.debug:  Traceback (most recent call last):

        # the error line also contains our profile name
        match = re.search('#upd:(\S+?):', precursor_lines[index])
        if not match: return None
        potential_profile_name = match.groups()[0]

        # in some cases, we can get a user name instead of a profile name. check
        if '@' in potential_profile_name:
            username = profile_name
        else:
            # ok, it's a profile name
            profile_name = potential_profile_name
    elif 'activity-worker' in traceback.program_name:
        # Mar 05 15:26:24 i-ksdfj-e swf.quickstart.activity-worker:  05/Mar/2018:15:26:24.462 7339/#prod!310595!AW!quick_start:beekeeping_cc_28910:HB: DEBUG    utils.swf.activity_worker.SwfHeartbeatGenerator: STOP
        # Mar 05 15:26:24 i-ksdfj-e swf.quickstart.activity-worker:  05/Mar/2018:15:26:24.462 7339/#prod!310595!AW!quick_start:beekeeping_cc_28910: ERROR    utils.swf.activity_worker.AbstractSwfActivityWorker: Caught exception while processing activity task, failing
        # Mar 05 15:26:24 i-ksdfj-e swf.quickstart.activity-worker:  Traceback (most recent call last):

        # Mar 16 09:06:32 i-jksdfj-g swf.reporting.activity-worker:  16/Mar/2018:09:06:32.572 7392/#SCH-53f16ea3-f310-4adb-bdc5-cc767f85a0a2:topherbrown: ERROR    engine.services.wordstream.swf_reporting.activity_worker.ReportingSwfActivityWorker:
        # Mar 16 09:06:32 i-jksdfj-g swf.reporting.activity-worker:  Traceback (most recent call last):

        # the error line also contains our profile name
        match = re.search(':(\S+):\s+ERROR', precursor_lines[index])
        if not match: return None
        profile_name = match.groups()[0]
    if 'engine.server.debug' in traceback.program_name or 'manager.debug' in traceback.program_name:
        # Mar 20 18:20:50 i-kjsdf-g aws2.engine.server.debug:  20/Mar/2018:18:20:50.834 15165/WS#ttt-solutions-ttt-res-admin@ttt-solutions.com: DEBUG    w.services: f,152158 4424.1889 ChangesHandler (POST) took 26645 milliseconds to complete and final memory 417MB (delta 0MB)
        # Mar 20 18:20:50 i-kjsdf-g aws2.engine.server.debug:  20/Mar/2018:18:20:50.834 15165/MainThread : ERROR    w.services: Unexpected error 500 Internal Server Error
        # Mar 20 18:20:50 i-kjsdf-g aws2.engine.server.debug:  Traceback (most recent call last):

        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  22/Mar/2018:09:36:51.614 17105/WS#topher_brown-@tbrown                 : DEBUG    w.services: f,1521725785.5479 ChangesHandler (POST) took 26066 milliseconds to complete and final memory 772MB (delta 0MB)
        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  22/Mar/2018:09:36:51.617 15176/MainThread                              : DEBUG    w.services: s,1521725811.6175 ChangesHandler (GET) starting memory 605MB
        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  22/Mar/2018:09:36:51.615 17105/MainThread                              : ERROR    w.services: Unexpected error 500 Internal Server Error
        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  Traceback (most recent call last):

        # Apr 01 07:12:16 i-kdsfj-h manager.debug:  01/Apr/2018:07:12:16.992 30740/PV#hoper-brown-topher@topherland.com:     DEBUG    wordstream.services: f,1522581136.9207 ChangesHandler (GET) took 72 milliseconds to complete and final memory 241MB (delta 0MB)
        # Apr 01 07:12:16 i-kdsfj-h manager.debug:  01/Apr/2018:07:12:16.992 30740/MainThread                              : ERROR    wordstream.services: Unexpected HTTP Exception
        # Apr 01 07:12:16 i-kdsfj-h manager.debug:  Traceback (most recent call last):

        # we can use the error line to the process PID
        pid_match = re.search('\s(\d+)/MainThread', precursor_lines[index])
        if not pid_match: return None
        pid = pid_match.groups()[0]

        # look backwards for the previous line with that same PID
        index2 = None
        for index2 in range(index - 1, -1, -1):
            if pid in precursor_lines[index2]:
                break
        if index2 is None: return None

        # grab the profile name and user name
        match = re.search('/(?:WS|PV)#(\S+)-(\S*@\S+)\s*:', precursor_lines[index2])
        if not match: return None
        profile_name = match.groups()[0]
        username = match.groups()[1]

    if (
            (profile_name and username)
            and (
                'zauto' in profile_name or 'zauto' in username
            )
    ):
        # automation has weird names. let's fix it manually
        try:
            profile_name, username = re.match('(\S*)-(zauto\S+?)$', profile_name + '-' + username).groups()[:2]
        except Exception:
            print('unable to handle zauto. %s, %s' % profile_name, username)

    # modify the traceback if we found anything
    modified = False
    if profile_name:
        traceback.profile_name = profile_name
        modified = True
    if username:
        traceback.username = username
        modified = True
    if not modified:
        return None
    return traceback


def __strip_traceback_text(log_lines: typing.List[str]) -> typing.Optional[typing.List[str]]:
    """ Given a set of log lines ending in a traceback, removes the traceback text """
    index = None
    for index, line in enumerate(reversed(log_lines)):
        if 'Traceback (most recent call last)' in line:
            break
    if index is None:
        return None
    return log_lines[:-(index + 1)]


def __find_first_error_line(log_lines: typing.List[str]) -> typing.Optional[int]:
    """ Looks backwards at the log lines until it founds the first line with ERROR """
    index = None
    for index in range(len(log_lines) - 1, -1, -1):
        if 'ERROR' in log_lines[index]:
            break
    return index
