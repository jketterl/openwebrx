from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, CheckboxInput
from owrx.form.input.validator import Range
from typing import List

class SddcSoapySource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "bias_tee_hf": "UpdBiasT_HF",
                "bias_tee_vhf": "UpdBiasT_VHF"
            }
        )
        return mappings

    def getDriver(self):
        return "SDDC"

class SddcSoapyDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "BBRF103 / RX666 / RX888 (SDDC) device (via SoapySDR)"

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            CheckboxInput(
                "bias_tee_hf",
                "Enable BIAS-T for HF antenna port"
            ),
            CheckboxInput(
                "bias_tee_vhf",
                "Enable BIAS-T for VHF antenna port"
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + [
            "bias_tee_hf", "bias_tee_vhf"
        ]

    def getGainStages(self):
        return ["RF", "IF"]

    def hasAgc(self):
        return False

    def getSampleRateRanges(self) -> List[Range]:
        return [
            Range(2000000),
            Range(4000000),
            Range(8000000),
            Range(16000000),
            Range(32000000),
        ]
