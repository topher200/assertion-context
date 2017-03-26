"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of FlaskElasticsearch
"""
import collections

from dogpile.cache import make_region

from .traceback import Traceback, generate_traceback_from_source


DOGPILE_REGION = make_region().configure(
    'dogpile.cache.redis',
    arguments={
        'host': 'redis',
        'redis_expiration_time': 60*60*2,  # 2 hours
    }
)


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
def get_tracebacks(es, start_date=None, end_date=None):
    """
        Queries the database for L{Traceback} from a given date range.

        Both dates are inclusive. Date filtering is done on the 'origin_timestamp' field of the
        Traceback.

        All filtering params are optional. Any params that are None are ignored.

        Params:
        - start_date: must be a datetime.date
        - end_date: must be a datetime.date

        @rtype: generator
        @postcondition: all(isinstance(v, Traceback) for v in return)
    """
    params_list = []
    if start_date is not None:
        params_list.append(
            {
                "range": {
                    "origin_timestamp": {
                        "gte": "%s||/d" % start_date,
                    }
                }
            }
        )
    if end_date is not None:
        params_list.append(
            {
                "range": {
                    "origin_timestamp": {
                        "lte": "%s||/d" % end_date,
                    }
                }
            }
        )

    if len(params_list) > 0:
        body = {
            "filter": {
                "bool": {
                    "must": params_list
                }
            }
        }
    else:
        body = {
            "query": {
                "match_all": {}
            }
        }

    res = es.search(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=body,
        sort='origin_timestamp:desc',
        size=100
    )
    for raw_traceback in res['hits']['hits']:
        yield generate_traceback_from_source(raw_traceback['_source'])


@DOGPILE_REGION.cache_on_arguments()
def get_similar_tracebacks(es, traceback_text):
    """
        Queries the database for any tracebacks with identical traceback_text

        @type traceback_text: str
        @rtype: generator

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
    for raw_traceback in raw_es_response['hits']['hits']:
        yield generate_traceback_from_source(raw_traceback['_source'])
