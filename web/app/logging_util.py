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

    logger.setLevel(logging.INFO)
    logger.info('Setting up logging. Debug? %s', bool(DEBUG_LOGGING))

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

        # quieter library logging levels, otherwise we get spam like
        # - /usr/local/lib/python3.6/site-packages/werkzeug/_internal.py._log:88 | 172.17.0.8 - - [09/Mar/2018 23:54:52] "GET /healthz HTTP/1.0" 200 -
        # - /usr/local/lib/python3.6/site-packages/elasticsearch/connection/base.py.log_request_success:83 | GET http://elasticsearch.default.svc.cluster.local:9200/ [status:200 request:0.002s]
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('elasticsearch').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)
        logging.getLogger('boto3').setLevel(logging.WARNING)
