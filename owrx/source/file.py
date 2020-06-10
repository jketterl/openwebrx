from owrx.command import Option
from .direct import DirectSource
from subprocess import Popen

import logging

logger = logging.getLogger(__name__)


class FileSource(DirectSource):
    def getCommandMapper(self):
        file = "CQWW_CW_2005.fs96k.cf7040.iq.s16.dat"
        bytes_per_sample = 4
        #sdrProps = getProps()
        #srate = sdrProps["samp_rate"]
        srate = 96000
        cmd = "(while true; do cat {fn}; done) | csdr flowcontrol {sr} 20".format(fn=file,sr=srate*bytes_per_sample*1.05)
        return super().getCommandMapper().setBase(cmd)

    def getFormatConversion(self):
        return ["csdr convert_s16_f --bigendian", "csdr iq_swap_ff"]
