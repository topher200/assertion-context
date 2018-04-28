from opentracing_instrumentation.client_hooks import install_all_patches
import jaeger_client


def initialize_tracer():
    install_all_patches()

    config = jaeger_client.Config(
        config = {
            'sampler': {'type': 'const', 'param': 1},
            'logging': False,
        },
        service_name='tracebacks'
    )

    return config.initialize_tracer() # also sets opentracing.tracer
