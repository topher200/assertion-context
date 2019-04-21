import logging

logger = logging.getLogger()


def generate_assertions():
    try:
        empty_dict = {}
        _ = empty_dict['non-existent-key']
    except KeyError:
        logger.exception('raising KeyError')
