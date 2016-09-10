import collections


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
