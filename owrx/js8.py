from .audio import AudioChopperProfile
from .parser import Parser
import re
from js8py import Js8
from js8py.frames import Js8FrameHeartbeat, Js8FrameCompound
from .map import Map, LocatorLocation
from .pskreporter import PskReporter
from .metrics import Metrics, CounterMetric
from .config import Config
from abc import ABCMeta, abstractmethod

import logging

logger = logging.getLogger(__name__)


class Js8Profiles(object):
    @staticmethod
    def getEnabledProfiles():
        config = Config.get()
        profiles = config["js8_enabled_profiles"] if "js8_enabled_profiles" in config else []
        return [Js8Profiles.loadProfile(p) for p in profiles]

    @staticmethod
    def loadProfile(profileName):
        className = "Js8{0}Profile".format(profileName[0].upper() + profileName[1:].lower())
        return globals()[className]()


class Js8Profile(AudioChopperProfile, metaclass=ABCMeta):
    def decoding_depth(self, mode):
        pm = Config.get()
        # return global default
        if "js8_decoding_depth" in pm:
            return pm["js8_decoding_depth"]
        # default when no setting is provided
        return 3

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M%S"

    def decoder_commandline(self, file):
        return ["js8", "--js8", "-b", self.get_sub_mode(), "-d", str(self.decoding_depth("js8")), file]

    @abstractmethod
    def get_sub_mode(self):
        pass


class Js8NormalProfile(Js8Profile):
    def getInterval(self):
        return 15

    def get_sub_mode(self):
        return "A"


class Js8SlowProfile(Js8Profile):
    def getInterval(self):
        return 30

    def get_sub_mode(self):
        return "E"


class Js8FastProfile(Js8Profile):
    def getInterval(self):
        return 10

    def get_sub_mode(self):
        return "B"


class Js8TurboProfile(Js8Profile):
    def getInterval(self):
        return 6

    def get_sub_mode(self):
        return "C"


class Js8Parser(Parser):
    decoderRegex = re.compile(" ?<Decode(Started|Debug|Finished)>")

    def parse(self, messages):
        for raw in messages:
            try:
                freq, raw_msg = raw
                self.setDialFrequency(freq)
                msg = raw_msg.decode().rstrip()
                if Js8Parser.decoderRegex.match(msg):
                    return
                if msg.startswith(" EOF on input file"):
                    return

                frame = Js8().parse_message(msg)
                self.handler.write_js8_message(frame, self.dial_freq)

                self.pushDecode()

                if (isinstance(frame, Js8FrameHeartbeat) or isinstance(frame, Js8FrameCompound)) and frame.grid:
                    Map.getSharedInstance().updateLocation(
                        frame.callsign, LocatorLocation(frame.grid), "JS8", self.band
                    )
                    PskReporter.getSharedInstance().spot({
                        "callsign": frame.callsign,
                        "mode": "JS8",
                        "locator": frame.grid,
                        "freq": self.dial_freq + frame.freq,
                        "db": frame.db,
                        "timestamp": frame.timestamp,
                        "msg": str(frame)
                    })

            except Exception:
                logger.exception("error while parsing js8 message")

    def pushDecode(self):
        metrics = Metrics.getSharedInstance()
        band = "unknown"
        if self.band is not None:
            band = self.band.getName()
        if band is None:
            band = "unknown"

        name = "js8call.decodes.{band}.JS8".format(band=band)
        metric = metrics.getMetric(name)
        if metric is None:
            metric = CounterMetric()
            metrics.addMetric(name, metric)

        metric.inc()
