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

        import operator
        print ''.join(
            ['%s: %s' % (l.line_number, l.parsed_log_message,)
             for l in sorted(
                 log_lines,
                 key=operator.attrgetter('origin_papertrail_id', 'line_number', ),
                 reverse=True,
             )
            ]
        )
        self.assertGreater(len(log_lines), 0)
        all([self.assertIsInstance(v, main.LogLine) for v in log_lines])


if __name__ == "__main__":
    unittest.main()
