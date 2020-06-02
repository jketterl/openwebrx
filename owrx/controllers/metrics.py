from . import Controller
from owrx.metrics import Metrics
import json


class MetricsController(Controller):
    def indexAction(self):
        data = json.dumps(Metrics.getSharedInstance().getMetrics())
        self.send_response(data, content_type="application/json")
