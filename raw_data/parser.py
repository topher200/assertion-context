"""
    Used for loading all records from a database, parsing them, then saving them back to the
    database in a new index.
"""
from elasticsearch import Elasticsearch

IP = 'localhost'
IP = 'http://ec2-54-237-247-170.compute-1.amazonaws.com/'
es = Elasticsearch(IP)
INDEX = 'logline-index'
DOC_TYPE = 'logline'
NEW_INDEX = 'parsed-loglines'

res = es.search(
    index=INDEX,
    size=10000,
    body={
        "query": {
            "match": {
                "line_number": 0
            }
        }
    },
)

# We hack the sys path so our tester can see the app directory
#pylint: disable=wrong-import-position,wrong-import-order
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.append(ROOT)

from web.app import file_parser

ids = []
for hit in res['hits']['hits']:
    log_line = hit['_source']['parsed_log_message']
    if file_parser.log_line_contains_important_error(log_line):
        # save the doc to the new index
        source = hit['_source']
        id = source['origin_papertrail_id']
        ids.append(id)


res = es.search(
    index=INDEX,
    size=100000,
    body={
        "query": {
            "match_all": {
            }
        }
    },
)

print(len(res['hits']['hits']))

counter = 0
for hit in res['hits']['hits']:
    source = hit['_source']
    if source['origin_papertrail_id'] in ids:
        es.index(
            index=NEW_INDEX,
            doc_type=DOC_TYPE,
            id=source['papertrail_id'],
            body=source
        )
        counter += 1
        if counter % 100 == 0:
            print(counter)

print('saved %s docs' % counter)
