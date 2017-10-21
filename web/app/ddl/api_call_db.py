"""
    Utility functions for performing actions on our api call ES database.

    For all functions, `es` must be an instance of Elasticsearch
"""
import collections
import logging

import dogpile.cache
import elasticsearch
import elasticsearch.helpers

from app import redis_util
from app import retry


DOGPILE_REGION = redis_util.make_dogpile_region(
    lambda key: (
        "dogpile:api_call:%s" %
        dogpile.cache.util.sha1_mangle_key(key.encode('utf-8'))
    )
)

INDEX = 'api-call-index'
DOC_TYPE = 'api-call'

logger = logging.getLogger()


@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,))
def save(es, api_calls):
    """
        Takes an iterable of L{ApiCall} and saves them to the database

        Invalidates the dogpile cache.

        Returns True if successful
    """
    assert isinstance(api_calls, collections.Iterable), (type(api_calls), api_calls)
    try:
        elasticsearch.helpers.bulk(es, _create_documents(api_calls))
    except elasticsearch.ElasticsearchException:
        logger.exception('api_call bulk update failed')
        return False
    invalidate_cache()
    return True


def _create_documents(api_calls):
    for api_call in api_calls:
        yield {
            "_index": INDEX,
            "_type": DOC_TYPE,
            "_id": api_call.papertrail_id,
            "_source": api_call.document()
        }


def invalidate_cache():
    DOGPILE_REGION.invalidate()
