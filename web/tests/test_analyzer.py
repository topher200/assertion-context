import datetime
import os
import unittest

# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import analyzer
from app import logline


class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.log_line0 = logline.LogLine(
            'AssertionError\n',
            '700594297938165774\t2016-08-12T03:18:39\t2016-08-12T03:18:39Z\t407484803\ti-2ee330b7\t107.21.188.48\tUser\tNotice\tmanager.debug\tAssertionError\n',  #pylint: disable=line-too-long
            datetime.datetime(2000, 8, 12, 3, 18, 39),
            '700594297938165772',
            '700594297938165770',
            0,
            'i-2ee330b7',
            'manager.debug',
        )
        self.log_line2 = logline.LogLine(
            'AssertionError\n',
            '700594297938165774\t2016-08-12T03:18:39\t2016-08-12T03:18:39Z\t407484803\ti-2ee330b7\t107.21.188.48\tUser\tNotice\tmanager.debug\tAssertionError\n',  #pylint: disable=line-too-long
            datetime.datetime(2000, 8, 12, 3, 18, 39),
            '700594297938165772',
            '700594297938165770',
            2,
            'i-2ee330b7',
            'manager.debug',
        )
        self.list_of_loglines = [self.log_line0, self.log_line2]

    def test_num_asserts_from_date(self):
        """
            Check that when analyze a list of loglines we get the correct count.
        """
        self.assertEqual(
            analyzer.num_asserts_from_date(self.list_of_loglines,
                                           self.list_of_loglines[0].timestamp.date()),
            1
        )
