from .direct import DirectSource
from owrx.command import Flag, Option


#
# In order to interface Perseus hardware, we resolve to use the
# perseustest utility that comes with libperseus-sdr support package.
# Below the base options used are shown:
#
# -p output    I/Q samples as 32 bits floating point
# -d -1        suppress debug messages
# -a           don't test attenuators on startup
# -t 0         runs indefinitely
# -o -         output samples on stdout
#
# As we are already returning I/Q samples as pairs of 32 bits
# floating points (option -p),no need for further conversions,
# so the method getFormatConversion(self) is not implemented at all.

class PerseussdrSource(DirectSource):
    def getCommandMapper(self):
        return super().getCommandMapper().setBase("perseustest -p -d -1 -a -t 0 -o -  ").setMappings(
            {
                "samp_rate": Option("-s"),
                "tuner_freq": Option("-f"),
                "attenuator": Option("-u"),
                "adc_preamp": Option("-m"),
                "adc_dither": Option("-x"),
                "wideband": Option("-w"),
            }
        )
