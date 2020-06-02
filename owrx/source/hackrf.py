from .soapy import SoapyConnectorSource


class HackrfSource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update({"bias_tee": "bias_tx"})
        return mappings

    def getDriver(self):
        return "hackrf"