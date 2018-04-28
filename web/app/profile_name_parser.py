""" Finds the relevant profile and/or user name for a given Traceback """

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

    if traceback.program_name == 'update.debug':
        # Apr 16 23:37:09 i-dskfj-j update.debug:  16/Apr/2018:23:37:09.674 23502/#upd:qa-jgon_0918-aws2:3fab             : ERROR    w.update: Failed to update profile `qa-jgon_0918-aws2' (145 of 226)
        # Apr 16 23:37:09 i-dskfj-j update.debug:  Traceback (most recent call last):

        # the error line also contains our profile name
        match = re.search('#upd:(\S+?)\s*:', precursor_lines[index])
        if not match: return None
        profile_name = match.groups()[0]

        # in some cases, we can get a user name instead of a profile name. check
        if '@' in profile_name:
            traceback.user_name = profile_name
            return traceback

        # ok, it's a profile name
        traceback.profile_name = profile_name
        return traceback
    if 'engine.server.debug' in traceback.program_name:
        # Mar 20 18:20:50 i-kjsdf-g aws2.engine.server.debug:  20/Mar/2018:18:20:50.834 15165/WS#ttt-solutions-ttt-res-admin@ttt-solutions.com: DEBUG    w.services: f,152158 4424.1889 ChangesHandler (POST) took 26645 milliseconds to complete and final memory 417MB (delta 0MB)
        # Mar 20 18:20:50 i-kjsdf-g aws2.engine.server.debug:  20/Mar/2018:18:20:50.834 15165/MainThread : ERROR    w.services: Unexpected error 500 Internal Server Error
        # Mar 20 18:20:50 i-kjsdf-g aws2.engine.server.debug:  Traceback (most recent call last):

        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  22/Mar/2018:09:36:51.614 17105/WS#topher_brown-@tbrown                 : DEBUG    w.services: f,1521725785.5479 ChangesHandler (POST) took 26066 milliseconds to complete and final memory 772MB (delta 0MB)
        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  22/Mar/2018:09:36:51.617 15176/MainThread                              : DEBUG    w.services: s,1521725811.6175 ChangesHandler (GET) starting memory 605MB
        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  22/Mar/2018:09:36:51.615 17105/MainThread                              : ERROR    w.services: Unexpected error 500 Internal Server Error
        # Mar 22 09:36:51 i-kdfjk-g aws2.engine.server.debug:  Traceback (most recent call last):

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
        print('match line: %s' % precursor_lines[index2])

        # grab the profile name and user name
        match = re.search('/WS#(\S+?)-(\w*@\S+)\s*:', precursor_lines[index2])
        if not match: return None
        profile_name = match.groups()[0]
        user_name = match.groups()[1]
        print('profile name: %s, user_name: %s' % (profile_name, user_name))

        # modify the traceback if we found anything
        modified = False
        if profile_name:
            traceback.profile_name = profile_name
            modified = True
        if user_name:
            traceback.user_name = user_name
            modified = True
        if not modified: return None
        return traceback
    else:
        return None


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
