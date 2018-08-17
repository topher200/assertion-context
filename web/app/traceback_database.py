"""
    Utility functions for performing actions on our tracebacks ES database.

    For all functions, `es` must be an instance of Elasticsearch
"""
import logging

import elasticsearch

from opentracing_instrumentation.request_context import get_current_span

from app import es_util
from app import redis_util
from app import retry
from .traceback import Traceback, generate_traceback_from_source

logger = logging.getLogger()


DOGPILE_REGION_PREFIX = 'dogpile:traceback'
DOGPILE_REGION = redis_util.make_dogpile_region(DOGPILE_REGION_PREFIX)
def invalidate_cache():
    redis_util.force_redis_cache_invalidation(DOGPILE_REGION_PREFIX)


INDEX = 'traceback-index'
DOC_TYPE = 'traceback'


@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,))
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
    invalidate_cache()
    return res


@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,))
def refresh(es):
    """
        Performs an ES refresh. Required to see newly-inserted values when searching
    """
    es.indices.refresh(
        index=INDEX
    )


@DOGPILE_REGION.cache_on_arguments()
@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,))
def get_tracebacks(es, tracer, start_date=None, end_date=None, num_matches=100):
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
        @postcondition: len(return) <= num_matches
    """
    params_list = {}
    if start_date is not None:
        params_list['gte'] = "%s||/d" % start_date
    if end_date is not None:
        params_list['lte'] = "%s||/d" % end_date

    if params_list:
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

    root_span = get_current_span()
    with tracer.start_span('elasticsearch', child_of=root_span):
        try:
            raw_tracebacks = es.search(
                index=INDEX,
                doc_type=DOC_TYPE,
                body=body,
                sort='origin_timestamp:desc',
                size=num_matches
            )
        except elasticsearch.exceptions.NotFoundError:
            logger.warning('traceback index not found. has it been created?')
            return []
    res = []
    for raw_traceback in raw_tracebacks['hits']['hits']:
        res.append(generate_traceback_from_source(raw_traceback['_source']))
    return res


@DOGPILE_REGION.cache_on_arguments()
@retry.Retry(exceptions=(elasticsearch.exceptions.ConnectionTimeout,))
def get_matching_tracebacks(es, tracer, traceback_text, match_level, num_matches):
    """
        Queries the database for any tracebacks with identical traceback_text

        Returns a list (instead of a generator) so we can be cached. Returns up to L{num_matches}
        tracebacks

        @type traceback_text: str
        @rtype: list

        @precondition: match_level in es_util.ALL_MATCH_LEVELS
        @postcondition: all(isinstance(v, Traceback) for v in return)
        @postcondition: len(return) <= num_matches
    """
    assert match_level in es_util.ALL_MATCH_LEVELS, (match_level, es_util.ALL_MATCH_LEVELS)

    body = es_util.generate_text_match_payload(traceback_text, ["traceback_text"], match_level)

    root_span = get_current_span()
    with tracer.start_span('elasticsearch', child_of=root_span):
        raw_es_response = es.search(
            index=INDEX,
            doc_type=DOC_TYPE,
            body=body,
            sort='origin_timestamp:desc',
            size=num_matches
        )
    res = []
    for raw_traceback in raw_es_response['hits']['hits']:
        res.append(generate_traceback_from_source(raw_traceback['_source']))
    return res


def get_traceback(es, id_: int) -> Traceback:
    """ Retrieves the traceback referenced by the given ID """
    raw_es_response = es.get(
        index=INDEX,
        doc_type=DOC_TYPE,
        id=id_
    )
    return generate_traceback_from_source(raw_es_response['_source'])
