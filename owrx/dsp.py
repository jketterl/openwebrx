from owrx.source import SdrSourceEventClient, SdrSourceState, SdrClientClass
from owrx.property import PropertyStack, PropertyLayer, PropertyValidator, PropertyDeleted, PropertyDeletion
from owrx.property.validators import OrValidator, RegexValidator, BoolValidator
from owrx.modes import Modes, DigitalMode
from csdr.chain import Chain
from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, HdAudio, \
    SecondaryDemodulator, DialFrequencyReceiver, MetaProvider, SlotFilterChain, SecondarySelectorChain, \
    DeemphasisTauChain, DemodulatorError, RdsChain, DabServiceSelector
from csdr.chain.selector import Selector, SecondarySelector
from csdr.chain.clientaudio import ClientAudioChain
from csdr.chain.fft import FftChain
from csdr.chain.dummy import DummyDemodulator
from pycsdr.modules import Buffer, Writer
from pycsdr.types import Format
from typing import Union, Optional
from io import BytesIO
from abc import ABC, abstractmethod
import threading
import re
import pickle

import logging

logger = logging.getLogger(__name__)


# now that's a name. help, i've reached enterprise level OOP here
class ClientDemodulatorSecondaryDspEventClient(ABC):
    @abstractmethod
    def onSecondaryDspRateChange(self, rate):
        pass

    @abstractmethod
    def onSecondaryDspBandwidthChange(self, bw):
        pass


class ClientDemodulatorChain(Chain):
    def __init__(self, demod: BaseDemodulatorChain, sampleRate: int, outputRate: int, hdOutputRate: int, audioCompression: str, secondaryDspEventReceiver: ClientDemodulatorSecondaryDspEventClient):
        self.sampleRate = sampleRate
        self.outputRate = outputRate
        self.hdOutputRate = hdOutputRate
        self.secondaryDspEventReceiver = secondaryDspEventReceiver
        self.selector = Selector(sampleRate, outputRate)
        self.selectorBuffer = Buffer(Format.COMPLEX_FLOAT)
        self.audioBuffer = None
        self.demodulator = demod
        self.secondaryDemodulator = None
        self.centerFrequency = None
        self.frequencyOffset = None
        self.wfmDeemphasisTau = 50e-6
        self.rdsRbds = False
        inputRate = demod.getFixedAudioRate() if isinstance(demod, FixedAudioRateChain) else outputRate
        oRate = hdOutputRate if isinstance(demod, HdAudio) else outputRate
        self.clientAudioChain = ClientAudioChain(demod.getOutputFormat(), inputRate, oRate, audioCompression)
        self.secondaryFftSize = 2048
        self.secondaryFftOverlapFactor = 0.3
        self.secondaryFftFps = 9
        self.secondaryFftCompression = "adpcm"
        self.secondaryFftChain = None
        self.metaWriter = None
        self.secondaryFftWriter = None
        self.secondaryWriter = None
        self.squelchLevel = -150
        self.secondarySelector = None
        self.secondaryFrequencyOffset = None
        super().__init__([self.selector, self.demodulator, self.clientAudioChain])

    def stop(self):
        super().stop()
        if self.secondaryFftChain is not None:
            self.secondaryFftChain.stop()
            self.secondaryFftChain = None
        if self.secondaryDemodulator is not None:
            self.secondaryDemodulator.stop()
            self.secondaryDemodulator = None

    def _connect(self, w1, w2, buffer: Optional[Buffer] = None) -> None:
        if w1 is self.selector:
            super()._connect(w1, w2, self.selectorBuffer)
        elif w2 is self.clientAudioChain:
            format = w1.getOutputFormat()
            if self.audioBuffer is None or self.audioBuffer.getFormat() != format:
                self.audioBuffer = Buffer(format)
                if self.secondaryDemodulator is not None and self.secondaryDemodulator.getInputFormat() is not Format.COMPLEX_FLOAT:
                    self.secondaryDemodulator.setReader(self.audioBuffer.getReader())
            super()._connect(w1, w2, self.audioBuffer)
        else:
            super()._connect(w1, w2)

    def setDemodulator(self, demodulator: BaseDemodulatorChain):
        if demodulator is self.demodulator:
            return

        try:
            self.clientAudioChain.setFormat(demodulator.getOutputFormat())
        except ValueError:
            # this will happen if the new format does not match the current demodulator.
            # it's expected and should be mended when swapping out the demodulator in the next step
            pass

        if self.demodulator is not None:
            self.demodulator.stop()

        self.demodulator = demodulator

        self.selector.setOutputRate(self._getSelectorOutputRate())

        clientRate = self._getClientAudioInputRate()
        self.demodulator.setSampleRate(clientRate)

        if isinstance(self.demodulator, DeemphasisTauChain):
            self.demodulator.setDeemphasisTau(self.wfmDeemphasisTau)

        if isinstance(self.demodulator, RdsChain):
            self.demodulator.setRdsRbds(self.rdsRbds)

        self._updateDialFrequency()
        self._syncSquelch()

        if self.metaWriter is not None and isinstance(demodulator, MetaProvider):
            demodulator.setMetaWriter(self.metaWriter)

        self.replace(1, demodulator)

        self.clientAudioChain.setInputRate(clientRate)
        outputRate = self.hdOutputRate if isinstance(self.demodulator, HdAudio) else self.outputRate
        self.clientAudioChain.setClientRate(outputRate)

    def stopDemodulator(self):
        if self.demodulator is None:
            return

        # we need to get the currrent demodulator out of the chain so that it can be deallocated properly
        # so we just replace it with a dummy here
        # in order to avoid any client audio chain hassle, the dummy simply imitates the output format of the current
        # demodulator
        self.replace(1, DummyDemodulator(self.demodulator.getOutputFormat()))

        self.demodulator.stop()
        self.demodulator = None

        self.setSecondaryDemodulator(None)

    def _getSelectorOutputRate(self):
        if isinstance(self.demodulator, FixedIfSampleRateChain):
            return self.demodulator.getFixedIfSampleRate()
        elif isinstance(self.secondaryDemodulator, FixedAudioRateChain):
            if isinstance(self.demodulator, FixedAudioRateChain) and self.demodulator.getFixedAudioRate() != self.secondaryDemodulator.getFixedAudioRate():
                raise ValueError("secondary and primary demodulator chain audio rates do not match!")
            return self.secondaryDemodulator.getFixedAudioRate()
        else:
            return self.hdOutputRate if isinstance(self.demodulator, HdAudio) else self.outputRate

    def _getClientAudioInputRate(self):
        if isinstance(self.demodulator, FixedAudioRateChain):
            return self.demodulator.getFixedAudioRate()
        elif isinstance(self.secondaryDemodulator, FixedAudioRateChain):
            return self.secondaryDemodulator.getFixedAudioRate()
        else:
            return self.hdOutputRate if isinstance(self.demodulator, HdAudio) else self.outputRate

    def setSecondaryDemodulator(self, demod: Optional[SecondaryDemodulator]):
        if demod is self.secondaryDemodulator:
            return

        if self.secondaryDemodulator is not None:
            self.secondaryDemodulator.stop()

        self.secondaryDemodulator = demod

        rate = self._getSelectorOutputRate()
        self.selector.setOutputRate(rate)

        clientRate = self._getClientAudioInputRate()
        self.clientAudioChain.setInputRate(clientRate)
        if self.demodulator is not None:
            self.demodulator.setSampleRate(clientRate)

        self._updateDialFrequency()
        self._syncSquelch()

        if isinstance(self.secondaryDemodulator, SecondarySelectorChain):
            bandwidth = self.secondaryDemodulator.getBandwidth()
            self.secondarySelector = SecondarySelector(rate, bandwidth)
            self.secondarySelector.setReader(self.selectorBuffer.getReader())
            self.secondarySelector.setFrequencyOffset(self.secondaryFrequencyOffset)
            self.secondaryDspEventReceiver.onSecondaryDspBandwidthChange(bandwidth)
        else:
            self.secondarySelector = None

        if self.secondaryDemodulator is not None:
            self.secondaryDemodulator.setSampleRate(rate)
            if self.secondarySelector is not None:
                buffer = Buffer(Format.COMPLEX_FLOAT)
                self.secondarySelector.setWriter(buffer)
                self.secondaryDemodulator.setReader(buffer.getReader())
            elif self.secondaryDemodulator.getInputFormat() is Format.COMPLEX_FLOAT:
                self.secondaryDemodulator.setReader(self.selectorBuffer.getReader())
            else:
                self.secondaryDemodulator.setReader(self.audioBuffer.getReader())
            self.secondaryDemodulator.setWriter(self.secondaryWriter)

        if (self.secondaryDemodulator is None or not self.secondaryDemodulator.isSecondaryFftShown()) and self.secondaryFftChain is not None:
            self.secondaryFftChain.stop()
            self.secondaryFftChain = None

        if (self.secondaryDemodulator is not None and self.secondaryDemodulator.isSecondaryFftShown()) and self.secondaryFftChain is None:
            self._createSecondaryFftChain()

        if self.secondaryFftChain is not None:
            self.secondaryFftChain.setSampleRate(rate)
            self.secondaryDspEventReceiver.onSecondaryDspRateChange(rate)

    def _createSecondaryFftChain(self):
        if self.secondaryFftChain is not None:
            self.secondaryFftChain.stop()
        self.secondaryFftChain = FftChain(self._getSelectorOutputRate(), self.secondaryFftSize, self.secondaryFftOverlapFactor, self.secondaryFftFps, self.secondaryFftCompression)
        self.secondaryFftChain.setReader(self.selectorBuffer.getReader())
        self.secondaryFftChain.setWriter(self.secondaryFftWriter)

    def _syncSquelch(self):
        if self.demodulator is not None and not self.demodulator.supportsSquelch() or (self.secondaryDemodulator is not None and not self.secondaryDemodulator.supportsSquelch()):
            self.selector.setSquelchLevel(-150)
        else:
            self.selector.setSquelchLevel(self.squelchLevel)

    def setLowCut(self, lowCut: Union[float, None]):
        self.selector.setLowCut(lowCut)

    def setHighCut(self, highCut: Union[float, None]):
        self.selector.setHighCut(highCut)

    def setBandpass(self, lowCut, highCut):
        self.selector.setBandpass(lowCut, highCut)

    def setFrequencyOffset(self, offset: int) -> None:
        if offset == self.frequencyOffset:
            return
        self.frequencyOffset = offset
        self.selector.setFrequencyOffset(offset)
        self._updateDialFrequency()

    def setCenterFrequency(self, frequency: int) -> None:
        if frequency == self.centerFrequency:
            return
        self.centerFrequency = frequency
        self._updateDialFrequency()

    def _updateDialFrequency(self):
        if self.centerFrequency is None or self.frequencyOffset is None:
            return
        dialFrequency = self.centerFrequency + self.frequencyOffset
        if isinstance(self.demodulator, DialFrequencyReceiver):
            self.demodulator.setDialFrequency(dialFrequency)
        if isinstance(self.secondaryDemodulator, DialFrequencyReceiver):
            if self.secondaryFrequencyOffset:
                dialFrequency += self.secondaryFrequencyOffset
            self.secondaryDemodulator.setDialFrequency(dialFrequency)

    def setAudioCompression(self, compression: str) -> None:
        self.clientAudioChain.setAudioCompression(compression)

    def setSquelchLevel(self, level: float) -> None:
        if level == self.squelchLevel:
            return
        self.squelchLevel = level
        self._syncSquelch()

    def setOutputRate(self, outputRate) -> None:
        if outputRate == self.outputRate:
            return

        self.outputRate = outputRate

        if isinstance(self.demodulator, HdAudio):
            return
        self._updateDemodulatorOutputRate(outputRate)

    def setHdOutputRate(self, outputRate) -> None:
        if outputRate == self.hdOutputRate:
            return

        self.hdOutputRate = outputRate

        if not isinstance(self.demodulator, HdAudio):
            return
        self._updateDemodulatorOutputRate(outputRate)

    def _updateDemodulatorOutputRate(self, outputRate):
        if not isinstance(self.demodulator, FixedIfSampleRateChain):
            self.selector.setOutputRate(outputRate)
            self.demodulator.setSampleRate(outputRate)
            if self.secondaryDemodulator is not None:
                self.secondaryDemodulator.setSampleRate(outputRate)
        if not isinstance(self.demodulator, FixedAudioRateChain):
            self.clientAudioChain.setClientRate(outputRate)

    def setSampleRate(self, sampleRate: int) -> None:
        if sampleRate == self.sampleRate:
            return
        self.sampleRate = sampleRate
        self.selector.setInputRate(sampleRate)

    def setPowerWriter(self, writer: Writer) -> None:
        self.selector.setPowerWriter(writer)

    def setMetaWriter(self, writer: Writer) -> None:
        if writer is self.metaWriter:
            return
        self.metaWriter = writer
        if isinstance(self.demodulator, MetaProvider):
            self.demodulator.setMetaWriter(self.metaWriter)

    def setSecondaryFftWriter(self, writer: Writer) -> None:
        if writer is self.secondaryFftWriter:
            return
        self.secondaryFftWriter = writer

        if self.secondaryFftChain is not None:
            self.secondaryFftChain.setWriter(writer)

    def setSecondaryWriter(self, writer: Writer) -> None:
        if writer is self.secondaryWriter:
            return
        self.secondaryWriter = writer
        if self.secondaryDemodulator is not None:
            self.secondaryDemodulator.setWriter(writer)

    def setSlotFilter(self, filter: int) -> None:
        if not isinstance(self.demodulator, SlotFilterChain):
            return
        self.demodulator.setSlotFilter(filter)

    def setDabServiceId(self, serviceId: int) -> None:
        if not isinstance(self.demodulator, DabServiceSelector):
            return
        self.demodulator.setDabServiceId(serviceId)

    def setSecondaryFftSize(self, size: int) -> None:
        if size == self.secondaryFftSize:
            return
        self.secondaryFftSize = size
        if not self.secondaryFftChain:
            return
        self._createSecondaryFftChain()

    def setSecondaryFrequencyOffset(self, freq: int) -> None:
        if self.secondaryFrequencyOffset == freq:
            return
        self.secondaryFrequencyOffset = freq
        if self.secondarySelector:
            self.secondarySelector.setFrequencyOffset(self.secondaryFrequencyOffset)
        self._updateDialFrequency()

    def setSecondaryFftCompression(self, compression: str) -> bool:
        if compression == self.secondaryFftCompression:
            return False
        self.secondaryFftCompression = compression
        if not self.secondaryFftChain:
            return False
        # compressions may have different formats
        try:
            self.secondaryFftChain.setCompression(self.secondaryFftCompression)
        except ValueError:
            return True
        # formats matched
        return False

    def setSecondaryFftOverlapFactor(self, overlap: float) -> None:
        if overlap == self.secondaryFftOverlapFactor:
            return
        self.secondaryFftOverlapFactor = overlap
        if not self.secondaryFftChain:
            return
        self.secondaryFftChain.setVOverlapFactor(self.secondaryFftOverlapFactor)

    def setSecondaryFftFps(self, fps: int) -> None:
        if fps == self.secondaryFftFps:
            return
        self.secondaryFftFps = fps
        if not self.secondaryFftChain:
            return
        self.secondaryFftChain.setFps(self.secondaryFftFps)

    def getSecondaryFftOutputFormat(self) -> Format:
        # if we already have an FFT chain, query its output format
        if self.secondaryFftChain is not None:
            return self.secondaryFftChain.getOutputFormat()
        # ADPCM compression produces chars
        elif self.secondaryFftCompression == "adpcm":
            return Format.CHAR
        # uncompressed FFT uses floats
        return Format.FLOAT

    def setWfmDeemphasisTau(self, tau: float) -> None:
        if tau == self.wfmDeemphasisTau:
            return
        self.wfmDeemphasisTau = tau
        if isinstance(self.demodulator, DeemphasisTauChain):
            self.demodulator.setDeemphasisTau(self.wfmDeemphasisTau)

    def setRdsRbds(self, rdsRbds: bool) -> None:
        if rdsRbds == self.rdsRbds:
            return
        self.rdsRbds = rdsRbds
        if isinstance(self.demodulator, RdsChain):
            self.demodulator.setRdsRbds(self.rdsRbds)


class ModulationValidator(OrValidator):
    """
    This validator only allows alphanumeric characters and numbers, but no spaces or special characters
    """

    def __init__(self):
        super().__init__(BoolValidator(), RegexValidator(re.compile("^[a-z0-9]+$")))


class DspManager(SdrSourceEventClient, ClientDemodulatorSecondaryDspEventClient):
    def __init__(self, handler, sdrSource):
        self.handler = handler
        self.sdrSource = sdrSource

        self.props = PropertyStack()

        # current audio mode. should be "audio" or "hd_audio" depending on what demodulatur is in use.
        self.audioOutput = None

        # local demodulator properties not forwarded to the sdr
        # ensure strict validation since these can be set from the client
        # and are used to build executable commands
        validators = {
            "output_rate": "int",
            "hd_output_rate": "int",
            "squelch_level": "num",
            "secondary_mod": ModulationValidator(),
            "low_cut": "num",
            "high_cut": "num",
            "offset_freq": "int",
            "mod": ModulationValidator(),
            "secondary_offset_freq": "int",
            "dmr_filter": "int",
            "dab_service_id": "int",
        }
        self.localProps = PropertyValidator(PropertyLayer().filter(*validators.keys()), validators)

        self.props.addLayer(0, self.localProps)
        # properties that we inherit from the sdr
        self.props.addLayer(
            1,
            self.sdrSource.getProps().filter(
                "audio_compression",
                "fft_compression",
                "digimodes_fft_size",
                "samp_rate",
                "center_freq",
                "start_mod",
                "start_freq",
                "wfm_deemphasis_tau",
                "wfm_rds_rbds",
                "digital_voice_codecserver",
            ),
        )

        # defaults for values that may not be set
        self.props.addLayer(
            2,
            PropertyLayer(
                output_rate=12000,
                hd_output_rate=48000,
                digital_voice_codecserver="",
            ).readonly()
        )

        self.chain = ClientDemodulatorChain(
            self._getDemodulator("nfm"),
            self.props["samp_rate"],
            self.props["output_rate"],
            self.props["hd_output_rate"],
            self.props["audio_compression"],
            self
        )

        self.readers = {}

        if "start_mod" in self.props:
            mode = Modes.findByModulation(self.props["start_mod"])
            if mode:
                self.setDemodulator(mode.get_modulation())
                if isinstance(mode, DigitalMode):
                    self.setSecondaryDemodulator(mode.modulation)
                if mode.bandpass:
                    bpf = [mode.bandpass.low_cut, mode.bandpass.high_cut]
                    self.chain.setBandpass(*bpf)
                    self.props["low_cut"] = mode.bandpass.low_cut
                    self.props["high_cut"] = mode.bandpass.high_cut
                else:
                    self.chain.setBandpass(None, None)
            else:
                # TODO modes should be mandatory
                self.setDemodulator(self.props["start_mod"])

        if "start_freq" in self.props and "center_freq" in self.props:
            self.chain.setFrequencyOffset(self.props["start_freq"] - self.props["center_freq"])
        else:
            self.chain.setFrequencyOffset(0)

        self.subscriptions = [
            self.props.wireProperty("audio_compression", self.setAudioCompression),
            self.props.wireProperty("fft_compression", self.setSecondaryFftCompression),
            self.props.wireProperty("fft_voverlap_factor", self.chain.setSecondaryFftOverlapFactor),
            self.props.wireProperty("fft_fps", self.chain.setSecondaryFftFps),
            self.props.wireProperty("digimodes_fft_size", self.setSecondaryFftSize),
            self.props.wireProperty("samp_rate", self.chain.setSampleRate),
            self.props.wireProperty("output_rate", self.chain.setOutputRate),
            self.props.wireProperty("hd_output_rate", self.chain.setHdOutputRate),
            self.props.wireProperty("offset_freq", self.chain.setFrequencyOffset),
            self.props.wireProperty("center_freq", self.chain.setCenterFrequency),
            self.props.wireProperty("squelch_level", self.chain.setSquelchLevel),
            self.props.wireProperty("low_cut", self.setLowCut),
            self.props.wireProperty("high_cut", self.setHighCut),
            self.props.wireProperty("mod", self.setDemodulator),
            self.props.wireProperty("dmr_filter", self.chain.setSlotFilter),
            self.props.wireProperty("dab_service_id", self.chain.setDabServiceId),
            self.props.wireProperty("wfm_deemphasis_tau", self.chain.setWfmDeemphasisTau),
            self.props.wireProperty("wfm_rds_rbds", self.chain.setRdsRbds),
            self.props.wireProperty("secondary_mod", self.setSecondaryDemodulator),
            self.props.wireProperty("secondary_offset_freq", self.chain.setSecondaryFrequencyOffset),
        ]

        # wire power level output
        buffer = Buffer(Format.FLOAT)
        self.chain.setPowerWriter(buffer)
        self.wireOutput("smeter", buffer)

        # wire meta output
        buffer = Buffer(Format.CHAR)
        self.chain.setMetaWriter(buffer)
        self.wireOutput("meta", buffer)

        # wire secondary FFT
        buffer = Buffer(self.chain.getSecondaryFftOutputFormat())
        self.chain.setSecondaryFftWriter(buffer)
        self.wireOutput("secondary_fft", buffer)

        # wire secondary demodulator
        buffer = Buffer(Format.CHAR)
        self.chain.setSecondaryWriter(buffer)
        self.wireOutput("secondary_demod", buffer)

        self.startOnAvailable = False

        self.sdrSource.addClient(self)

    def setSecondaryFftSize(self, size):
        self.chain.setSecondaryFftSize(size)
        self.handler.write_secondary_dsp_config({"secondary_fft_size": size})

    def _getDemodulator(self, demod: Union[str, BaseDemodulatorChain]) -> Optional[BaseDemodulatorChain]:
        if isinstance(demod, BaseDemodulatorChain):
            return demod
        # TODO: move this to Modes
        if demod == "nfm":
            from csdr.chain.analog import NFm
            return NFm(self.props["output_rate"])
        elif demod == "wfm":
            from csdr.chain.analog import WFm
            return WFm(self.props["hd_output_rate"], self.props["wfm_deemphasis_tau"], self.props["wfm_rds_rbds"])
        elif demod == "am":
            from csdr.chain.analog import Am
            return Am()
        elif demod in ["usb", "lsb", "cw"]:
            from csdr.chain.analog import Ssb
            return Ssb()
        elif demod == "dmr":
            from csdr.chain.digiham import Dmr
            return Dmr(self.props["digital_voice_codecserver"])
        elif demod == "dstar":
            from csdr.chain.digiham import Dstar
            return Dstar(self.props["digital_voice_codecserver"])
        elif demod == "ysf":
            from csdr.chain.digiham import Ysf
            return Ysf(self.props["digital_voice_codecserver"])
        elif demod == "nxdn":
            from csdr.chain.digiham import Nxdn
            return Nxdn(self.props["digital_voice_codecserver"])
        elif demod == "m17":
            from csdr.chain.m17 import M17
            return M17()
        elif demod == "drm":
            from csdr.chain.drm import Drm
            return Drm()
        elif demod == "freedv":
            from csdr.chain.freedv import FreeDV
            return FreeDV()
        elif demod == "dab":
            from csdr.chain.dablin import Dablin
            return Dablin()
        elif demod == "empty":
            from csdr.chain.analog import Empty
            return Empty()

    def setDemodulator(self, mod):
        # this kills both primary and secondary demodulators
        self.chain.stopDemodulator()

        try:
            demodulator = self._getDemodulator(mod)
            if demodulator is None:
                raise ValueError("unsupported demodulator: {}".format(mod))
            self.chain.setDemodulator(demodulator)

            output = "hd_audio" if isinstance(demodulator, HdAudio) else "audio"

            if output != self.audioOutput:
                self.audioOutput = output
                # re-wire the audio to the correct client API
                buffer = Buffer(self.chain.getOutputFormat())
                self.chain.setWriter(buffer)
                self.wireOutput(self.audioOutput, buffer)

            # recreate secondary demodulator, if present
            mod2 = self.props["secondary_mod"] if "secondary_mod" in self.props else ""
            desc = Modes.findByModulation(mod2)
            if hasattr(desc, "underlying") and mod in desc.underlying:
                self.setSecondaryDemodulator(mod2)

        except DemodulatorError as de:
            self.handler.write_demodulator_error(str(de))

    def _getSecondaryDemodulator(self, mod) -> Optional[SecondaryDemodulator]:
        if isinstance(mod, SecondaryDemodulator):
            return mod
        if mod in ["ft8", "wspr", "jt65", "jt9", "ft4", "fst4", "fst4w", "q65"]:
            from csdr.chain.digimodes import AudioChopperDemodulator
            from owrx.wsjt import WsjtParser
            return AudioChopperDemodulator(mod, WsjtParser())
        elif mod == "msk144":
            from csdr.chain.digimodes import Msk144Demodulator
            return Msk144Demodulator()
        elif mod == "js8":
            from csdr.chain.digimodes import AudioChopperDemodulator
            from owrx.js8 import Js8Parser
            return AudioChopperDemodulator(mod, Js8Parser())
        elif mod == "packet":
            from csdr.chain.digimodes import PacketDemodulator
            return PacketDemodulator()
        elif mod == "pocsag":
            from csdr.chain.digiham import PocsagDemodulator
            return PocsagDemodulator()
        elif mod == "bpsk31":
            from csdr.chain.digimodes import PskDemodulator
            return PskDemodulator(31.25)
        elif mod == "bpsk63":
            from csdr.chain.digimodes import PskDemodulator
            return PskDemodulator(62.5)
        elif mod == "rtty170":
            from csdr.chain.digimodes import RttyDemodulator
            return RttyDemodulator(45.45, 170)
        elif mod == "rtty450":
            from csdr.chain.digimodes import RttyDemodulator
            return RttyDemodulator(50, 450, invert=True)
        elif mod == "rtty85":
            from csdr.chain.digimodes import RttyDemodulator
            return RttyDemodulator(50, 85, invert=True)
        elif mod == "adsb":
            from csdr.chain.dump1090 import Dump1090
            return Dump1090()
        elif mod == "ism":
            from csdr.chain.rtl433 import Rtl433
            return Rtl433()
        elif mod == "hfdl":
            from csdr.chain.dumphfdl import DumpHFDL
            return DumpHFDL()
        elif mod == "vdl2":
            from csdr.chain.dumpvdl2 import DumpVDL2
            return DumpVDL2()

    def setSecondaryDemodulator(self, mod):
        demodulator = self._getSecondaryDemodulator(mod)
        if not demodulator:
            self.chain.setSecondaryDemodulator(None)
        else:
            self.chain.setSecondaryDemodulator(demodulator)

    def setAudioCompression(self, comp):
        try:
            self.chain.setAudioCompression(comp)
        except ValueError:
            # wrong output format... need to re-wire
            buffer = Buffer(self.chain.getOutputFormat())
            self.chain.setWriter(buffer)
            self.wireOutput(self.audioOutput, buffer)

    def setSecondaryFftCompression(self, compression):
        try:
            self.chain.setSecondaryFftCompression(compression)
        except ValueError:
            # wrong output format... need to re-wire
            pass

        buffer = Buffer(self.chain.getSecondaryFftOutputFormat())
        self.chain.setSecondaryFftWriter(buffer)
        self.wireOutput("secondary_fft", buffer)

    def setLowCut(self, lowCut: Union[float, PropertyDeletion]):
        self.chain.setLowCut(None if lowCut is PropertyDeleted else lowCut)

    def setHighCut(self, highCut: Union[float, PropertyDeletion]):
        self.chain.setHighCut(None if highCut is PropertyDeleted else highCut)

    def start(self):
        if self.sdrSource.isAvailable():
            self.chain.setReader(self.sdrSource.getBuffer().getReader())
        else:
            self.startOnAvailable = True

    def unwireOutput(self, t: str):
        if t in self.readers:
            self.readers[t].stop()
            del self.readers[t]

    def wireOutput(self, t: str, buffer: Buffer):
        logger.debug("wiring new output of type %s", t)
        writers = {
            "audio": self.handler.write_dsp_data,
            "hd_audio": self.handler.write_hd_audio,
            "smeter": self.handler.write_s_meter_level,
            "secondary_fft": self.handler.write_secondary_fft,
            "secondary_demod": self._unpickle(self.handler.write_secondary_demod),
            "meta": self._unpickle(self.handler.write_metadata),
        }

        write = writers[t]

        self.unwireOutput(t)

        reader = buffer.getReader()
        self.readers[t] = reader
        threading.Thread(target=self.chain.pump(reader.read, write), name="dsp_pump_{}".format(t)).start()

    def _unpickle(self, callback):
        def unpickler(data):
            b = data.tobytes()
            # If we know it's not pickled, let us not unpickle
            if len(b) < 2 or b[0] != 0x80 or not 3 <= b[1] <= pickle.HIGHEST_PROTOCOL:
                callback(b.decode("ascii", errors="replace"))
                return

            io = BytesIO(b)
            try:
                while True:
                    callback(pickle.load(io))
            except EOFError:
                pass
            except pickle.UnpicklingError:
                callback(b.decode("ascii", errors="replace"))

        return unpickler

    def stop(self):
        if self.chain:
            self.chain.stop()
            self.chain = None
        for reader in self.readers.values():
            reader.stop()
        self.readers = {}

        self.startOnAvailable = False
        self.sdrSource.removeClient(self)
        for sub in self.subscriptions:
            sub.cancel()
        self.subscriptions = []

    def setProperties(self, props):
        for k, v in props.items():
            self.setProperty(k, v)

    def setProperty(self, prop, value):
        if value is None:
            if prop in self.localProps:
                del self.localProps[prop]
        else:
            self.localProps[prop] = value

    def getClientClass(self) -> SdrClientClass:
        return SdrClientClass.USER

    def onStateChange(self, state: SdrSourceState):
        if state is SdrSourceState.RUNNING:
            logger.debug("received STATE_RUNNING, attempting DspSource restart")
            if self.startOnAvailable:
                self.chain.setReader(self.sdrSource.getBuffer().getReader())
                self.startOnAvailable = False

    def onFail(self):
        logger.debug("received onFail(), shutting down DspSource")
        self.stop()

    def onShutdown(self):
        self.stop()

    def onSecondaryDspBandwidthChange(self, bw):
        self.handler.write_secondary_dsp_config({"secondary_bw": bw})

    def onSecondaryDspRateChange(self, rate):
        self.handler.write_secondary_dsp_config({"if_samp_rate": rate})
