import os
import unittest


# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app.file_parser import Parser


LOG_LINES_THAT_SHOULD_MATCH = [
    '\nAssertionError',
    '\nAssertionError: join a child process',
    '\nKeyError: i broke it',
    '\nKeyError',
    '\nNotImplementedError',
    '\nNotImplementedError: sdf',
    '\nValueError',
    '\nValueError: sdf',
]

LOG_LINES_THAT_SHOULD_NOT_MATCH = [
    '',
    'asdf details = AssertionError fdsa',
    '\nAssertionError: can only join a child process',
    '\nKeyError: threading.pyc',
    '\nKeyError: args:[',
    '\nValueE',
]

class TestAssertionRegex(unittest.TestCase):
    def test_lines_that_should_match(self):
        """
            When we give our regex checker a line that should match, it matches
        """
        for line in LOG_LINES_THAT_SHOULD_MATCH:
            self.assertTrue(Parser.log_line_contains_important_error(line), line)

    def test_lines_that_should_not_match(self):
        """
            When we give our regex checker a line that shouldn't match, it doesn't match
        """
        for line in LOG_LINES_THAT_SHOULD_NOT_MATCH:
            self.assertFalse(Parser.log_line_contains_important_error(line), line)
