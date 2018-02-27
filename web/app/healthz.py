import healthcheck

def add_healthcheck_endpoint(app, ES, REDIS):
    health = healthcheck.HealthCheck(app, "/healthz")

    def elasticsearch_available():
        ES.info()
        return True, 'elasticsearch ok'
    health.add_check(elasticsearch_available)

    def redis_available():
        REDIS.info()
        return True, 'redis ok'
    health.add_check(redis_available)

    _ = healthcheck.EnvironmentDump(app, "/environment")