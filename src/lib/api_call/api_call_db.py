"""
    Utility functions for performing actions on our api call ES database.

    For all functions, `es` must be an instance of Elasticsearch
"""
import collections
import logging

import elasticsearch
import elasticsearch.helpers

from common_util import retry


INDEX_TEMPLATE = 'api-call-%04d-%02d'
"""
    Template for our index name.

    Takes the form api-call-YEAR-MONTH where YEAR is a 4 digit number and MONTH is 2
"""
DOC_TYPE = 'api-call'

logger = logging.getLogger()


@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,
                         elasticsearch.ElasticsearchException))
def save(es, api_calls):
    """
        Takes an iterable of L{ApiCall} and saves them to the database

        Returns True if successful
    """
    assert isinstance(api_calls, collections.Iterable), (type(api_calls), api_calls)
    elasticsearch.helpers.bulk(es, _create_documents(api_calls))
    return True


def _create_documents(api_calls):
    for api_call in api_calls:
        index_name = INDEX_TEMPLATE % (api_call.timestamp.year, api_call.timestamp.month)
        yield {
            "_index": index_name,
            "_type": DOC_TYPE,
            "_id": api_call.papertrail_id,
            "_source": api_call.document()
        }
