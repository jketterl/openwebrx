from datetime import datetime, timezone
from typing import List
from owrx.map import Map, LocatorLocation, CallsignSource
from owrx.metrics import Metrics, CounterMetric
from owrx.reporting import ReportingEngine
from owrx.audio import AudioChopperProfile, StaticProfileSource, ConfigWiredProfileSource
from owrx.audio.chopper import AudioChopperParser
from abc import ABC, ABCMeta, abstractmethod
from owrx.config import Config
from enum import Enum
from owrx.bands import Bandplan
import re

import logging

logger = logging.getLogger(__name__)


class WsjtProfile(AudioChopperProfile, metaclass=ABCMeta):
    def decoding_depth(self):
        pm = Config.get()
        mode = self.getMode().lower()
        # mode-specific setting?
        if "wsjt_decoding_depths" in pm and mode in pm["wsjt_decoding_depths"]:
            return pm["wsjt_decoding_depths"][mode]
        # return global default
        if "wsjt_decoding_depth" in pm:
            return pm["wsjt_decoding_depth"]
        # default when no setting is provided
        return 3

    def getTimestampFormat(self):
        if self.getInterval() < 60:
            return "%H%M%S"
        return "%H%M"

    def getFileTimestampFormat(self):
        return "%y%m%d_" + self.getTimestampFormat()

    @abstractmethod
    def getMode(self):
        pass


class Fst4ProfileSource(ConfigWiredProfileSource):
    def getPropertiesToWire(self) -> List[str]:
        return ["fst4_enabled_intervals"]

    def getProfiles(self) -> List[AudioChopperProfile]:
        config = Config.get()
        profiles = config["fst4_enabled_intervals"] if "fst4_enabled_intervals" in config else []
        return [Fst4Profile(i) for i in profiles if i in Fst4Profile.availableIntervals]


class Fst4wProfileSource(ConfigWiredProfileSource):
    def getPropertiesToWire(self) -> List[str]:
        return ["fst4w_enabled_intervals"]

    def getProfiles(self) -> List[AudioChopperProfile]:
        config = Config.get()
        profiles = config["fst4w_enabled_intervals"] if "fst4w_enabled_intervals" in config else []
        return [Fst4wProfile(i) for i in profiles if i in Fst4wProfile.availableIntervals]


class JT4ProfileSource(ConfigWiredProfileSource):
    def getPropertiesToWire(self) -> List[str]:
        return ["jt4_enabled_submodes"]

    def getProfiles(self) -> List[AudioChopperProfile]:
        config = Config.get()
        profiles = config["jt4_enabled_submodes"] if "jt4_enabled_submodes" in config else []
        return [JT4Profile(i) for i in profiles if i in JT4Profile.availableSubmodes]

class Q65ProfileSource(ConfigWiredProfileSource):
    def getPropertiesToWire(self) -> List[str]:
        return ["q65_enabled_combinations"]

    def getProfiles(self) -> List[AudioChopperProfile]:
        config = Config.get()
        profiles = config["q65_enabled_combinations"] if "q65_enabled_combinations" in config else []

        def buildProfile(modestring):
            try:
                mode = Q65Mode[modestring[0]]
                interval = Q65Interval(int(modestring[1:]))
                if interval.is_available(mode):
                    return Q65Profile(interval, mode)
            except (ValueError, KeyError):
                pass
            logger.warning('"%s" is not a valid Q65 mode, or an invalid mode string, ignoring', modestring)
            return None

        mapped = [buildProfile(m) for m in profiles]
        return [p for p in mapped if p is not None]


class WsjtProfiles(object):
    @staticmethod
    def getSource(mode: str):
        if mode == "ft8":
            return StaticProfileSource([Ft8Profile()])
        elif mode == "wspr":
            return StaticProfileSource([WsprProfile()])
        elif mode == "jt65":
            return StaticProfileSource([Jt65Profile()])
        elif mode == "jt9":
            return StaticProfileSource([Jt9Profile()])
        elif mode == "ft4":
            return StaticProfileSource([Ft4Profile()])
        elif mode == "fst4":
            return Fst4ProfileSource()
        elif mode == "fst4w":
            return Fst4wProfileSource()
        elif mode == "jt4":
            return JT4ProfileSource()
        elif mode == "q65":
            return Q65ProfileSource()


class Ft8Profile(WsjtProfile):
    def getInterval(self):
        return 15

    def decoder_commandline(self, file):
        return ["jt9", "--ft8", "-d", str(self.decoding_depth()), file]

    def getMode(self):
        return "FT8"


class WsprProfile(WsjtProfile):
    def getInterval(self):
        return 120

    def decoder_commandline(self, file):
        cmd = ["wsprd"]
        if self.decoding_depth() > 1:
            cmd += ["-d"]
        cmd += [file]
        return cmd

    def getMode(self):
        return "WSPR"


class Jt65Profile(WsjtProfile):
    def getInterval(self):
        return 60

    def decoder_commandline(self, file):
        return ["jt9", "--jt65", "-d", str(self.decoding_depth()), file]

    def getMode(self):
        return "JT65"


class Jt9Profile(WsjtProfile):
    def getInterval(self):
        return 60

    def decoder_commandline(self, file):
        return ["jt9", "--jt9", "-d", str(self.decoding_depth()), file]

    def getMode(self):
        return "JT9"


class Ft4Profile(WsjtProfile):
    def getInterval(self):
        return 7.5

    def decoder_commandline(self, file):
        return ["jt9", "--ft4", "-d", str(self.decoding_depth()), file]

    def getMode(self):
        return "FT4"


class Fst4Profile(WsjtProfile):
    availableIntervals = [15, 30, 60, 120, 300, 900, 1800]

    def __init__(self, interval):
        self.interval = interval

    def getInterval(self):
        return self.interval

    def decoder_commandline(self, file):
        return ["jt9", "--fst4", "-p", str(self.interval), "-d", str(self.decoding_depth()), file]

    def getMode(self):
        return "FST4"


class Fst4wProfile(WsjtProfile):
    availableIntervals = [120, 300, 900, 1800]

    def __init__(self, interval):
        self.interval = interval

    def getInterval(self):
        return self.interval

    def decoder_commandline(self, file):
        return ["jt9", "--fst4w", "-p", str(self.interval), "-d", str(self.decoding_depth()), file]

    def getMode(self):
        return "FST4W"


class JT4Profile(WsjtProfile):
    availableSubmodes = ["A", "B", "C", "D", "E", "F", "G"]

    def __init__(self, submode):
        self.submode = submode

    def getInterval(self):
        return 60

    def frequency_tolerance(self):
        config = Config.get()
        if "jt4_frequency_tolerance" in config:
            return config["jt4_frequency_tolerance"]
        # default when no setting is provided
        return 20

    def decoder_commandline(self, file):
        return ["jt9", "-4", "-b", str(self.submode), "-d", str(self.decoding_depth()), "-F", str(self.frequency_tolerance()), file]

    def getMode(self):
        return "JT4"


class Q65Mode(Enum):
    # value is the bandwidth multiplier according to https://physics.princeton.edu/pulsar/k1jt/Q65_Quick_Start.pdf
    A = 1
    B = 2
    C = 4
    D = 8
    E = 16

    def is_available(self, interval: "Q65Interval"):
        return interval.is_available(self)


class Q65Interval(Enum):
    # (interval, occupied bandwidth in mode "A")
    # according to https://physics.princeton.edu/pulsar/k1jt/Q65_Quick_Start.pdf
    INTERVAL_15 = (15, 433)
    INTERVAL_30 = (30, 217)
    INTERVAL_60 = (60, 108)
    INTERVAL_120 = (120, 49)
    INTERVAL_300 = (300, 19)

    def __new__(cls, *args, **kwargs):
        interval, occupied_bandwidth = args
        obj = object.__new__(cls)
        obj._value_ = interval
        obj.occupied_bandwidth = occupied_bandwidth
        return obj

    def is_available(self, mode: Q65Mode):
        # total bandwidth must not exceed the typical SSB bandwidth
        return self.occupied_bandwidth * mode.value < 2700


class Q65Profile(WsjtProfile):
    def __init__(self, interval: Q65Interval, mode: Q65Mode):
        self.interval = interval.value
        self.mode = mode

    def getMode(self):
        return "Q65"

    def getInterval(self):
        return self.interval

    def decoder_commandline(self, file):
        return ["jt9", "--q65", "-p", str(self.interval), "-b", self.mode.name, "-d", str(self.decoding_depth()), file]


class Msk144Profile(WsjtProfile):
    def getMode(self):
        return "MSK144"

    def getInterval(self):
        return 15

    def decoder_commandline(self, file):
        return None


class WsjtParser(AudioChopperParser):
    def parse(self, profile: WsjtProfile, freq: int, raw_msg: bytes):
        try:
            band = None
            if freq is not None:
                band = Bandplan.getSharedInstance().findBand(freq)

            msg = raw_msg.decode().rstrip()
            # known debug messages we know to skip
            if msg.startswith("<DecodeFinished>"):
                return
            if msg.startswith(" EOF on input file"):
                return

            mode = profile.getMode()
            if mode in ["JT4"] and (msg.endswith("$*") or msg.endswith("$#")):
                return
            if mode in ["WSPR", "FST4W"]:
                messageParser = BeaconMessageParser()
            else:
                messageParser = QsoMessageParser()
            if mode == "WSPR":
                decoder = WsprDecoder(profile, messageParser)
            else:
                decoder = Jt9Decoder(profile, messageParser)
            out = decoder.parse(msg, freq)
            if isinstance(profile, Q65Profile) and not out["msg"]:
                # all efforts in vain, it's just a potential signal indicator
                return
            out["mode"] = mode
            out["interval"] = profile.getInterval()

            self.pushDecode(mode, band)
            if "source" in out and "locator" in out:
                Map.getSharedInstance().updateLocation(
                    CallsignSource(**out["source"]), LocatorLocation(out["locator"]), mode, band
                )
                ReportingEngine.getSharedInstance().spot(out)

            return out
        except Exception:
            logger.exception("Exception while parsing wsjt message")

    def pushDecode(self, mode, band):
        metrics = Metrics.getSharedInstance()
        bandName = "unknown"
        if band is not None:
            bandName = band.getName()

        if mode is None:
            mode = "unknown"

        name = "wsjt.decodes.{band}.{mode}".format(band=bandName, mode=mode)
        metric = metrics.getMetric(name)
        if metric is None:
            metric = CounterMetric()
            metrics.addMetric(name, metric)

        metric.inc()


class Decoder(ABC):
    def __init__(self, profile, messageParser):
        self.profile = profile
        self.messageParser = messageParser

    def parse_timestamp(self, instring):
        dateformat = self.profile.getTimestampFormat()
        remain = instring[len(dateformat) + 1:]
        try:
            ts = datetime.strptime(instring[0: len(dateformat)], dateformat)
            return remain, int(
                datetime.combine(datetime.utcnow().date(), ts.time()).replace(tzinfo=timezone.utc).timestamp() * 1000
            )
        except ValueError:
            return remain, None

    @abstractmethod
    def parse(self, msg, dial_freq):
        pass


class MessageParser(ABC):
    @abstractmethod
    def parse(self, msg):
        pass


# Used in QSO-style modes (FT8, FT4, FST4)
class QsoMessageParser(MessageParser):
    locator_pattern = re.compile(".*\\s([A-Z0-9/]{2,})(\\sR)?\\s([A-R]{2}[0-9]{2})$")

    def parse(self, msg):
        m = QsoMessageParser.locator_pattern.match(msg)
        if m is None:
            return {}
        # this is a valid locator in theory, but it's somewhere in the arctic ocean, near the north pole, so it's very
        # likely this just means roger roger goodbye.
        if m.group(3) == "RR73":
            return {"source": {"callsign": m.group(1)}}
        return {"source": {"callsign": m.group(1)}, "locator": m.group(3)}


# Used in propagation reporting / beacon modes (WSPR / FST4W)
class BeaconMessageParser(MessageParser):
    wspr_splitter_pattern = re.compile("([A-Z0-9/]*)\\s([A-R]{2}[0-9]{2})\\s([0-9]+)")

    def parse(self, msg):
        m = BeaconMessageParser.wspr_splitter_pattern.match(msg)
        if m is None:
            return {}
        return {"source": {"callsign": m.group(1)}, "locator": m.group(2), "dbm": m.group(3)}


class Jt9Decoder(Decoder):
    def parse(self, msg, dial_freq):
        # ft8 sample
        # '222100 -15 -0.0  508 ~  CQ EA7MJ IM66'
        # jt65 sample
        # '2352  -7  0.4 1801 #  R0WAS R2ABM KO85'
        # '0003  -4  0.4 1762 #  CQ R2ABM KO85'
        # fst4 sample
        # '**** -23  0.6 3023 `  <...> <...> R 591631 BI53PV'
        # MSK144 sample
        # '221602   8  0.4 1488 &  K1JT WA4CQG EM72'
        msg, timestamp = self.parse_timestamp(msg)
        wsjt_msg = msg[17:53].strip()

        result = {
            "timestamp": timestamp,
            "db": float(msg[0:3]),
            "dt": float(msg[4:8]),
            "freq": dial_freq + int(msg[9:13]),
            "msg": wsjt_msg,
        }
        result.update(self.messageParser.parse(wsjt_msg))
        return result


class WsprDecoder(Decoder):
    def parse(self, msg, dial_freq):
        # wspr sample
        # '2600 -24  0.4   0.001492 -1  G8AXA JO01 33'
        # '0052 -29  2.6   0.001486  0  G02CWT IO92 23'
        msg, timestamp = self.parse_timestamp(msg)
        wsjt_msg = msg[24:].strip()
        result = {
            "timestamp": timestamp,
            "db": float(msg[0:3]),
            "dt": float(msg[4:8]),
            "freq": dial_freq + int(float(msg[10:20]) * 1e6),
            "drift": int(msg[20:23]),
            "msg": wsjt_msg,
        }
        result.update(self.messageParser.parse(wsjt_msg))
        return result
