from . import Controller
from owrx.metrics import CounterMetric, DirectMetric, Metrics


class MetricsController(Controller):
    def indexAction(self):
        metrics = Metrics.getSharedInstance().metrics

        data = "# https://prometheus.io/docs/instrumenting/exposition_formats/\n"
        for key,metric in metrics.items():

            value = -1

            if isinstance(metric, CounterMetric):
                key += "_total"
                value = metric.getValue()["count"]
            elif isinstance(metric, DirectMetric):
                value = metric.getValue()
            else:
                raise ValueError("Unexpected metric type for metric %s" % repr(metric))

            data += "%s %s\n" % (key.replace(".", "_"), value)

        self.send_response(data, content_type="text/plain; version=0.0.4")
