from abc import ABCMeta
from . import SdrSource

import logging

logger = logging.getLogger(__name__)


class DirectSource(SdrSource, metaclass=ABCMeta):
    def onPropertyChange(self, name, value):
        logger.debug(
            "restarting sdr source due to property change: {0} changed to {1}".format(
                name, value
            )
        )
        self.stop()
        self.sleepOnRestart()
        self.start()

    def getEventNames(self):
        return super().getEventNames() + [
            "nmux_memory",
        ]

    def getNmuxCommand(self):
        props = self.sdrProps

        nmux_bufcnt = nmux_bufsize = 0
        while nmux_bufsize < props["samp_rate"] / 4:
            nmux_bufsize += 4096
        while nmux_bufsize * nmux_bufcnt < props["nmux_memory"] * 1e6:
            nmux_bufcnt += 1
        if nmux_bufcnt == 0 or nmux_bufsize == 0:
            raise ValueError(
                "Error: nmux_bufsize or nmux_bufcnt is zero. "
                "These depend on nmux_memory and samp_rate options in config_webrx.py"
            )

        return ["nmux --bufsize %d --bufcnt %d --port %d --address 127.0.0.1" % (
            nmux_bufsize,
            nmux_bufcnt,
            self.port,
        )]

    def getCommand(self):
        return super().getCommand() + self.getFormatConversion() + self.getNmuxCommand()

    # override this in subclasses, if necessary
    def getFormatConversion(self):
        return []

    # override this in subclasses, if necessary
    def sleepOnRestart(self):
        pass
