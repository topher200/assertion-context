import logging

import dogpile.cache

from . import config_util

USE_DOGPILE_CACHE = config_util.get('USE_DOGPILE_CACHE')
REDIS_ADDRESS = config_util.get('REDIS_ADDRESS')


logger = logging.getLogger()


def make_dogpile_region(key_mangler_func):
    if not USE_DOGPILE_CACHE:
        dogpile_region = dogpile.cache.make_region().configure('dogpile.cache.null')
        logger.info("dogpile cache turned off")
        return dogpile_region

    dogpile_region = dogpile.cache.make_region(
        key_mangler=key_mangler_func
    ).configure(
        'dogpile.cache.redis',
        expiration_time=60*15,  # 15 minutes
        arguments={
            'host': REDIS_ADDRESS,
            'redis_expiration_time': 60*20,  # 20 minutes
        }
    )
    logger.info("using dogpile cache from redis at %s", REDIS_ADDRESS)

    # we purposely don't check that the redis connection is available here; we let our healthcheck
    # endpoint handle that for us
    return dogpile_region
