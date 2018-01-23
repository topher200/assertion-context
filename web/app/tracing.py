import jaeger_client


def initialize_tracer():
    config = jaeger_client.Config(
        config = {
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
            'local_agent': {'reporting_host': 'jaeger'},
        },
        service_name='hello-world'
    )

    return config.initialize_tracer() # also sets opentracing.tracer
