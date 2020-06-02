from .soapy import SoapyConnectorSource


class SdrplaySource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "bias_tee": "biasT_ctrl",
                "rf_notch": "rfnotch_ctrl",
                "dab_notch": "dabnotch_ctrl",
                "if_mode": "if_mode",
            }
        )
        return mappings

    def getDriver(self):
        return "sdrplay"
