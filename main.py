"""
    Generate L{LogLine}s from gzipped Papertrail log files

    This file roughly performs these steps:
    - Take a filename
    - Confirm that the file is zipped
    - Unzip that file and read from it
    - Check each line of the file for AssertionError (or other notable error)
    - When AssertionError is found, determine the instance ID of the offending line
    - Search backwards in the logs for the previous lines from that instance ID
    - Generate a list of all the lines found in this manner
"""

import argparse
import collections
import datetime
import itertools
import gzip
import time


LogLine = collections.namedtuple(
    'LogLine', (
        'parsed_log_message',
        'raw_log_message',
        'datetime',
        'papertrail_id',
        'origin_papertrail_id',
        'line_number',
        'instance_id',
        'program_name',
    )
)
"""
    L{LogLine} holds the data from a single Papertrail log line

    L{LogLine} are related to each other via the concept of an "origin" line. We determine a line is
    significant if it matches an error message we care about, like "AssertionError". The line
    containing the string "AssertionError" (or whatever) is the origin line. We then search
    backwards for related lines from the same instance_id and program name as the origin line.
    Lines found this way are given the same L{origin_papertrail_id} as the origin. They're also
    given a L{line_number}. The origin line always has a L{line_number} of 0, the line directly
    before it will be line 1, etc.

    To help explain this relationship via an example of how this could be used: one could recreate
    the logs as shown by papertrail by taking a set of L{LogLine} that share an
    L{origin_papertrail_id} and arranging them in decending L{line_number} order.

    - parsed_log_message: string containing the parsed log message without any metadata
    - raw_log_message: string containing the original message as found in papertrail
    - datetime: string of the datetime reported by the message. utc. example: 2016-08-12T03:18:39
    - papertrail_id: the int id papertrail gave the log line. assumed to be unique. example:
      700594297938165774
    - origin_papertrail_id: int id of the origin line assossicated with this L{LogLine}
    - line_number: how many lines previous to the origin "AssertionError" line this line was found.
      the "origin" line is always 0
    - instance_id: string of the parsed EC2 instance id of the log line
    - program_name: string of the parsed program name from the log line
"""


def __generate_LogLine(raw_log_line, origin_papertrail_id, line_number):
    """
        Takes a L{raw_log_line} and metadata and returns a L{LogLine}

        If L{origin_papertrail_id} is None, we're the origin! We use our own generated
        L{papertrail_id} as the L{origin_papertrail_id}.
    """
    (
        papertrail_id,
        log_datetime,
        instance_id,
        program_name,
        parsed_log_message,
    ) = __parse_papertrail_log_line(raw_log_line)

    return LogLine(
        parsed_log_message,
        raw_log_line,
        log_datetime,
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
            - the log datetime, the 2st column
            - the instance id, the 5th column
            - the running program name, the 9th column
            - the actual log message, which is everything after the 9th column

        Returns the above fields as a tuple.
    """
    log_line_pieces = raw_log_line.split('\t', 9)
    assert len(log_line_pieces) == 10, log_line_pieces
    papertrail_id = log_line_pieces[0]
    log_datetime = log_line_pieces[1]
    instance_id = log_line_pieces[4]
    program_name = log_line_pieces[8]
    parsed_log_message = log_line_pieces[9]

    return (
        papertrail_id,
        log_datetime,
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
        Returns a list of all the relevant L{LogLine} found in L{file_object}

        A relevant log line is one that either has an AssertionError on it or is related to one.

        L{file_object} is expected to be an open file, but can be anything that generates lines of
        log files.
    """
    # We use a circular buffer to keep track of the last few lines. When we find an
    # AssertionError, we search backwards in the log lines to find the lines previous from that
    # machine
    circular_buffer = collections.deque(maxlen=10000)
    log_lines = []
    for line in file_object:
        assert len(line) > 1, line  # make sure we're getting real lines

        # see if this line has an important error
        if 'AssertionError' in line:
            # we found a match! add it to the list
            origin_line = __generate_LogLine(line, None, 0)
            log_lines.append(origin_line)

            # search backwards to grab the previous 10 traceback lines
            log_lines.extend(
                itertools.islice(
                    __get_previous_log_lines(circular_buffer, origin_line),
                    10
                )
            )

        # now that we're done processing this line, add it to the buffer
        circular_buffer.append(line)
    return log_lines


def parse_gzipped_file(zipped_filename):
    """
        Opens the gzipped file given by L{zipped_filename} and calls L{parse} on it

        Raises an assert if the filename doesn't match that of a gzipped file.
    """
    assert zipped_filename.endswith('.gz')
    with gzip.open(zipped_filename, 'r') as f:
        parse(f)


def main():
    start_time = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='filename to parse')
    args = parser.parse_args()
    filename = args.filename

    print "running with %s" % filename
    parse_gzipped_file(filename)
    print 'program executed in %s' % datetime.timedelta(seconds=time.time() - start_time)

if __name__ == "__main__":
    main()
