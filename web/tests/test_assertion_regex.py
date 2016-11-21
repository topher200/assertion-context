import os
import unittest


# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app.file_parser import log_line_contains_important_error


LOG_LINES_THAT_SHOULD_MATCH = [
    'AssertionError',
    'AssertionError: join a child process',
    'KeyError: i broke it',
    'KeyError',
    'asdf KeyError',
    'NotImplementedError',
    'NotImplementedError: sdf',
    'ValueError',
    'ValueError: sdf',
]

LOG_LINES_THAT_SHOULD_NOT_MATCH = [
    '',
    'asdf details = AssertionError',
    'AssertionError: can only join a child process',
    'KeyError: threading.pyc',
    'KeyError: args:[',
    'ValueE',
]

class TestAssertionRegex(unittest.TestCase):
    def test_lines_that_should_match(self):
        """
            When we give our regex checker a line that should match, it matches
        """
        for line in LOG_LINES_THAT_SHOULD_MATCH:
            self.assertTrue(log_line_contains_important_error(line), line)

    def test_lines_that_should_not_match(self):
        """
            When we give our regex checker a line that shouldn't match, it doesn't match
        """
        for line in LOG_LINES_THAT_SHOULD_NOT_MATCH:
            self.assertFalse(log_line_contains_important_error(line), line)
