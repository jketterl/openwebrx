from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import Input, CheckboxInput
from owrx.form.input.device import BiasTeeInput
from owrx.form.input.validator import Range
from typing import List

# case sensitive, be careful changing it
class HydrasdrSource(SoapyConnectorSource):
    def getSoapySettingsMappings(self):
        mappings = super().getSoapySettingsMappings()
        mappings.update(
            {
                "bias_tee": "biastee",
                "bitpack": "bitpack",
            }
        )
        return mappings

    def getDriver(self):
        return "hydrasdr"


class HydrasdrDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "HydraSDR RFone"

    def supportsPpm(self):
        # not supported by the device API
        # frequency calibration can be done with separate tools and will be persisted on the device.
        # see discussion here: https://groups.io/g/openwebrx/topic/79360293
        return False

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [
            BiasTeeInput(),
            CheckboxInput(
                "bitpack",
                "Enable bit-packing",
                infotext="Packs two 12-bit samples into 3 bytes."
                + " Lowers USB bandwidth consumption, increases CPU load",
            ),
        ]

    def getDeviceOptionalKeys(self):
        return super().getDeviceOptionalKeys() + ["bias_tee", "bitpack"]

    def getProfileOptionalKeys(self):
        return super().getProfileOptionalKeys() + ["bias_tee"]

    def getGainStages(self):
        return ["LNA", "MIX", "VGA"]

    def getSampleRateRanges(self) -> List[Range]:
        # Device only supports 2.5, 5, and 10 MSPS for now, mfg suggests it may
        # be able to do up to 80 MSPS "with custom firmware"
        return [
            Range(2500000),
            Range(5000000),
            Range(10000000),
        ]
