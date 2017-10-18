import datetime
import logging

import pytz


LOG_TIMEZONE = pytz.timezone('America/New_York')
"""
    Timezone in which the logs were taken

    We translate Papertrail's UTC timestamps into this timezone
"""

logger = logging.getLogger()


class ParserUtil(object):
    @staticmethod
    def parse_papertrail_log_line(raw_log_line):
        """
            Parse out interesting parts of a Papertrail log line

            Papertrail log lines take this form (I've replaced tabs with newlines):
                700594297938165774
                2016-08-12T03:18:39 OR 2017-07-21T01:00:12-04:00
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
                - the "formatted line", which is how papertrail displays the log line to the user.
                if you were to copy/paste the line out of papertrail, this is what you'd get

            In addition to parsing out the text for every field, we convert the timestamp field to
            a L{datetime}. If a timezone is not given, we assume UTC (the default for Papertrail's
            archives).

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

        # handle the timestamp, whether it includes a timezone or not
        timestamp_ignoring_timezone = datetime.datetime.strptime(
            timestamp_string[:19], '%Y-%m-%dT%H:%M:%S'
        )
        timezone_string = timestamp_string[19:]
        if timezone_string == '':
            # no timezone string == UTC
            time_with_timezone = timestamp_ignoring_timezone.replace(tzinfo=pytz.UTC)
        elif timezone_string == '-04:00':
            time_with_timezone = pytz.timezone('America/New_York').localize(timestamp_ignoring_timezone)
        else:
            logger.error('unknown timezone string "%s". %s', timezone_string, timestamp_string)
            assert False, locals()
        timestamp_with_tz = time_with_timezone.astimezone(LOG_TIMEZONE)

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
