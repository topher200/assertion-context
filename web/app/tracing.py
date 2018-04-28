import jaeger_client
from opentracing_instrumentation.client_hooks import install_all_patches


TRACER = None


def initialize_tracer():
    install_all_patches()

    config = jaeger_client.Config(
        config = {
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
        },
        service_name='tracebacks'
    )

    global TRACER
    TRACER = config.initialize_tracer() # also sets opentracing.tracer
    return TRACER

def get_tracer():
    global TRACER
    if TRACER is None:
        initialize_tracer()
    return TRACER
