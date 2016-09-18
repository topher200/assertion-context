"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of FlaskElasticsearch
"""
import datetime
from typing import Sequence

from .logline import LogLine

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

def get_loglines(
        es,
        start_date: datetime.date,
        end_date: datetime.date,
        line_numbers: Sequence[int]
):
    """
        Queries the database for the asserts from a given date range with the given line numbers.

        Both dates are inclusive.

        Only returns loglines whose line_numbers match the given list.
    """
    query = {
        "filter": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "timestamp": {
                                "gte": "%s||/d" % start_date,
                                "lte": "%s||/d" % end_date,
                            }
                        }
                    },
                    {
                        "terms": {
                            "line_number": line_numbers
                        }
                    }
                ]
            }
        }
    }
    res = es.search(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=query
    )
    return res['hits']['hits']
