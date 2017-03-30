import flask_login
import logging.config


LOG_CONFIG = {
    'version': 1,
    'filters': {
        'username': {
            '()': 'log.UsernameLogFilter',
        },
    },
    'formatters': {
        'standard': {
            'format': "[%(asctime)s] | %(username)s | %(levelname)s | %(pathname)s:%(lineno)d | %(funcName)s | %(message)s",
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'filters': ['username'],
            'formatter': 'standard'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level':'DEBUG',
        },
        'app': {
            'handlers': ['console'],
            'level':'DEBUG',
        },
    }
}

logging.config.dictConfig(LOG_CONFIG)
