"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of FlaskElasticsearch
"""
from .logline import LogLine, generate_logline_from_source

INDEX = 'logline-index'
DOC_TYPE = 'logline'


def save_log_line(es, log_line):
    """
        Takes a L{LogLine} and saves it to the database

        Returns True if successfull
    """
    assert isinstance(log_line, LogLine), (type(log_line), log_line)
    doc = log_line.document()
    return es.index(
        index=INDEX,
        doc_type=DOC_TYPE,
        id=log_line.papertrail_id,
        body=doc
    )

def refresh(es):
    """
        Performs an ES refresh. Required to see newly-inserted values when searching
    """
    es.indices.refresh(
        index=INDEX
    )

def get_loglines(es, start_date=None, end_date=None, line_numbers=None):
    """
        Queries the database for the asserts from a given date range with the given line numbers.

        Both dates are inclusive.

        All filtering params are optional. Any params that are None are ignored.

        Params:
        - start_date: must be a datetime.date
        - end_date: must be a datetime.date
        - line_numbers: must be a list of ints

        Only returns loglines whose line_numbers match the given list.

        @rtype: generator
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
        index=INDEX,
        doc_type=DOC_TYPE,
        body=body
    )
    for raw_logline in res['hits']['hits']:
        yield generate_logline_from_source(raw_logline['_source'])
