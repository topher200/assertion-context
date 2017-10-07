import datetime
import logging
import os
import subprocess
import tempfile

from elasticsearch import Elasticsearch

# We hack the sys path so our script can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import (
    json_parser,
    logging_util,
    traceback_database
)
from realtime_updater import time_util

from instance import config

# set up database
ES = Elasticsearch([config.ES_ADDRESS])

logger = logging.getLogger()


def main():
    setup_logging()
    start_time, end_time = __get_times()
    logger.info('getting logs from %s -> %s', start_time, end_time)

    # fill a log file with papertrail output
    with tempfile.NamedTemporaryFile('wb') as local_file:
        papertrail = subprocess.run(
            ['/usr/local/bin/papertrail', '--min-time', str(start_time), '--max-time', str(end_time), '-j'],
            stdout=local_file,
            encoding="utf-8"
        )

        count = 0
        for tb in json_parser.parse_json_file(local_file.name):
            count += 1
            logger.info('found traceback. #%s', count)
            traceback_database.save_traceback(ES, tb)

    logger.info('done with logs from %s -> %s', start_time, end_time)


def setup_logging(*_, **__):
    logging_util.setup_logging()


def __get_times():
    now = datetime.datetime.now()
    # lag behind by 5 minutes
    end_time = time_util.round_time(now - datetime.timedelta(minutes=5))
    # 1 minutes worth of data at a time
    start_time = end_time - datetime.timedelta(minutes=1)
    return (start_time, end_time)


if __name__ == '__main__':
    main()
