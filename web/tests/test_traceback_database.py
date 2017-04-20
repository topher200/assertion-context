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

from app import traceback_database
from app import traceback
from instance.config import ES_ADDRESS


class TestElasticSearch(unittest.TestCase):
    def setUp(self):
        self.es = Elasticsearch(ES_ADDRESS, use_ssl=True)
        self.traceback_0 = traceback.Traceback(
            'File "/opt/wordstream/engine/rest_api/services/bing/DeprecatedBingDownloadAccountChangesService.py", line 81, in download_account_changes\nAssertionError\n',
            'File "/opt/wordstream/engine/rest_api/services/bing/DeprecatedBingDownloadAccountChangesService.py", line 81, in download_account_changes\nAssertionError\n',
            '700594297938165770',
            datetime.datetime(2000, 8, 12, 3, 18, 00),
            'i-2ee330b0',
            'manager.debug',
        )
        self.traceback_1 = traceback.Traceback(
            'File "/opt/wordstream/engine/rest_api/handlers/bing/BingDownloadAccountChangesHandler.py", line 93, in _do_post\nAssertionError\n',
            'File "/opt/wordstream/engine/rest_api/handlers/bing/BingDownloadAccountChangesHandler.py", line 93, in _do_post\nAssertionError\n',
            '700594297938165771',
            datetime.datetime(2000, 8, 12, 3, 18, 1),
            'i-2ee330b1',
            'server.debug',
        )

    def tearDown(self):
        # Clean up any created tracebacks after each test
        try:
            self.es.delete(
                index=traceback_database.INDEX,
                doc_type=traceback_database.DOC_TYPE,
                id=self.traceback_0.origin_papertrail_id,
            )
        except NotFoundError:
            pass
        try:
            self.es.delete(
                index=traceback_database.INDEX,
                doc_type=traceback_database.DOC_TYPE,
                id=self.traceback_1.origin_papertrail_id,
            )
        except NotFoundError:
            pass

    def test_save_traceback(self):
        self.assertTrue(traceback_database.save_traceback(self.es, self.traceback_0))
        self.assertTrue(
            self.es.exists(
                index=traceback_database.INDEX,
                doc_type=traceback_database.DOC_TYPE,
                id=self.traceback_0.origin_papertrail_id,
                params={
                    'refresh': True,
                }
            )
        )

    def test_get_tracebacks_from_date_range(self):
        """
            Check that when we search for our new tracebacks we find them.
        """
        # save the tracebacks
        self.assertTrue(traceback_database.save_traceback(self.es, self.traceback_0))
        self.assertTrue(traceback_database.save_traceback(self.es, self.traceback_1))
        traceback_database.refresh(self.es)

        # test that we find them all. assumes that the timestamps are from the same day.
        tracebacks = traceback_database.get_tracebacks(
            self.es,
            self.traceback_0.origin_timestamp.date(),
            self.traceback_0.origin_timestamp.date(),
        )
        self.assertEqual(len(list(tracebacks)), 2)

    def test_get_tracebacks_no_params(self):
        """
            Check that when we search for all tracebacks, we find many
        """
        # save the new tracebacks
        self.assertTrue(traceback_database.save_traceback(self.es, self.traceback_0))
        self.assertTrue(traceback_database.save_traceback(self.es, self.traceback_1))
        traceback_database.refresh(self.es)

        tracebacks = traceback_database.get_tracebacks(
            self.es,
        )
        self.assertGreaterEqual(len(list(tracebacks)), 2)
