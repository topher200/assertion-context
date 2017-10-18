"""
    Utility functions for performing actions on our api call ES database.

    For all functions, `es` must be an instance of Elasticsearch
"""
import dogpile.cache
import elasticsearch

from app import redis_util
from app import retry
from app.entities.api_call import ApiCall


DOGPILE_REGION = redis_util.make_dogpile_region(
    lambda key: (
        "dogpile:api_call:%s" %
        dogpile.cache.util.sha1_mangle_key(key.encode('utf-8'))
    )
)

INDEX = 'api-call-index'
DOC_TYPE = 'api-call'


@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,))
def save(es, api_call):
    """
        Takes a L{ApiCall} and saves it to the database

        Invalidates the dogpile cache.

        Returns True if successful
    """
    assert isinstance(api_call, ApiCall), (type(api_call), api_call)
    doc = api_call.document()
    res = es.index(
        index=INDEX,
        doc_type=DOC_TYPE,
        id=api_call.papertrail_id,
        body=doc
    )
    invalidate_cache()
    return res


def invalidate_cache():
    DOGPILE_REGION.invalidate()
