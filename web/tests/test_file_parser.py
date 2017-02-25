import os
import unittest

# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position
import sys
sys.path.append(ROOT)

from app import file_parser
from app import traceback


ROOT = os.path.dirname(__file__)
TEST_FILENAME = os.path.join(ROOT, 'test_data.tsv')


class TestParse(unittest.TestCase):
    def setUp(self):
        with open(TEST_FILENAME, 'r') as f:
            self.test_data = f.readlines()

    def test_parse(self):
        """
            Check that when we parse the test data we get a generator of L{Traceback}s back
        """
        tracebacks = list(file_parser.parse(self.test_data))

        self.assertGreater(len(tracebacks), 0)
        all([self.assertIsInstance(v, traceback.Traceback) for v in tracebacks])

        for t in tracebacks:
            # check that our parsing and saving worked correctly
            self.assertNotIn('origin_papertrail_id', t.text)
