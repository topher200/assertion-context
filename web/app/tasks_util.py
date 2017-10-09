import requests


def invalidate_cache(cache=None):
    """
        Call the server and invalidate a cache.

        If None, invalidate all caches
    """
    if cache is None:
        cache = ''
    requests.put('http://nginx/api/invalidate_cache/%s' % cache)
