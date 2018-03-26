import jaeger_client


def initialize_tracer():
    config = jaeger_client.Config(
        config = {
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
        },
        service_name='tracebacks'
    )

    return config.initialize_tracer() # also sets opentracing.tracer
