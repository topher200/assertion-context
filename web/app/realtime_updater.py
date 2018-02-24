import datetime
import logging
import math
import os
import subprocess
import tempfile
import time

# We hack the sys path so our script can see the app directory
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#pylint: disable=wrong-import-position,wrong-import-order
import sys
sys.path.append(ROOT)

from app import (
    json_parser,
    tasks,
    tasks_util,
    traceback_database,
    time_util,
)
from app.ddl import api_call_db


logger = logging.getLogger()


def enqueue(end_time):
    """ add a realtime_update job to the queue """
    assert end_time is None or isinstance(end_time, datetime.datetime), end_time

    start_time, end_time = __get_times(end_time)
    logger.info('queueing realtime updater for logs from %s -> %s', start_time, end_time)
    tasks.realtime_update.delay(start_time, end_time)


def run(ES, start_time, end_time):
    """ run the realtime updater for the given times """
    assert isinstance(start_time, str), (type(start_time), start_time)
    assert isinstance(end_time, str), (type(end_time), end_time)

    # fill a log file with papertrail output. retry on failures
    for i in range(10):
        local_file = __call_papertrail_cli(start_time, end_time)
        if local_file is not None:
            break
        time.sleep(math.pow(2, i))  # increasing backoff
    if local_file is None:
        logger.warning('papertrail cli failed. %s -> %s', start_time, end_time)
        return

    tracebacks, api_calls = json_parser.parse_json_file(local_file.name)
    count = 0
    for tb in tracebacks:
        count += 1
        traceback_database.save_traceback(ES, tb)
    logger.info("saved %s tracebacks", count)

    if count > 0:
        logger.info('invalidating traceback cache')
        tasks_util.invalidate_cache('traceback')

    if api_calls:
        logger.info('saving %s api calls', len(api_calls))
        api_call_db.save(ES, api_calls)
    else:
        logger.info('no api calls found. %s to %s', start_time, end_time)

    logger.info('done with logs from %s -> %s', start_time, end_time)


def __call_papertrail_cli(start_time, end_time):
    local_file = tempfile.NamedTemporaryFile('wb')
    res = subprocess.run(
        # Note: this expects that the env var PAPERTRAIL_API_TOKEN is populated
        ['/usr/local/bin/papertrail', '--min-time', str(start_time), '--max-time', str(end_time), '-j'],
        stdout=local_file,
        stderr=subprocess.PIPE,
        encoding="utf-8"
    )

    if res.stderr:
        # some error occured
        try:
            logger.info('subprocess failed. err: %s', res.stderr.split('\n')[0])
        except Exception:
            logger.error('subprocess failed. could not parse error logs. %s', res.stderr)
        logger.debug('subprocess failed. full err: %s', res.stderr)
        return None

    return local_file


def __get_times(end_time=None):
    if end_time is None:
        now = datetime.datetime.now()
        # lag behind by a minute
        end_time = time_util.round_time(now - datetime.timedelta(minutes=1))

    # 1 minute worth of data at a time
    start_time = end_time - datetime.timedelta(minutes=1)

    # papertrail's --max-time uses inclusive times, take a second off
    end_time = end_time - datetime.timedelta(seconds=1)

    return (start_time, end_time)
