import healthcheck
from elasticsearch import Elasticsearch
import certifi
import redis

from . import api_aservice


def add_healthcheck_endpoint(app, ES, REDIS):
    health = healthcheck.HealthCheck(app, "/healthz")

    ES = Elasticsearch([app.config['ES_ADDRESS']], ca_certs=certifi.where())

    # use redis for our session storage (ie: server side cookies)
    REDIS = redis.StrictRedis(host=app.config['REDIS_ADDRESS'])

    def elasticsearch_available():
        ES.info()
        return True, 'elasticsearch ok'
    health.add_check(elasticsearch_available)

    def redis_available():
        REDIS.info()
        return True, 'redis ok'
    health.add_check(redis_available)

    def main_page_renders():
        res = api_aservice.render_main_page(ES, None, 0, 'No Ticket')
        if res:
            return True, 'site ok'
        else:
            return False, 'render failed'
    health.add_check(main_page_renders)

    _ = healthcheck.EnvironmentDump(app, "/environment")
