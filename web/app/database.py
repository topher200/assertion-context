"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of FlaskElasticsearch
"""
from .logline import LogLine
from .papertrail_traceback import PapertrailTraceback

LOGLINE_INDEX = 'parsed-loglines'
LOGLINE_DOC_TYPE = 'logline'
TRACEBACK_INDEX = 'traceback-index'
TRACEBACK_DOC_TYPE = 'traceback'


def save_log_line(es, log_line):
    """
        Takes a L{LogLine} and saves it to the database

        Returns True if successful
    """
    assert isinstance(log_line, LogLine), (type(log_line), log_line)
    doc = log_line.document()
    return es.index(
        index=LOGLINE_INDEX,
        doc_type=LOGLINE_DOC_TYPE,
        id=log_line.papertrail_id,
        body=doc
    )

def save_papertrail_traceback(es, traceback_):
    """
        Takes a L{PapertrailTraceback} and saves it to the database

        Returns True if successful
    """
    assert isinstance(traceback_, PapertrailTraceback), (type(traceback_), traceback_)
    doc = traceback_.document()
    return es.index(
        index=TRACEBACK_INDEX,
        doc_type=TRACEBACK_DOC_TYPE,
        id=traceback_.papertrail_id,
        body=doc
    )


def refresh(es):
    """
        Performs an ES refresh on LogLine index.

        Required to see newly-inserted values when searching
    """
    es.indices.refresh(
        index=LOGLINE_INDEX
    )

def get_loglines(es, start_date=None, end_date=None, line_numbers=None):
    """
        Queries the database for the loglines from a given date range with the given line numbers.

        Both dates are inclusive.

        All filtering params are optional. Any params that are None are ignored.

        Params:
        - start_date: must be a datetime.date
        - end_date: must be a datetime.date
        - line_numbers: must be a list of ints

        Only returns loglines whose line_numbers match the given list.
    """
    params_list = []
    if start_date is not None:
        params_list.append(
            {
                "range": {
                    "timestamp": {
                        "gte": "%s||/d" % start_date,
                    }
                }
            }
        )
    if end_date is not None:
        params_list.append(
            {
                "range": {
                    "timestamp": {
                        "lte": "%s||/d" % end_date,
                    }
                }
            }
        )
    if line_numbers is not None:
        params_list.append(
            {
                "terms": {
                    "line_number": line_numbers
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
        index=LOGLINE_INDEX,
        doc_type=LOGLINE_DOC_TYPE,
        body=body
    )
    return res['hits']['hits']


def get_unique_origin_ids(es):
    """
        Returns a generator of unique papertrail_origin_id

        @rtype: GeneratorType
        @postcondition: isinstance(v, int) for v in return
    """
    query = {
        "size": 10000,
        "aggs": {
            "distinct_origin_papertrail_ids": {
                "terms": {
                    "field": "origin_papertrail_id"
                }
            }
        }
    }

    # TODO(topher): this returns way more data than we need, like the _source of the loglines we're
    # requesting data on. make it return less
    res = es.search(
        index=LOGLINE_INDEX,
        doc_type=LOGLINE_DOC_TYPE,
        body=query,
        size=10000,
    )

    # make sure we're not getting too many hits
    assert res['hits']['total'] < 9995, res

    # make sure we didn't miss any
    assert res['aggregations']['distinct_origin_papertrail_ids']['sum_other_doc_count'] == 0, (
        res['aggregations']['distinct_origin_papertrail_ids']['sum_other_doc_count'],
    )

    for r in res['aggregations']['distinct_origin_papertrail_ids']['buckets']:
        yield int(r['key'])

    # so this approach doesn't seem to be working. it's not clear how to get back a huge number of
    # buckets from an aggregation using elasticsearch-py. in addition, we will need to download all
    # the data eventually.

    # new plan: get all the data, and make a local data store (hash table) for each traceback.
    # contruct it in python and upload
