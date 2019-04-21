import logging

logger = logging.getLogger()


def setup_logging(log_file):
    logger.setLevel(logging.DEBUG)
    format = '%(asctime)s BadCorp: %(message)s'
    formatter = logging.Formatter(format, datefmt='%b %d %H:%M:%S')

    # add log handler to sys.stderr
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # output logs to file
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.debug('logger configured')
