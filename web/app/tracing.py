from opentracing_instrumentation.client_hooks import install_all_patches
import jaeger_client
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory

from . import config_util

JAEGER_REPORTING_HOST = config_util.get('JAEGER_REPORTING_HOST')


def initialize_tracer():
    install_all_patches()

    config = jaeger_client.Config(
        config = {
            'sampler': {'type': 'const', 'param': 1},
            'logging': False,
            'local_agent': {
                'reporting_host': JAEGER_REPORTING_HOST,
            }
        },
        service_name='tracebacks',
        validate=True,
        metrics_factory=PrometheusMetricsFactory(namespace='tracebacks'),
    )

    return config.initialize_tracer() # also sets opentracing.tracer
