import threading
import logging

from csdreti.modules import EtiDecoder
from pycsdr.modules import Shift, Buffer
from pycsdr.types import Format

logger = logging.getLogger(__name__)


class SharedDabDecoder:
    """
    Runs a single Shift + EtiDecoder + MetaProcessor pipeline for one DAB multiplex.
    Multiple clients call getEtiReader() to receive independent readers into the shared
    ETI output buffer — each reader maintains its own cursor position, so clients consume
    data at their own pace without interfering with each other.
    """

    def __init__(self, sdr_id, center_freq, sdr_source):
        self._sdr_id = sdr_id
        self._center_freq = center_freq
        self._sdr_source = sdr_source  # saved so start() can call getBuffer()
        self._iq_reader = None         # initialised here so stop() is safe before start()

        self._shift = Shift(0)
        self._decoder = EtiDecoder()

        # Large buffer between Shift and EtiDecoder — EtiDecoder needs big chunks to
        # maintain OFDM frame sync.
        self._shift_out = Buffer(Format.COMPLEX_FLOAT, size=2097152)
        self._shift.setWriter(self._shift_out)
        self._decoder.setReader(self._shift_out.getReader())

        # ETI output buffer — clients each get an independent reader via getEtiReader().
        # pycsdr.Buffer.getReader() creates an independent fan-out cursor (same mechanism
        # used by SpectrumThread in owrx/fft.py): each reader has its own position and
        # the buffer retains data until the slowest reader has consumed it.
        self._eti_buffer = Buffer(Format.CHAR)
        self._decoder.setWriter(self._eti_buffer)

        # MetaProcessor handles coarse/fine frequency correction by nudging the Shift
        # module. Import here to avoid circular import (MetaProcessor lives in dablin.py).
        from csdr.chain.dablin import MetaProcessor
        self._meta_buffer = Buffer(Format.CHAR)
        self._decoder.setMetaWriter(self._meta_buffer)
        self._processor = MetaProcessor(self._shift)
        self._processor.setReader(self._meta_buffer.getReader())
        self._processor.setWriter(Buffer(Format.CHAR))  # dummy — frequency correction only

    def start(self):
        """Connect to the SDR IQ buffer and begin OFDM demodulation."""
        self._iq_reader = self._sdr_source.getBuffer().getReader()
        self._shift.setReader(self._iq_reader)
        logger.info("SharedDabDecoder started — sdr=%s center_freq=%s Hz", self._sdr_id, self._center_freq)

    def stop(self):
        """Tear down the demodulation pipeline. Called when last client disconnects."""
        self._processor.stop()
        if self._iq_reader is not None:
            self._iq_reader.stop()
            self._iq_reader = None
        logger.info("SharedDabDecoder stopped — sdr=%s center_freq=%s Hz", self._sdr_id, self._center_freq)

    def getEtiReader(self):
        """Return a new independent reader into the shared ETI output buffer."""
        return self._eti_buffer.getReader()

    def getMetaReader(self):
        """Return a new independent reader into the shared meta buffer.
        Per-client MetaForwarder instances read from here to forward programme
        labels and service info to each client's meta WebSocket channel."""
        return self._meta_buffer.getReader()

    def getCachedMeta(self):
        """Return the last stable metadata snapshot captured by MetaProcessor.
        Used by Dablin.setMetaWriter() to replay programme/ensemble data to
        clients that connect after the initial FIC decode."""
        return dict(self._processor.cached_output)


class DabDecoderManager:
    """
    Singleton pool of SharedDabDecoder instances, keyed by (sdr_id, center_freq).

    Usage:
        shared = DabDecoderManager.getShared().acquire(sdr_id, center_freq, sdr_source)
        # ... use shared.getEtiReader() ...
        DabDecoderManager.getShared().release(sdr_id, center_freq)

    The first acquire() for a given key creates and starts the decoder.
    Each subsequent acquire() increments the refcount and returns the same decoder.
    The last release() stops and removes the decoder.
    """

    _instance = None
    _class_lock = threading.Lock()  # guards singleton creation only

    @classmethod
    def getShared(cls):
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = DabDecoderManager()
            return cls._instance

    def __init__(self):
        self._lock = threading.Lock()  # instance-level lock guards _decoders + _refcounts
        self._decoders = {}            # (sdr_id, center_freq) → SharedDabDecoder
        self._refcounts = {}           # (sdr_id, center_freq) → int

    def acquire(self, sdr_id, center_freq, sdr_source):
        """
        Return the shared decoder for this multiplex, creating it if necessary.
        Thread-safe. Increments refcount.
        """
        key = (sdr_id, center_freq)
        with self._lock:
            if key not in self._decoders:
                decoder = SharedDabDecoder(sdr_id, center_freq, sdr_source)
                decoder.start()
                self._decoders[key] = decoder
                self._refcounts[key] = 0
            self._refcounts[key] += 1
            logger.debug("DAB decoder acquired — key=%s refcount=%d", key, self._refcounts[key])
            return self._decoders[key]

    def release(self, sdr_id, center_freq):
        """
        Decrement refcount. Stops and removes the decoder when the last client releases.
        Thread-safe. Safe to call if key is not present (no-op).
        """
        key = (sdr_id, center_freq)
        with self._lock:
            if key not in self._refcounts:
                return
            self._refcounts[key] -= 1
            logger.debug("DAB decoder released — key=%s refcount=%d", key, self._refcounts[key])
            if self._refcounts[key] <= 0:
                self._decoders[key].stop()
                del self._decoders[key]
                del self._refcounts[key]
