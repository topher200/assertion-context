import logging
from logging.handlers import SysLogHandler

from common.util import config


__PAPERTRAIL_URL = config.get('PAPERTRAIL_URL')
__PAPERTRAIL_PORT = config.get('PAPERTRAIL_PORT')


def setup_logging():
    # from https://help.papertrailapp.com/kb/configuration/configuring-centralized-logging-from-python-apps/#generic-python-app
    syslog = SysLogHandler(address=(__PAPERTRAIL_URL, __PAPERTRAIL_PORT))

    format = '%(asctime)s %(hostname)s YOUR_APP: %(message)s'
    formatter = logging.Formatter(format, datefmt='%b %d %H:%M:%S')
    syslog.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(syslog)
    logger.setLevel(logging.INFO)
