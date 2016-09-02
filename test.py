import unittest

import main


TEST_FILENAME = 'test_data.tsv'


class TestParse(unittest.TestCase):
    def setUp(self):
        with open(TEST_FILENAME, 'r') as f:
            self.test_data = f.readlines()

    def test_parse(self):
        """
            Check that when we parse the test data we get a list of L{LogLine}s back
        """
        log_lines = main.parse(self.test_data)

        self.assertGreater(len(log_lines), 0)
        all([self.assertIsInstance(v, main.LogLine) for v in log_lines])


if __name__ == "__main__":
    unittest.main()
