from owrx.source.soapy import SoapyConnectorSource, SoapyConnectorDeviceDescription
from owrx.form.input import DropdownEnum, DropdownInput, Input, NumberInput
from owrx.form.input.validator import Range, RangeValidator
from owrx.form.input.device import GainInput
from typing import List


class FobosClockSourceOptions(DropdownEnum):
    CLOCK_SOURCE_INTERNAL = (0, "Internal")
    CLOCK_SOURCE_EXTERNAL = (1, "External 10 MHz")

    def __new__(cls, *args, **kwargs):
        value, description = args
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj

    def __str__(self):
        return self.description


class FobosLnaOptions(DropdownEnum):
    LNA_0 = (0, "0 - no gain")
    LNA_1 = (1, "1 - no gain / same as 0")
    LNA_2 = (2, "2 - 16 dB")
    LNA_3 = (3, "3 - 32 dB")

    def __new__(cls, *args, **kwargs):
        value, description = args
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj

    def __str__(self):
        return self.description


class FobosSource(SoapyConnectorSource):
    def getDriver(self):
        return "fobos"

    def getEventNames(self):
        return super().getEventNames() + ["fobos_lna", "fobos_vga"]

    def getSoapySettingsMappings(self):
        return {
            "clock_source": "clock_source",
        }

    def _buildRfGain(self, values):
        lna = values.get("fobos_lna", 0)
        vga = values.get("fobos_vga", 10)
        return "LNA={0},VGA={1}".format(lna, vga)

    def getCommandValues(self):
        values = super().getCommandValues()
        values["rf_gain"] = self._buildRfGain(values)
        return values

    def onPropertyChange(self, changes):
        changes = dict(changes)

        gain_changed = "fobos_lna" in changes or "fobos_vga" in changes
        changes.pop("fobos_lna", None)
        changes.pop("fobos_vga", None)

        if gain_changed:
            current_values = self.sdrProps.__dict__()
            changes["rf_gain"] = self._buildRfGain(current_values)

        if changes:
            super().onPropertyChange(changes)


class FobosDeviceDescription(SoapyConnectorDeviceDescription):
    def getName(self):
        return "RigExpert Fobos SDR"

    def supportsPpm(self):
        return False

    def hasAgc(self):
        return False

    def getGainStages(self):
        return None

    def _remove_generic_gain_input(self, inputs):
        return [i for i in inputs if not isinstance(i, GainInput)]

    def getInputs(self) -> List[Input]:
        return self._remove_generic_gain_input(super().getInputs()) + [
            DropdownInput(
                "clock_source",
                "Clock source",
                FobosClockSourceOptions,
                infotext="Use Internal for normal operation or External 10 MHz when a stable external reference is connected.",
            ),
            DropdownInput(
                "fobos_lna",
                "Fobos LNA",
                FobosLnaOptions,
                infotext="RF input only. Valid values: 0...3. Values 0 and 1 are effectively no gain / the same setting.",
            ),
            NumberInput(
                "fobos_vga",
                "Fobos VGA",
                infotext="RF input only. Valid values: 0...31.",
                validator=RangeValidator(0, 31),
            ),
        ]

    def getDeviceOptionalKeys(self):
        keys = super().getDeviceOptionalKeys()
        keys = [k for k in keys if k != "rf_gain"]
        return keys + ["clock_source", "fobos_lna", "fobos_vga"]

    def getProfileOptionalKeys(self):
        keys = super().getProfileOptionalKeys()
        keys = [k for k in keys if k != "rf_gain"]
        return keys + ["clock_source", "fobos_lna", "fobos_vga"]

    def getSampleRateRanges(self) -> List[Range]:
        return [
            Range(8000000),
            Range(10000000),
            Range(12500000),
            Range(16000000),
            Range(20000000),
            Range(25000000),
            Range(32000000),
            Range(40000000),
            Range(50000000),
        ]
