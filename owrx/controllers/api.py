from . import Controller
from owrx.feature import FeatureDetector
from owrx.details import ReceiverDetails
import json


class ApiController(Controller):
    def indexAction(self):
        data = json.dumps(FeatureDetector().feature_report())
        self.send_response(data, content_type="application/json")

    def receiverDetails(self):
        receiver_details = ReceiverDetails()
        data = json.dumps(receiver_details.__dict__())
        self.send_response(data, content_type="application/json")
