import logging
import logging.handlers

from . import config_util


logger = logging.getLogger()
DEBUG_LOGGING = config_util.get('DEBUG_LOGGING')


def setup_logging():
    formatter = logging.Formatter(
        (
            "[%(asctime)s] | %(levelname)s | pid%(process)d | "
            "%(pathname)s.%(funcName)s:%(lineno)d | %(message)s"
        )
    )

    # add log handler to sys.stderr
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    if DEBUG_LOGGING:
        logger.setLevel(logging.DEBUG)
        # rotating file handler with more verbosity
        handler = logging.handlers.RotatingFileHandler(
            '/var/log/flask_app.log',
            maxBytes=10000000,  # 10MB
            backupCount=10
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
    else:
        logger.setLevel(logging.INFO)

        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.WARNING)
