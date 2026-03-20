from csdr.chain.demodulator import BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, HdAudio, \
    MetaProvider, DabServiceSelector, DialFrequencyReceiver
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
        # Cache stable fields (programmes, ensemble_id/label) so they can be
        # replayed to clients that connect after the initial FIC decode.
        self.cached_output = {}
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
        # Merge only stable fields (programmes, ensemble_label, etc.) into the cache.
        # Do NOT replace the whole dict — freq-correction-only packets have no
        # stable fields and would wipe out previously cached programme data.
        stable = {k: v for k, v in result.items() if k not in ("timestamp", "mode")}
        if stable:
            self.cached_output.update(stable)
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


class MetaForwarder(PickleModule):
    """
    Per-client meta forwarder for shared DAB mode.

    Reads from the shared ETI meta buffer (same source as MetaProcessor in
    SharedDabDecoder), strips frequency-correction keys (already handled by
    MetaProcessor in SharedDabDecoder), and forwards all other DAB metadata
    (programme labels, service list) to each client's meta WebSocket channel.
    """

    def process(self, data):
        result = {}
        for key, value in data.items():
            if key not in ("coarse_frequency_shift", "fine_frequency_shift"):
                result[key] = value
        if not result:
            return
        result["mode"] = "DAB"
        return result


class Dablin(BaseDemodulatorChain, FixedIfSampleRateChain, FixedAudioRateChain, HdAudio, MetaProvider, DabServiceSelector, DialFrequencyReceiver):
    def __init__(self, shared_decoder=None):
        self._shared_decoder = shared_decoder
        # Cache ETI reader — getEtiReader() allocates a new buffer cursor each call;
        # calling it repeatedly would orphan previous readers. Allocate once in setReader().
        self._eti_reader = None

        if shared_decoder is None:
            # Standalone mode — original behaviour, one EtiDecoder per client.
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
        else:
            # Shared mode — EtiDecoder runs in SharedDabDecoder; this chain only handles
            # per-client audio service selection. setReader() is overridden below to wire
            # DablinModule to the shared ETI stream instead of the IQ source.
            # Per-client MetaForwarder reads from the shared meta buffer and forwards
            # programme/service metadata to each client's meta WebSocket channel.
            self.dablin = DablinModule()
            self._meta_forwarder = MetaForwarder()
            self._meta_forwarder.setReader(shared_decoder.getMetaReader())
            # use a dummy to start with; will be replaced by setMetaWriter().
            self._meta_forwarder.setWriter(Buffer(Format.CHAR))

            workers = [
                self.dablin,
                Downmix(Format.FLOAT),
            ]

        super().__init__(workers)

    def setReader(self, reader) -> None:
        if self._shared_decoder is not None:
            # Ignore the IQ reader passed by ClientDemodulatorChain.
            # Wire DablinModule directly to the shared ETI output buffer instead.
            # Cache the reader — getEtiReader() creates a new cursor each call.
            if self._eti_reader is None:
                self._eti_reader = self._shared_decoder.getEtiReader()
            super().setReader(self._eti_reader)
        else:
            super().setReader(reader)

    def _connect(self, w1, w2, buffer: Optional[Buffer] = None) -> None:
        if isinstance(w2, EtiDecoder):
            # eti decoder needs big chunks of data (standalone mode only —
            # EtiDecoder is not in the shared-mode worker list)
            buffer = Buffer(w1.getOutputFormat(), size=2097152)
        super()._connect(w1, w2, buffer)

    def getFixedIfSampleRate(self) -> int:
        return 2048000

    def getFixedAudioRate(self) -> int:
        return 48000

    def stop(self):
        if self._shared_decoder is None:
            self.processor.stop()
        else:
            self._meta_forwarder.stop()
            if self._eti_reader is not None:
                self._eti_reader.stop()
                self._eti_reader = None

    def setMetaWriter(self, writer: Writer) -> None:
        if self._shared_decoder is None:
            self.processor.setWriter(writer)
        else:
            self._meta_forwarder.setWriter(writer)
            # Replay cached programme/ensemble metadata so the client sees the
            # programme list immediately, without waiting for EtiDecoder to
            # re-emit FIC data (which only happens once at initial decode).
            cached = self._shared_decoder.getCachedMeta()
            if cached:
                import pickle
                cached['mode'] = 'DAB'  # required: JS DabMetaPanel.isSupported() checks data.mode
                writer.write(pickle.dumps(cached))

    def setDabServiceId(self, serviceId: int) -> None:
        if self._shared_decoder is None:
            self.decoder.setServiceIdFilter([serviceId])
        self.dablin.setDabServiceId(serviceId)

    def setDialFrequency(self, frequency: int) -> None:
        if self._shared_decoder is None:
            self.processor.resetShift()
