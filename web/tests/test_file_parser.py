import datetime
import os
import unittest

# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position
import sys
sys.path.append(ROOT)

from app import file_parser
from app import logline


ROOT = os.path.dirname(__file__)
TEST_FILENAME = os.path.join(ROOT, 'test_data.tsv')


class TestParse(unittest.TestCase):
    def setUp(self):
        with open(TEST_FILENAME, 'r') as f:
            self.test_data = f.readlines()

    def test_parse(self):
        """
            Check that when we parse the test data we get a generator of L{LogLine}s back
        """
        log_lines = list(file_parser.parse(self.test_data))

        self.assertGreater(len(log_lines), 0)
        all([self.assertIsInstance(v, logline.LogLine) for v in log_lines])
        all([self.assertIsInstance(v.timestamp, datetime.datetime) for v in log_lines])
