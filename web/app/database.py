"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of Elasticsearch
"""
from dogpile.cache import make_region
import redis

from .traceback import Traceback, generate_traceback_from_source


# if we don't see the remote (docker) redis, see if we're running locally instead
try:
    DOGPILE_REGION = make_region(
        key_mangler=lambda key: "dogpile:traceback:" + key
    ).configure(
        'dogpile.cache.redis',
        arguments={
            'host': 'redis',
            'redis_expiration_time': 60*60*2,  # 2 hours
        }
    )
    DOGPILE_REGION.get('confirm_redis_connection')
except redis.exceptions.ConnectionError:
    DOGPILE_REGION = make_region(
        key_mangler=lambda key: "dogpile:traceback:" + key
    ).configure(
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

        Invalidates the dogpile cache.

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
def get_tracebacks(es, start_date=None, end_date=None):
    """
        Queries the database for L{Traceback} from a given date range.

        Both dates are inclusive. Date filtering is done on the 'origin_timestamp' field of the
        Traceback.

        All filtering params are optional. Any params that are None are ignored.

        Returns a list (instead of a generator) so we can be cached

        Params:
        - start_date: must be a datetime.date
        - end_date: must be a datetime.date

        @rtype: list
        @postcondition: all(isinstance(v, Traceback) for v in return)
    """
    params_list = {}
    if start_date is not None:
        params_list['gte'] = "%s||/d" % start_date
    if end_date is not None:
        params_list['lte'] = "%s||/d" % end_date

    if len(params_list) > 0:
        body = {
            "query": {
                "range": {
                    "origin_timestamp": params_list
                }
            }
        }
    else:
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
