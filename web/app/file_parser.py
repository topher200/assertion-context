"""
    Generate L{traceback.Traceback}s from gzipped Papertrail log files

    Uses L{logline.LogLine}s as an intermediate step between individual lines and a full Traceback.
"""
import collections
import datetime
import itertools
import gzip
import re

from .logline import LogLine
from .traceback import Traceback


ERROR_REGEX = re.compile('AssertionError|KeyError|NotImplementedError|ValueError')
ASSERTION_ERROR_REGEX_NEGATIVE = re.compile(
    '''(details = AssertionError)|(AssertionError.*can only join a child process)'''
)
KEY_ERROR_REGEX_NEGATIVE = re.compile(
    '''threading.pyc|args:\['''
)
"""
    Our regexes are by the Papertrail search we perform against production, which looks like this:
        (AssertionError -"details = AssertionError" -"can only join a child process")
            OR (KeyError -threading.pyc -args:[)
            OR (NotImplementedError)
            OR (ValueError)
"""


def __generate_LogLine(raw_log_line, origin_papertrail_id, line_number):
    """
        Takes a L{raw_log_line} and metadata and returns a L{LogLine}

        If L{origin_papertrail_id} is None, we're the origin! We use our own generated
        L{papertrail_id} as the L{origin_papertrail_id}.
    """
    (
        papertrail_id,
        timestamp,
        instance_id,
        program_name,
        parsed_log_message,
    ) = __parse_papertrail_log_line(raw_log_line)

    return LogLine(
        parsed_log_message,
        raw_log_line,
        timestamp,
        papertrail_id,
        origin_papertrail_id if origin_papertrail_id is not None else papertrail_id,
        line_number,
        instance_id,
        program_name,
    )


def __generate_Traceback(origin_logline, previous_loglines):
    """
        Combines L{LogLine}s into a L{Traceback}.
    """
    parsed_text = ''.join(map(str, itertools.chain(previous_loglines, [origin_logline])))
    return Traceback(
        parsed_text,
        origin_logline.papertrail_id,
        origin_logline.timestamp,
        origin_logline.instance_id,
        origin_logline.program_name,
    )


def __parse_papertrail_log_line(raw_log_line):
    """
        Parse out interesting parts of a Papertrail log line

        Papertrail log lines take this form (I've replaced tabs with newlines):
            700594297938165774
            2016-08-12T03:18:39
            2016-08-12T03:18:39Z
            407484803
            i-2ee330b7
            107.21.188.48
            User
            Notice
            manager.debug
            AssertionError

        We parse out the following parts:
            - the papertrail log line id, the 1st column
            - the log timestamp, the 2st column
            - the instance id, the 5th column
            - the running program name, the 9th column
            - the actual log message, which is everything after the 9th column

        In addition to parsing out the text for every field, we convert the timestamp field to a
        L{datetime}. Times in the logs are UTC (thanks Papertrail!)

        Returns the above fields as a tuple.
    """
    assert isinstance(raw_log_line, str), (type(raw_log_line), raw_log_line)

    log_line_pieces = raw_log_line.split('\t', 9)
    assert len(log_line_pieces) == 10, log_line_pieces
    papertrail_id = log_line_pieces[0]
    timestamp_string = log_line_pieces[1]
    instance_id = log_line_pieces[4]
    program_name = log_line_pieces[8]
    parsed_log_message = log_line_pieces[9]

    timestamp = datetime.datetime.strptime(timestamp_string, '%Y-%m-%dT%H:%M:%S')

    return (
        papertrail_id,
        timestamp,
        instance_id,
        program_name,
        parsed_log_message,
    )


def __get_previous_log_lines(circular_buffer, origin_line):
    """
        Searches backwards in L{circular_buffer} for lines that match the given specs.

        Lines are considered matching if they
            - share the instance_id of L{origin_line}
            - share the program_name L{origin_program_name}

        yields L{LogLine}s. All L{LogLine}s yielded will have the L{origin_papertrail_id} of
        L{origin_line} and a L{line_number} > 0.

        This function has the possibility to return an infinite number of values; it's the caller's
        responsibility to cut off the hose at some point.
    """
    line_number = 1
    for raw_line in list(circular_buffer)[::-1]:
        assert isinstance(raw_line, str), raw_line
        log_line = __generate_LogLine(raw_line, origin_line.papertrail_id, line_number)
        if ((log_line.instance_id == origin_line.instance_id) and
            (log_line.program_name == origin_line.program_name)):
            # This line matches our origin line!
            yield log_line
            line_number += 1

def log_line_contains_important_error(log_line):
    """
        Returns True if the log line contains an AssertionError (or other important error)

        Defined by the Papertrail search we perform against production, which looks like this:
            (AssertionError -"details = AssertionError" -"can only join a child process")
                OR (KeyError -threading.pyc -args:[)
                OR (NotImplementedError)
                OR (ValueError)
    """
    # implementation note: since the regex contains "negative" fields, we check for the things we
    # want then reject if it contains things we don't.

    if re.search(ERROR_REGEX, log_line) is None:
        return False

    # We want the checks before this point to be super fast, since that part gets called a lot.
    # It's OK if the checks after this point are more readable than efficient since this is the
    # infrequently-traveled code path

    if 'AssertionError' in log_line:
        if re.search(ASSERTION_ERROR_REGEX_NEGATIVE, log_line) is not None:
            return False

    if 'KeyError' in log_line:
        if re.search(KEY_ERROR_REGEX_NEGATIVE, log_line) is not None:
            return False

    return True


def parse(file_object):
    """
        Yields a generator of all L{Traceback} found in L{file_object}

        A Traceback is generated by finding a log line that has an important error (like an
        AssertionError), then working backwards in the logs to find the associated log lines
        previous to it.

        L{file_object} is expected to be an open file, but can be anything that generates lines of
        log files.
    """
    # We use a LIFO buffer to keep track of the last few lines. When we find an
    # AssertionError, we search backwards in the log lines to find the lines previous from that
    # machine
    lifo_buffer = collections.deque(maxlen=10000)
    for line in file_object:
        assert len(line) > 1, line  # make sure we're getting real lines
        assert isinstance(line, str), line

        # see if this line has an error we care about
        if log_line_contains_important_error(line):
            # we found a match! build a traceback out of it
            origin_line = __generate_LogLine(line, None, 0)

            # search backwards to grab the previous 10 traceback lines
            previous_10_log_lines = (
                itertools.islice(
                    __get_previous_log_lines(lifo_buffer, origin_line),
                    10
                )
            )

            yield __generate_Traceback(origin_line, previous_10_log_lines)

        # now that we're done processing this line, add it to the buffer
        assert isinstance(line, str), line
        lifo_buffer.append(line)


def parse_gzipped_file(zipped_filename):
    """
        Opens the gzipped file given by L{zipped_filename} and calls L{parse} on it

        Doesn't perform any checks to confirm that it is a gzip'd file.

        Returns a list of L{Traceback}s
    """
    with gzip.open(zipped_filename, 'rt', encoding='UTF-8') as f:
        return list(parse(f))
