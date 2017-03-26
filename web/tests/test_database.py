import datetime
import os
import unittest

import certifi

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# We hack the sys path so our tester can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import database
from app import traceback


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT_DIR, '.es_credentials')) as f:
    ES_ADDRESS = str.strip(f.readline())


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
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.traceback_0.origin_papertrail_id,
            )
        except NotFoundError:
            pass
        try:
            self.es.delete(
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.traceback_1.origin_papertrail_id,
            )
        except NotFoundError:
            pass

    def test_save_traceback(self):
        self.assertTrue(database.save_traceback(self.es, self.traceback_0))
        self.assertTrue(
            self.es.exists(
                index=database.INDEX,
                doc_type=database.DOC_TYPE,
                id=self.traceback_0.origin_papertrail_id,
                params={
                    'refresh': True,
                }
            )
        )

    def test_get_tracebacks_no_params(self):
        """
            Check that when we search for all tracebacks, we find many
        """
        # save the new tracebacks
        self.assertTrue(database.save_traceback(self.es, self.traceback_0))
        self.assertTrue(database.save_traceback(self.es, self.traceback_1))
        database.refresh(self.es)

        tracebacks = database.get_tracebacks(
            self.es,
        )
        self.assertGreaterEqual(len(list(tracebacks)), 2)
