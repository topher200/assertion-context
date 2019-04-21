import os

from cachetools import cached


class ConfigKeyNotFound(Exception):
    """Raised if the given config key is not found"""


@cached(cache={})
def get(key):
    """
    @raises ConfigKeyNotFound if key not found
    """
    value = os.environ.get(key)
    if value is None:
        raise ConfigKeyNotFound(key)

    # If value is "true" or "false", parse as a boolean
    # Otherwise, if it contains a "." then try to parse as a float
    # Otherwise, try to parse as an integer
    # If all else fails, just keep it a string
    # stolen from https://github.com/brettlangdon/flask-env/blob/master/flask_env.py (MIT license)
    if value.lower() in ('true', 'false'):
        value = value.lower() == 'true'
    elif '.' in value:
        try:
            value = float(value)
        except ValueError:
            pass
    else:
        try:
            value = int(value)
        except ValueError:
            pass

    return value
