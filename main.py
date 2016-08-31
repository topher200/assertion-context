# Take a filename
# Confirm that the file is zipped
# Unzip that file and read from it
# Check each line of the file for AssertionError
# When AssertionError is found, determine the instance ID of the offending line
# Search backwards in the logs for the previous lines from that instance ID
# Parse out the tracebacks from those error lines

import argparse
import datetime
import gzip
import time


def parse_log_line(log_line):
    """
        Parse out interesting parts of the log line.

        Log lines take this form:
            700594297938165774	2016-08-12T03:18:39	2016-08-12T03:18:39Z	407484803	i-2ee330b7	107.21.188.48	User	Notice	manager.debug	AssertionError
        The separator for a log line is the tab charactor.

        We parse out the following parts:
            - the log line id, the 1st column
            - the instance id, the 5th column
            - the running program name, the 9th column
            - the actual message, which is everything after the 9th column

        Returns a 4-tuple of the above parts
    """
    log_line_pieces = log_line.split('\t', 9)
    assert len(log_line_pieces) == 10, log_line_pieces
    log_line_id = log_line_pieces[0]
    instance_id = log_line_pieces[4]
    program_name = log_line_pieces[8]
    message = log_line_pieces[9]

    return (log_line_id, instance_id, program_name, message)


def parse(zipped_filename):
    with gzip.open(zipped_filename, 'r') as f:
        import collections
        # We use a circular buffer to keep track of the last few lines. When we find an
        # AssertionError, we search backwards in the log lines to find the lines previous from that
        # machine
        circular_buffer = collections.deque(maxlen=10000)
        for line in f:
            # see if this line has an important error
            if 'AssertionError' in line:
                # it does! what machine did it happen on?
                log_line_id, instance_id, program_name, assertion_error = parse_log_line(line)
                print log_line_id, instance_id, program_name, assertion_error

                # search backwards on that machine for the previous traceback lines
                previous_lines = []
                for searching_line in list(circular_buffer)[::-1]:
                    (_,
                     searching_line_instance_id,
                     searching_line_program_name,
                     context_line) = parse_log_line(searching_line)
                    if ((searching_line_instance_id == instance_id) and
                        (searching_line_program_name == program_name)):
                        previous_lines.append(context_line)
                        if len(previous_lines) >= 10:
                            break
                print ''.join(previous_lines[::-1])

            # now that we're done processing this line, add it to the buffer
            circular_buffer.append(line)


def main():
    start_time = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='filename to parse')
    args = parser.parse_args()
    filename = args.filename

    print "running with %s" % filename

    assert filename.endswith('.gz')
    parse(filename)

    # with open(filename, 'r') as f:
    #     i = 0
    #     for line in f:
    #         print line
    #         i += 1
    #         if i == 100:
    #             break
    #         if 'AssertionError' in line:
    #             print line

    print 'program executed in %s' % datetime.timedelta(seconds=time.time() - start_time)

if __name__ == "__main__":
    main()
