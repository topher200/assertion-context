import datetime
import typing

from app.logline import LogLine


def num_asserts_from_date(loglines: typing.Sequence[LogLine], date_: datetime.date):
    """
        Returns the number of asserts from a given day.

        Does this by counting the number of log lines on that day. Only counts lines that are the
        have a line_number of "2", to ensure we only get one line per real assert.
    """
    count = 0
    for logline in loglines:
        if (logline.line_number == 2) and (logline.timestamp.date() == date_):
            count += 1
    return count
