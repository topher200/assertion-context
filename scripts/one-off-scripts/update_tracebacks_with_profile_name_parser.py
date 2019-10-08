"""
    One-off script used to apply profile_name to older Tracebacks.

    Loaded all tracebacks, used our new parser to find the profile_name, and re-saved each updated
    traceback back to the database.
"""
import datetime

from elasticsearch import Elasticsearch
import certifi

from app import (
    config_util,
    profile_name_parser,
    traceback_db,
    tracing,
)


tracer = tracing.initialize_tracer()

ES_ADDRESS = config_util.get('ES_ADDRESS')
ES = Elasticsearch([ES_ADDRESS], ca_certs=certifi.where())


def main():
    for m in range(9, 12 + 1):
        for d in range(1, 31 + 1):
            try:
                date_ = datetime.date(2017, m, d)
                print('running for %s' % date_)
            except Exception:
                print('date does not exist: %s' % date_)
                continue
            tracebacks = traceback_db.get_tracebacks(
                ES, tracer, date_, date_, 10000
            )
            print('found %s tracebacks' % len(tracebacks))
            for traceback in tracebacks:
                new_traceback = profile_name_parser.parse(traceback)
                if new_traceback:
                    traceback_db.save_traceback(ES, new_traceback)


if __name__ == '__main__':
    main()
