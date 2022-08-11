from owrx.source.connector import ConnectorSource, ConnectorDeviceDescription
from owrx.command import Flag, Option, Argument
from owrx.form.input import Input
from owrx.form.input.device import RemoteInput
from typing import List


class RtlTcpSource(ConnectorSource):
    def getCommandMapper(self):
        return (
            super()
            .getCommandMapper()
            .setBase("rtl_tcp_connector")
            .setMappings(
                {
                    "bias_tee": Flag("--biastee"),
                    "direct_sampling": Option("--directsampling"),
                    "remote": Argument(),
                }
            )
        )


class RtlTcpDeviceDescription(ConnectorDeviceDescription):
    def getName(self):
        return "RTL-SDR device (via rtl_tcp)"

    def getInputs(self) -> List[Input]:
        return super().getInputs() + [RemoteInput()]

    def getDeviceMandatoryKeys(self):
        return super().getDeviceMandatoryKeys() + ["remote"]
