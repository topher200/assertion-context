import datetime
import os
import unittest

from elasticsearch import Elasticsearch

# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import database
from app import logline


class TestElasticSearch(unittest.TestCase):
    def setUp(self):
        self.es = Elasticsearch("localhost:9200")
        self.log_line = logline.LogLine(
            'AssertionError\n',
            '700594297938165774\t2016-08-12T03:18:39\t2016-08-12T03:18:39Z\t407484803\ti-2ee330b7\t107.21.188.48\tUser\tNotice\tmanager.debug\tAssertionError\n',  #pylint: disable=line-too-long
            datetime.datetime(2000, 8, 12, 3, 18, 39),
            '700594297938165774',
            '700594297938165774',
            0,
            'i-2ee330b7',
            'manager.debug',
        )

    def tearDown(self):
        self.es.delete(
            index=database.INDEX,
            doc_type=database.DOC_TYPE,
            id=self.log_line.papertrail_id,
        )

    def test_save_log_line(self):
        self.assertTrue(database.save_log_line(self.es, self.log_line))
        self.assertTrue(
            self.es.exists(
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.log_line.papertrail_id,
                params={
                    'refresh': True,
                }
            )
        )

    def test_num_asserts_per_day(self):
        """
            Check that when we search for our new log line we find it.
        """
        # save the new line
        self.assertTrue(database.save_log_line(self.es, self.log_line))
        database.refresh(self.es)

        # test that it exists
        self.assertEqual(
            database.num_asserts_per_day(self.es, self.log_line.timestamp.date()),
            1
        )
