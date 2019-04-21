import logging

logger = logging.getLogger()


__LINE_FORMATTER = logging.Formatter(
    '%(asctime)s.%(msecs)03d %(process)d/%(threadName)-40s: %(levelname)-8s %(name)s: %(message)s',
    '%d/%b/%Y:%H:%M:%S')


def setup_logging(log_file):
    logger.setLevel(logging.DEBUG)

    # add log handler to sys.stderr
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(__LINE_FORMATTER)
    logger.addHandler(stream_handler)

    # output logs to file
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(__LINE_FORMATTER)
    logger.addHandler(file_handler)

    logger.debug('logger configured')
