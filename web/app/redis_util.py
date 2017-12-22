import logging

import dogpile.cache

from instance import config


logger = logging.getLogger()


def make_dogpile_region(key_mangler_func):
    if not config.USE_DOGPILE_CACHE:
        dogpile_region = dogpile.cache.make_region().configure('dogpile.cache.null')
        logger.info("dogpile cache turned off")
        return dogpile_region

    dogpile_region = dogpile.cache.make_region(
        key_mangler=key_mangler_func
    ).configure(
        'dogpile.cache.redis',
        expiration_time=60*60*2,  # 2 hours
        arguments={
            'host': config.REDIS_ADDRESS,
        }
    )
    dogpile_region.get('confirm_redis_connection')
    logger.info("using dogpile cache from redis at %s", config.REDIS_ADDRESS)
    return dogpile_region
