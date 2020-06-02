from .connector import ConnectorSource
from owrx.command import Flag, Option


class RtlSdrSource(ConnectorSource):
    def getCommandMapper(self):
        return (
            super()
            .getCommandMapper()
            .setBase("rtl_connector")
            .setMappings({"bias_tee": Flag("-b"), "direct_sampling": Option("-e")})
        )
