"""
    Generate L{traceback.Traceback}s from gzipped Papertrail log files

    Uses L{logline.LogLine}s as an intermediate step between individual lines and a full Traceback.
"""
import collections
import datetime
import itertools
import gzip
import logging
import re

import pytz

from .logline import LogLine
from .traceback import Traceback


ERROR_REGEX = re.compile('\nAssertionError|\nKeyError|\nNotImplementedError|\nValueError')
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

NUM_PREVIOUS_LOG_LINES_TO_SAVE = 50
"""
    How many log lines previous to our AssertionError we should save.

    I'm purposely going high with this number since it's easier to ignore data than re-query for it
"""

LOG_TIMEZONE = pytz.timezone("US/Eastern")
"""
    Timezone in which the logs were taken

    We translate Papertrail's UTC timestamps into this timezone
"""

logger = logging.getLogger()


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
        formatted_line,
    ) = __parse_papertrail_log_line(raw_log_line)

    return LogLine(
        parsed_log_message,
        formatted_line,
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

        Returns None on failure
    """
    log_lines = itertools.chain(previous_loglines, [origin_logline])
    log_lines1, log_lines2 = itertools.tee(log_lines)

    raw_full_text = ''.join(logline.raw_log_message for logline in log_lines1)
    raw_traceback_text = _get_last_traceback_text_raw(raw_full_text)

    parsed_text = ''.join(logline.parsed_log_message for logline in log_lines2)
    traceback_text, traceback_plus_context_text = _get_last_traceback_text(parsed_text)
    if traceback_text is None or traceback_plus_context_text is None:
        return None

    return Traceback(
        traceback_text,
        traceback_plus_context_text,
        raw_traceback_text,
        raw_full_text,
        origin_logline.papertrail_id,
        origin_logline.timestamp,
        origin_logline.instance_id,
        origin_logline.program_name,
    )


def _get_last_traceback_text(parsed_log_text):
    """
        For the given parsed log text, filter out just the last traceback text.

        All python tracebacks start with the string 'Traceback (most recent call last)'. We grab
        the last one in the parsed text.

        Returns a two-tuple:
            - the parsed traceback (so no metadata, shows just the message)
            - the parsed traceback (so no metadata), plus the last few lines before the start of
                the traceback (to give a little context); the extra lines are also parsed (include
                no metadata).

        If we can't parse out the traceback, returns a two-tuple of (None, None)
    """
    assert isinstance(parsed_log_text, str), (type(parsed_log_text), parsed_log_text)

    previous_text, sep, traceback_text = parsed_log_text.rpartition(
        'Traceback (most recent call last)'
    )
    if len(sep) == 0:
        logger.warning("unable to parse out Traceback. text: %s", parsed_log_text)
        return (None, None)
    context_lines = '\n'.join(previous_text.splitlines()[-3:])
    return sep + traceback_text, context_lines + '\n' + sep + traceback_text


def _get_last_traceback_text_raw(raw_log_text):
    """
        For the given parsed log text, filter out just the last traceback text.

        All python tracebacks start with the string 'Traceback (most recent call last)'. We grab
        the last one in the text.

        If we can't parse out the traceback, returns an empty string.

        Returns the traceback text in its 'raw' form, including the log metadata (so it's exactly
        what you see in papertrail).
    """
    assert isinstance(raw_log_text, str), (type(raw_log_text), raw_log_text)

    # find the line that has the 'Traceback' label in it. start from the bottom (so if there's more
    # than one, we get the last one)
    index = None
    lines = raw_log_text.splitlines()
    for index, line in enumerate(reversed(lines)):
        if 'Traceback (most recent call last)' in line:
            break

    # 'index' is now the line number of the start of our traceback, counting from the bottom. get
    # it and all the lines after it
    if index is None:
        return ''
    else:
        return '\n'.join(lines[-(index + 1):])


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
            - the "formatted line", which is how papertrail displays the log line to the user. if
              you were to copy/paste the line out of papertrail, this is what you'd get

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

    timestamp_utc = datetime.datetime.strptime(
        timestamp_string, '%Y-%m-%dT%H:%M:%S'
    ).replace(tzinfo=pytz.UTC)
    timestamp_with_tz = timestamp_utc.astimezone(LOG_TIMEZONE)

    # formatted line looks like this, seperated by spaces:
    # - three letter month
    # - two letter day
    # - time 00:00:00
    # - instance id
    # - program name
    # - log message
    formatted_timestamp = timestamp_with_tz.strftime('%b %d %H:%M:%S')
    formatted_line = '%s %s %s:  %s' % (
        formatted_timestamp, instance_id, program_name, parsed_log_message
    )

    return (
        papertrail_id,
        timestamp_with_tz,
        instance_id,
        program_name,
        parsed_log_message,
        formatted_line,
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

            # search backwards to grab the previous X traceback lines
            previous_log_lines = list(
                itertools.islice(
                    __get_previous_log_lines(lifo_buffer, origin_line),
                    NUM_PREVIOUS_LOG_LINES_TO_SAVE
                )
            )

            traceback = __generate_Traceback(origin_line, reversed(previous_log_lines))
            if traceback is not None:
                yield traceback

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
