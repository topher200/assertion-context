"""
    Generate L{logline.LogLine}s from gzipped Papertrail log files
"""
import collections
import datetime
import itertools
import gzip

from .logline import LogLine


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
        log_line = __generate_LogLine(raw_line, origin_line.papertrail_id, line_number)
        if ((log_line.instance_id == origin_line.instance_id) and
            (log_line.program_name == origin_line.program_name)):
            # This line matches our origin line!
            yield log_line
            line_number += 1


def parse(file_object):
    """
        Yields a generator of all the relevant L{LogLine} found in L{file_object}

        A relevant log line is one that either has an AssertionError on it or is related to one.

        L{file_object} is expected to be an open file, but can be anything that generates lines of
        log files.
    """
    # We use a circular buffer to keep track of the last few lines. When we find an
    # AssertionError, we search backwards in the log lines to find the lines previous from that
    # machine
    circular_buffer = collections.deque(maxlen=10000)
    for line in file_object:
        assert len(line) > 1, line  # make sure we're getting real lines

        # see if this line has an important error
        if 'AssertionError' in line:
            # we found a match! return it
            origin_line = __generate_LogLine(line, None, 0)
            yield origin_line

            # search backwards to grab the previous 10 traceback lines
            previous_10_lines = (
                itertools.islice(
                    __get_previous_log_lines(circular_buffer, origin_line),
                    10
                )
            )
            for line in previous_10_lines:
                yield line

        # now that we're done processing this line, add it to the buffer
        circular_buffer.append(line)


def parse_gzipped_file(zipped_filename):
    """
        Opens the gzipped file given by L{zipped_filename} and calls L{parse} on it

        Doesn't perform any checks to confirm that it is a gzip'd file.

        Returns a list of L{LogLine}s
    """
    with gzip.open(zipped_filename, 'r') as f:
        return list(parse(f))
