"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of Elasticsearch
"""
import collections

from dogpile.cache import make_region
import redis

from .traceback import Traceback, generate_traceback_from_source


# if we don't see the remote (docker) redis, see if we're running locally instead
try:
    DOGPILE_REGION = make_region().configure(
        'dogpile.cache.redis',
        arguments={
            'host': 'redis',
            'redis_expiration_time': 60*60*2,  # 2 hours
        }
    )
    DOGPILE_REGION.get('confirm_redis_connection')
except redis.exceptions.ConnectionError:
    DOGPILE_REGION = make_region().configure(
        'dogpile.cache.redis',
        arguments={
            'host': 'localhost',
            'redis_expiration_time': 60*60*2,  # 2 hours
        }
    )
    DOGPILE_REGION.get('confirm_redis_connection')

INDEX = 'traceback-index'
DOC_TYPE = 'traceback'


def save_traceback(es, traceback):
    """
        Takes a L{Traceback} and saves it to the database

        Returns True if successful
    """
    assert isinstance(traceback, Traceback), (type(traceback), traceback)
    doc = traceback.document()
    res = es.index(
        index=INDEX,
        doc_type=DOC_TYPE,
        id=traceback.origin_papertrail_id,
        body=doc
    )
    DOGPILE_REGION.invalidate()
    return res


def refresh(es):
    """
        Performs an ES refresh. Required to see newly-inserted values when searching
    """
    es.indices.refresh(
        index=INDEX
    )


@DOGPILE_REGION.cache_on_arguments()
def get_tracebacks(es):
    """
        Queries the database for a list of L{Traceback}

        Returns a list (instead of a generator) so we can be cached

        @rtype: list
        @postcondition: all(isinstance(v, Traceback) for v in return)
    """
    body = {
        "query": {
            "match_all": {}
        }
    }

    raw_tracebacks = es.search(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=body,
        sort='origin_timestamp:desc',
        size=100
    )
    res = []
    for raw_traceback in raw_tracebacks['hits']['hits']:
        res.append(generate_traceback_from_source(raw_traceback['_source']))
    return res


@DOGPILE_REGION.cache_on_arguments()
def get_similar_tracebacks(es, traceback_text):
    """
        Queries the database for any tracebacks with identical traceback_text

        Returns a list (instead of a generator) so we can be cached

        @type traceback_text: str
        @rtype: list

        @postcondition: all(isinstance(v, Traceback) for v in return)
    """
    body = {
        "query": {
            "match_phrase": {
                "traceback_text": traceback_text
            }
        }
    }

    raw_es_response = es.search(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=body,
        sort='origin_timestamp:desc',
        size=1000
    )
    res = []
    for raw_traceback in raw_es_response['hits']['hits']:
        res.append(generate_traceback_from_source(raw_traceback['_source']))
    return res
