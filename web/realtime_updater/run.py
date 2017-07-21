import logging
import os
import subprocess

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

from instance import config

# set up database
ES = Elasticsearch([config.ES_ADDRESS])

logger = logging.getLogger()


def main():
    setup_logging()

    # start a processes with 'papertrail -f'
    papertrail = subprocess.Popen(
        ['papertrail', '-f', '-j'], stdout=subprocess.PIPE, encoding="utf-8"
    )
    logger.info('running realtime updater')

    # read from the stdout buffer, forever
    count = 0
    for tb in json_parser.parse_json_stream(papertrail.stdout):
        count += 1
        logger.info('found traceback. #%s', count)
        traceback_database.save_traceback(ES, tb)


def setup_logging(*_, **__):
    logging_util.setup_logging()


if __name__ == "__main__":
    main()
