from .soapy import SoapyConnectorSource


class RedPitayaSource(SoapyConnectorSource):
    def getDriver(self):
        return "redpitaya"
