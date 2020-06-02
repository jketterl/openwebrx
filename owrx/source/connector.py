from . import SdrSource
from owrx.socket import getAvailablePort
import socket
from owrx.command import CommandMapper, Flag, Option

import logging

logger = logging.getLogger(__name__)


class ConnectorSource(SdrSource):
    def __init__(self, id, props):
        self.controlSocket = None
        self.controlPort = getAvailablePort()
        super().__init__(id, props)

    def getCommandMapper(self):
        return super().getCommandMapper().setMappings(
            {
                "samp_rate": Option("-s"),
                "tuner_freq": Option("-f"),
                "port": Option("-p"),
                "controlPort": Option("-c"),
                "device": Option("-d"),
                "iqswap": Flag("-i"),
                "rtltcp_compat": Flag("-r"),
                "ppm": Option("-P"),
                "rf_gain": Option("-g"),
            }
        )

    def sendControlMessage(self, prop, value):
        logger.debug("sending property change over control socket: {0} changed to {1}".format(prop, value))
        self.controlSocket.sendall("{prop}:{value}\n".format(prop=prop, value=value).encode())

    def onPropertyChange(self, prop, value):
        if self.monitor is None:
            return
        if (
            (prop == "center_freq" or prop == "lfo_offset")
            and "lfo_offset" in self.sdrProps
            and self.sdrProps["lfo_offset"] is not None
        ):
            freq = self.sdrProps["center_freq"] + self.sdrProps["lfo_offset"]
            self.sendControlMessage("center_freq", freq)
        else:
            self.sendControlMessage(prop, value)

    def postStart(self):
        logger.debug("opening control socket...")
        self.controlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.controlSocket.connect(("localhost", self.controlPort))

    def stop(self):
        super().stop()
        if self.controlSocket:
            self.controlSocket.close()
            self.controlSocket = None

    def getControlPort(self):
        return self.controlPort

    def getCommandValues(self):
        values = super().getCommandValues()
        values["port"] = self.getPort()
        values["controlPort"] = self.getControlPort()
        return values
