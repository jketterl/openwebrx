from .soapy import SoapyConnectorSource


class UhdSource(SoapyConnectorSource):
    def getDriver(self):
        return "uhd"
