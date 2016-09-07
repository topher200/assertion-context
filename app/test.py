import os
import unittest

import file_parser


ROOT = os.path.dirname(__file__)
TEST_FILENAME = os.path.join(ROOT, 'test_data.tsv')


class TestParse(unittest.TestCase):
    def setUp(self):
        with open(TEST_FILENAME, 'r') as f:
            self.test_data = f.readlines()

    def test_parse(self):
        """
            Check that when we parse the test data we get a list of L{LogLine}s back
        """
        log_lines = file_parser.parse(self.test_data)

        self.assertGreater(len(log_lines), 0)
        all([self.assertIsInstance(v, file_parser.LogLine) for v in log_lines])


if __name__ == "__main__":
    unittest.main()
