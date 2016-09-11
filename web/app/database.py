"""
    Utility functions for performing actions on our ES database.

    For all functions, `es` must be an instance of FlaskElasticsearch
"""
import datetime

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

def num_asserts_per_day(es, date_):
    """
        Queries the database for number of asserts in a given day.

        Does this by counting the number of log lines on that day. Only counts lines that are the
        "origin" line.

        Takes date_, a datetime.date
    """
    assert isinstance(date_, datetime.date), (type(date_), date_)
    query = {
        "query": {
            "range": {
                "timestamp": {
                    "gte": "%s||/d" % date_,
                    "lt": "%s||+1d/d" % date_,
                }
            }
        }
    }
    res = es.search(
        index=INDEX,
        doc_type=DOC_TYPE,
        body=query
    )
    return res['hits']['total']
