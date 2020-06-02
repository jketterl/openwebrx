from abc import ABCMeta, abstractmethod
from owrx.command import Option
from .connector import ConnectorSource


class SoapyConnectorSource(ConnectorSource, metaclass=ABCMeta):
    def getCommandMapper(self):
        return super().getCommandMapper().setBase("soapy_connector").setMappings(
            {
                "antenna": Option("-a"),
                "soapy_settings": Option("-t"),
            }
        )

    """
    must be implemented by child classes to be able to build a driver-based device selector by default.
    return value must be the corresponding soapy driver identifier.
    """

    @abstractmethod
    def getDriver(self):
        pass

    def getEventNames(self):
        return super().getEventNames() + list(self.getSoapySettingsMappings().keys())

    def parseDeviceString(self, dstr):
        def decodeComponent(c):
            kv = c.split("=", 1)
            if len(kv) < 2:
                return c
            else:
                return {kv[0]: kv[1]}

        return [decodeComponent(c) for c in dstr.split(",")]

    def encodeDeviceString(self, dobj):
        def encodeComponent(c):
            if isinstance(c, str):
                return c
            else:
                return ",".join(["{0}={1}".format(key, value) for key, value in c.items()])

        return ",".join([encodeComponent(c) for c in dobj])

    def buildSoapyDeviceParameters(self, parsed, values):
        """
        this method always attempts to inject a driver= part into the soapysdr query, depending on what connector was used.
        this prevents the soapy_connector from using the wrong device in scenarios where there's no same-type sdrs.
        """
        parsed = [v for v in parsed if "driver" not in v]
        parsed += [{"driver": self.getDriver()}]
        return parsed

    def getSoapySettingsMappings(self):
        return {}

    def buildSoapySettings(self, values):
        settings = {}
        for k, v in self.getSoapySettingsMappings().items():
            if k in values and values[k] is not None:
                settings[v] = self.convertSoapySettingsValue(values[k])
        return settings

    def convertSoapySettingsValue(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        return value

    def getCommandValues(self):
        values = super().getCommandValues()
        if "device" in values and values["device"] is not None:
            parsed = self.parseDeviceString(values["device"])
        else:
            parsed = []
        modified = self.buildSoapyDeviceParameters(parsed, values)
        values["device"] = self.encodeDeviceString(modified)
        settings = ",".join(["{0}={1}".format(k, v) for k, v in self.buildSoapySettings(values).items()])
        if len(settings):
            values["soapy_settings"] = settings
        return values

    def onPropertyChange(self, prop, value):
        mappings = self.getSoapySettingsMappings()
        if prop in mappings.keys():
            value = "{0}={1}".format(mappings[prop], self.convertSoapySettingsValue(value))
            prop = "settings"
        super().onPropertyChange(prop, value)
