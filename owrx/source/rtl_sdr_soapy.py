from .soapy import SoapyConnectorSource


class RtlSdrSoapySource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update({"direct_sampling": "direct_samp", "bias_tee": "biastee"})
        return mappings

    def getDriver(self):
        return "rtlsdr"
