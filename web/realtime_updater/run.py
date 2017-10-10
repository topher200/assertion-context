import argparse
import datetime
import logging
import os
import subprocess
import tempfile
import time

from elasticsearch import Elasticsearch

# We hack the sys path so our script can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import (
    json_parser,
    logging_util,
    tasks_util,
    traceback_database,
)
from realtime_updater import time_util

from instance import config

# set up database
ES = Elasticsearch([config.ES_ADDRESS])

logger = logging.getLogger()


def main(end_time=None):
    setup_logging()
    start_time, end_time = __get_times(end_time)
    logger.info('getting logs from %s -> %s', start_time, end_time)

    # fill a log file with papertrail output. try on failures
    for i in range(10):
        local_file = call_papertrail_cli(start_time, end_time)
        if local_file is not None:
            break
        time.sleep(i * 2)  # increasing backoff
    if local_file is None:
        logger.error('papertrail cli failed. %s -> %s', start_time, end_time)
        return

    count = 0
    for tb in json_parser.parse_json_file(local_file.name):
        count += 1
        logger.info('found traceback. #%s', count)
        traceback_database.save_traceback(ES, tb)

    if count > 0:
        logger.info('invalidating traceback cache')
        tasks_util.invalidate_cache('traceback')

    logger.info('done with logs from %s -> %s', start_time, end_time)


def call_papertrail_cli(start_time, end_time):
    local_file = tempfile.NamedTemporaryFile('wb')
    res = subprocess.run(
        ['/usr/local/bin/papertrail', '--min-time', str(start_time), '--max-time', str(end_time), '-j'],
        stdout=local_file,
        stderr=subprocess.PIPE,
        encoding="utf-8"
    )

    if res.stderr:
        try:
            logger.info('subprocess failed. err: %s', res.stderr.split('\n')[0])
        except:
            logger.info('subprocess failed. could not parse error logs')
        logger.debug('subprocess failed. full err: %s', res.stderr)
        return None
    else:
        return local_file


def setup_logging(*_, **__):
    logging_util.setup_logging()


def __get_times(end_time=None):
    if end_time is None:
        now = datetime.datetime.now()
        # lag behind by 3 minutes
        end_time = time_util.round_time(now - datetime.timedelta(minutes=3))

    # 1 minute worth of data at a time
    start_time = end_time - datetime.timedelta(minutes=1)
    return (start_time, end_time)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='download papertrail logs from their api')
    parser.add_argument('--time', help='optional end time for download')
    args = parser.parse_args()
    if args.time:
        end_time_str = args.time
        end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
        main(end_time)
    else:
        main()
