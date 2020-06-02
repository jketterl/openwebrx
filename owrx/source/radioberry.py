from .soapy import SoapyConnectorSource


class RadioberrySource(SoapyConnectorSource):
    def getDriver(self):
        return "radioberry"
