import datetime
import os
import unittest

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import database
from app import logline

# when searching, use a number larger than the number of possible loglines for a single assert
MAX_LOG_LINES_PER_ASSERT = 10


class TestElasticSearch(unittest.TestCase):
    def setUp(self):
        self.es = Elasticsearch("localhost:9200")
        self.log_line0 = logline.LogLine(
            'AssertionError\n',
            '700594297938165774\t2016-08-12T03:18:39\t2016-08-12T03:18:39Z\t407484803\ti-2ee330b7\t107.21.188.48\tUser\tNotice\tmanager.debug\tAssertionError\n',  #pylint: disable=line-too-long
            datetime.datetime(2000, 8, 12, 3, 18, 39),
            '700594297938165770',
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

    def tearDown(self):
        # Clean up any created log lines after each test
        try:
            self.es.delete(
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.log_line0.papertrail_id,
            )
        except NotFoundError:
            pass
        try:
            self.es.delete(
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.log_line2.papertrail_id,
            )
        except NotFoundError:
            pass

    def test_save_log_line(self):
        self.assertTrue(database.save_log_line(self.es, self.log_line0))
        self.assertTrue(
            self.es.exists(
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.log_line0.papertrail_id,
                params={
                    'refresh': True,
                }
            )
        )

    def test_get_loglines(self):
        """
            Check that when we search for our new log lines we find them.
        """
        # save the new lines
        self.assertTrue(database.save_log_line(self.es, self.log_line0))
        self.assertTrue(database.save_log_line(self.es, self.log_line2))
        database.refresh(self.es)

        # test that we find them all. assumes that the timestamps are from the same day.
        log_lines = database.get_loglines(
            self.es,
            self.log_line2.timestamp.date(),
            self.log_line2.timestamp.date(),
            list(range(-1, MAX_LOG_LINES_PER_ASSERT))
        )
        self.assertEqual(len(log_lines), 2)

    def test_get_loglines_from_date_range_for_specific_lines(self):
        """
            Check that when we search for a specific line number from a day we get it.
        """
        # save the new lines
        self.assertTrue(database.save_log_line(self.es, self.log_line0))
        self.assertTrue(database.save_log_line(self.es, self.log_line2))
        database.refresh(self.es)

        # test that we find only one
        log_lines = database.get_loglines(
            self.es,
            self.log_line2.timestamp.date(),
            self.log_line2.timestamp.date(),
            [self.log_line2.line_number]
        )
        self.assertEqual(len(log_lines), 1)
