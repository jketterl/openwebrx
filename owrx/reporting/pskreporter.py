import logging
import threading
import time
import random
import socket
from functools import reduce
from operator import and_
from owrx.config import Config
from owrx.version import openwebrx_version
from owrx.locator import Locator
from owrx.metrics import Metrics, CounterMetric
from owrx.reporting.reporter import FilteredReporter

logger = logging.getLogger(__name__)


class PskReporter(FilteredReporter):
    """
    This class implements the reporting interface to send received signals to pskreporter.info.

    It interfaces with pskreporter as documented here: https://pskreporter.info/pskdev.html
    """
    interval = 300

    def getSupportedModes(self):
        """
        Supports all valid MODE and SUBMODE values from the ADIF standard.

        Current version at the time of the last change:
        https://www.adif.org/314/ADIF_314.htm#Mode_Enumeration
        """
        return ["FT8", "FT4", "JT9", "JT4", "JT65", "FST4", "JS8", "Q65", "WSPR", "FST4W", "MSK144"]

    def stop(self):
        self.cancelTimer()
        with self.spotLock:
            self.spots = []

    def __init__(self):
        self.spots = []
        self.spotLock = threading.Lock()
        self.uploader = Uploader()
        self.timer = None
        metrics = Metrics.getSharedInstance()
        self.dupeCounter = CounterMetric()
        metrics.addMetric("pskreporter.duplicates", self.dupeCounter)
        self.spotCounter = CounterMetric()
        metrics.addMetric("pskreporter.spots", self.spotCounter)

    def scheduleNextUpload(self):
        if self.timer:
            return
        delay = PskReporter.interval + random.uniform(0, 30)
        logger.debug("scheduling next pskreporter upload in %f seconds", delay)
        self.timer = threading.Timer(delay, self.upload)
        self.timer.start()

    def spotEquals(self, s1, s2):
        keys = ["source", "timestamp", "locator", "mode", "msg"]

        return reduce(and_, map(lambda key: s1[key] == s2[key], keys))

    def spot(self, spot):
        with self.spotLock:
            if any(x for x in self.spots if self.spotEquals(spot, x)):
                # dupe
                self.dupeCounter.inc()
            else:
                self.spotCounter.inc()
                self.spots.append(spot)
            self.scheduleNextUpload()

    def upload(self):
        try:
            with self.spotLock:
                self.timer = None
                spots = self.spots
                self.spots = []

            if spots:
                self.uploader.upload(spots)
        except Exception:
            logger.exception("Failed to upload spots")

    def cancelTimer(self):
        if self.timer:
            self.timer.cancel()


class Uploader(object):
    receieverDelimiter = [0x99, 0x92]
    senderDelimiter = [0x99, 0x93]

    def __init__(self):
        self.sequence = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def upload(self, spots):
        logger.debug("uploading %i spots", len(spots))
        for packet in self.getPackets(spots):
            self.socket.sendto(packet, ("report.pskreporter.info", 4739))

    def getPackets(self, spots):
        encoded = [self.encodeSpot(spot) for spot in spots]
        # filter out any erroneous encodes
        encoded = [e for e in encoded if e is not None]

        def chunks(block, max_size):
            size = 0
            current = []
            for r in block:
                if size + len(r) > max_size:
                    yield current
                    current = []
                    size = 0
                size += len(r)
                current.append(r)
            yield current

        rHeader = self.getReceiverInformationHeader()
        rInfo = self.getReceiverInformation()
        sHeader = self.getSenderInformationHeader()

        packets = []
        # 1200 bytes of sender data should keep the packet size below MTU for most cases
        for chunk in chunks(encoded, 1200):
            sInfo = self.getSenderInformation(chunk)
            length = 16 + len(rHeader) + len(sHeader) + len(rInfo) + len(sInfo)
            header = self.getHeader(length)
            packets.append(header + rHeader + sHeader + rInfo + sInfo)
            self.sequence = (self.sequence + len(chunk)) % (1 << 32)

        return packets

    def getHeader(self, length):
        return bytes(
            # protocol version
            [0x00, 0x0A]
            + list(length.to_bytes(2, "big"))
            + list(int(time.time()).to_bytes(4, "big"))
            + list(self.sequence.to_bytes(4, "big"))
            + list((id(self) & 0xFFFFFFFF).to_bytes(4, "big"))
        )

    def encodeString(self, s):
        return [len(s)] + list(s.encode("utf-8"))

    def encodeSpot(self, spot):
        try:
            return bytes(
                self.encodeString(spot["source"]["callsign"])
                + list(int(spot["freq"]).to_bytes(5, "big"))
                + list(int(spot["db"]).to_bytes(1, "big", signed=True))
                + self.encodeString(spot["mode"])
                + self.encodeString(spot["locator"])
                # informationsource. 1 means "automatically extracted
                + [0x01]
                + list(int(spot["timestamp"] / 1000).to_bytes(4, "big"))
            )
        except Exception:
            logger.exception("Error while encoding spot for pskreporter")
            return None

    def getReceiverInformationHeader(self):
        pm = Config.get()
        with_antenna = "pskreporter_antenna_information" in pm and pm["pskreporter_antenna_information"] is not None
        num_fields = 4 if with_antenna else 3
        length = 12 + num_fields * 8
        return bytes(
            # id
            [0x00, 0x03]
            # length
            + list(length.to_bytes(2, "big"))
            + Uploader.receieverDelimiter
            # number of fields
            + list(num_fields.to_bytes(2, "big"))
            # scoped field count
            + [0x00, 0x01]
            # receiverCallsign
            + [0x80, 0x02, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F]
            # receiverLocator
            + [0x80, 0x04, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F]
            # decodingSoftware
            + [0x80, 0x08, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F]
            # antennaInformation
            + ([0x80, 0x09, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F] if with_antenna else [])
            # padding
            + [0x00, 0x00]
        )

    def getReceiverInformation(self):
        pm = Config.get()
        bodyFields = [
            # callsign
            pm["pskreporter_callsign"],
            # locator
            Locator.fromCoordinates(pm["receiver_gps"]),
            # decodingSoftware
            "OpenWebRX " + openwebrx_version,
        ]
        if "pskreporter_antenna_information" in pm and pm["pskreporter_antenna_information"] is not None:
            bodyFields += [pm["pskreporter_antenna_information"]]
        body = [b for s in bodyFields for b in self.encodeString(s)]
        body = self.pad(body, 4)
        body = bytes(Uploader.receieverDelimiter + list((len(body) + 4).to_bytes(2, "big")) + body)
        return body

    def getSenderInformationHeader(self):
        return bytes(
            # id, length
            [0x00, 0x02, 0x00, 0x3C]
            + Uploader.senderDelimiter
            # number of fields
            + [0x00, 0x07]
            # senderCallsign
            + [0x80, 0x01, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F]
            # frequency
            + [0x80, 0x05, 0x00, 0x05, 0x00, 0x00, 0x76, 0x8F]
            # sNR
            + [0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x76, 0x8F]
            # mode
            + [0x80, 0x0A, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F]
            # senderLocator
            + [0x80, 0x03, 0xFF, 0xFF, 0x00, 0x00, 0x76, 0x8F]
            # informationSource
            + [0x80, 0x0B, 0x00, 0x01, 0x00, 0x00, 0x76, 0x8F]
            # flowStartSeconds
            + [0x00, 0x96, 0x00, 0x04]
        )

    def getSenderInformation(self, chunk):
        sInfo = self.padBytes(b"".join(chunk), 4)
        sInfoLength = len(sInfo) + 4
        return bytes(Uploader.senderDelimiter) + sInfoLength.to_bytes(2, "big") + sInfo

    def pad(self, b, l):
        return b + [0x00 for _ in range(0, -1 * len(b) % l)]

    def padBytes(self, b, l):
        return b + bytes([0x00 for _ in range(0, -1 * len(b) % l)])
