import healthcheck
from elasticsearch import Elasticsearch
import certifi
import redis


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

    _ = healthcheck.EnvironmentDump(app, "/environment")
