from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, HdAudio, \
    MetaProvider, AudioServiceSelector, DialFrequencyReceiver
from csdr.module import PickleModule
from csdreti.modules import EtiDecoder
from owrx.dab.dablin import DablinModule
from pycsdr.modules import Downmix, Buffer, Shift, Writer
from pycsdr.types import Format
from typing import Optional
from random import random

import logging

logger = logging.getLogger(__name__)


class MetaProcessor(PickleModule):
    def __init__(self, shifter: Shift):
        self.shifter = shifter
        self.shift = 0.0
        self.coarse_increment = -32 / 2048000
        self.fine_increment = - (1/3) / 2048000
        # carrier spacing is 1kHz, don't drift further than that.
        self.max_shift = 1000 / 2048000
        super().__init__()

    def process(self, data):
        result = {}
        for key, value in data.items():
            if key == "coarse_frequency_shift":
                if value > 0:
                    self._nudgeShift(random() * self.coarse_increment)
                else:
                    self._nudgeShift(random() * -self.coarse_increment)
            elif key == "fine_frequency_shift":
                if abs(value) > 10:
                    self._nudgeShift(self.fine_increment * value)
            else:
                # pass through everything else
                result[key] = value
        # don't send out data if there was nothing interesting for the client
        if not result:
            return
        result["mode"] = "DAB"
        return result

    def _nudgeShift(self, amount):
        self.shift += amount
        if self.shift > self.max_shift:
            self.shift = self.max_shift
        elif self.shift < -self.max_shift:
            self.shift = -self.max_shift
        logger.debug("new shift: %f", self.shift)
        self.shifter.setRate(self.shift)

    def resetShift(self):
        logger.debug("resetting shift")
        self.shift = 0
        self.shifter.setRate(0)


class Dablin(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, HdAudio, MetaProvider, AudioServiceSelector, DialFrequencyReceiver):
    def __init__(self):
        shift = Shift(0)
        self.decoder = EtiDecoder()

        metaBuffer = Buffer(Format.CHAR)
        self.decoder.setMetaWriter(metaBuffer)
        self.processor = MetaProcessor(shift)
        self.processor.setReader(metaBuffer.getReader())
        # use a dummy to start with. it won't run without.
        # will be replaced by setMetaWriter().
        self.processor.setWriter(Buffer(Format.CHAR))

        self.dablin = DablinModule()

        workers = [
            shift,
            self.decoder,
            self.dablin,
            Downmix(Format.FLOAT),
        ]
        super().__init__(workers)

    def _connect(self, w1, w2, buffer: Optional[Buffer] = None) -> None:
        if isinstance(w2, EtiDecoder):
            # eti decoder needs big chunks of data
            buffer = Buffer(w1.getOutputFormat(), size=2097152)
        super()._connect(w1, w2, buffer)

    def getFixedIfSampleRate(self) -> int:
        return 2048000

    def getFixedAudioRate(self) -> int:
        return 48000

    def stop(self):
        self.processor.stop()

    def setMetaWriter(self, writer: Writer) -> None:
        self.processor.setWriter(writer)

    def setAudioServiceId(self, serviceId: int) -> None:
        self.decoder.setServiceIdFilter([serviceId])
        self.dablin.setDabServiceId(serviceId)

    def setDialFrequency(self, frequency: int) -> None:
        self.processor.resetShift()
