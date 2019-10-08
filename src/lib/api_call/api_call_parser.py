import logging
import re

from lib.api_call.api_call import ApiCall
from common_util.parser_util import ParserUtil


API_CALL_REGEX = re.compile((
    '\d+/\w+#(?:(?P<profile_name>\w+)-)?'
    '(?P<username>[a-zA-Z0-9_\.+\-@]+).*\s(?P<api_name>\w+)\s\((?P<method>[A-Z]+)\) '
    'took (?P<duration>\d+) milliseconds to complete'
    '(?: and final memory (?P<memory_final>-?\d+)MB \(delta (?P<memory_delta>-?\d+)MB\))?'
))
"""
    Regex we can use to get information about API calls from the log message

    Example log message:
        05/Dec/2016:09:00:00.004 6012/WS#name-profile_name@name.com   : DEBUG    wordstream.services: f,1480946399.9936 IsGetInProgressHandler (GET) took 11 milliseconds to complete and final memory 236MB (delta -1MB)


    Groups from this regex (with the value from our Example in parens):
        1: profile_name (name). may be missing
        2: username (profile_name@name.com)
        3: api_name (IsGetInProgressHandler)
        4: method (GET)
        5: duration in ms (11)
"""

SERVERS_WE_CARE_ABOUT = frozenset((
    'engine.server.debug',
    'manager.debug',
))
"""
    Set of server names of which we care about requests
"""

logger = logging.getLogger()


class ApiCallParser():
    @staticmethod
    def parse_stream(file_object):
        """
            Yields a generator of all L{ApiCall} found in L{file_object}

            L{file_object} can be any file-like stream object that generates lines of logs
        """
        for log_line in file_object:
            assert len(log_line) > 1, log_line  # make sure we're getting real lines
            assert isinstance(log_line, str), log_line

            if ApiCallParser.__log_line_contains_api_call_with_timing(log_line):
                api_call = ApiCallParser.__generate_ApiCall(log_line)
                if api_call is not None:
                    yield api_call

    @staticmethod
    def __log_line_contains_api_call_with_timing(log_line):
        """
            Checks that the given log line has an authenticated API call with timings
        """
        if 'milliseconds to complete' not in log_line:
            # we don't have timings
            return False
        if 'MainThread' in log_line:
            # anything with 'MainThread' doesn't have profile-level authentication
            return False
        if not any(server in log_line for server in SERVERS_WE_CARE_ABOUT):
            # the request isn't coming from a server we care about
            return False
        return True

    @staticmethod
    def __generate_ApiCall(log_line):
        """
            Takes a raw log_line from Papertrail and creates a L{ApiCall} object

            Returns None if our regex cannot parse the log line correctly. Logs the erroring line
            with a WARNING
        """
        (
            papertrail_id,
            timestamp,
            instance_id,
            program_name,
            parsed_log_message,
            _,
        ) = ParserUtil.parse_papertrail_log_line(log_line)

        match = re.search(API_CALL_REGEX, parsed_log_message)
        if not match:
            logger.debug('api call parser failed on log line: %s', log_line)
            return None

        duration = int(match.group('duration'))

        # memory stats are only available in more modern log files
        memory_final = None
        memory_delta = None
        memory_final_str = match.group('memory_final')
        memory_delta_str = match.group('memory_delta')
        if memory_final_str:
            memory_final = int(memory_final_str)
        if memory_delta_str:
            memory_delta = int(memory_delta_str)

        return ApiCall(
            timestamp,
            papertrail_id,
            instance_id,
            program_name,
            match.group('api_name'),
            match.group('profile_name') if match.group('profile_name') else None,
            match.group('username'),
            match.group('method'),
            duration,
            memory_final,
            memory_delta,
        )
