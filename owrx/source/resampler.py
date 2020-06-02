from .direct import DirectSource

import logging

logger = logging.getLogger(__name__)


class Resampler(DirectSource):
    def onPropertyChange(self, name, value):
        logger.warning("Resampler is unable to handle property change ({0} changed to {1})".format(name, value))

    def __init__(self, props, sdr):
        sdrProps = sdr.getProps()
        self.shift = (sdrProps["center_freq"] - props["center_freq"]) / sdrProps["samp_rate"]
        self.decimation = int(float(sdrProps["samp_rate"]) / props["samp_rate"])
        if_samp_rate = sdrProps["samp_rate"] / self.decimation
        self.transition_bw = 0.15 * (if_samp_rate / float(sdrProps["samp_rate"]))
        props["samp_rate"] = if_samp_rate

        self.sdr = sdr
        super().__init__(None, props)

    def getCommand(self):
        return [
            "nc -v 127.0.0.1 {nc_port}".format(nc_port=self.sdr.getPort()),
            "csdr shift_addfast_cc {shift}".format(shift=self.shift),
            "csdr fir_decimate_cc {decimation} {ddc_transition_bw} HAMMING".format(
                decimation=self.decimation, ddc_transition_bw=self.transition_bw
            ),
        ] + self.getNmuxCommand()

    def activateProfile(self, profile_id=None):
        logger.warning("Resampler does not support setting profiles")
        pass
