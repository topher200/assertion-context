import logging

from badcorp.util.setup_logging import setup_logging

logger = logging.getLogger()


def generate_assertions():
    setup_logging()

    try:
        empty_dict = {}
        empty_dict['non-existent-key']
    except KeyError:
        logger.exception('Raising exception')
