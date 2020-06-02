from datetime import datetime, timezone
from owrx.map import Map, LocatorLocation
import re
from owrx.metrics import Metrics, CounterMetric
from owrx.pskreporter import PskReporter
from owrx.parser import Parser
from owrx.audio import AudioChopperProfile
from abc import ABC, ABCMeta, abstractmethod
from owrx.config import Config

import logging

logger = logging.getLogger(__name__)


class WsjtProfile(AudioChopperProfile, metaclass=ABCMeta):
    def decoding_depth(self, mode):
        pm = Config.get()
        # mode-specific setting?
        if "wsjt_decoding_depths" in pm and mode in pm["wsjt_decoding_depths"]:
            return pm["wsjt_decoding_depths"][mode]
        # return global default
        if "wsjt_decoding_depth" in pm:
            return pm["wsjt_decoding_depth"]
        # default when no setting is provided
        return 3


class Ft8Profile(WsjtProfile):
    def getInterval(self):
        return 15

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M%S"

    def decoder_commandline(self, file):
        return ["jt9", "--ft8", "-d", str(self.decoding_depth("ft8")), file]


class WsprProfile(WsjtProfile):
    def getInterval(self):
        return 120

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M"

    def decoder_commandline(self, file):
        cmd = ["wsprd"]
        if self.decoding_depth("wspr") > 1:
            cmd += ["-d"]
        cmd += [file]
        return cmd


class Jt65Profile(WsjtProfile):
    def getInterval(self):
        return 60

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M"

    def decoder_commandline(self, file):
        return ["jt9", "--jt65", "-d", str(self.decoding_depth("jt65")), file]


class Jt9Profile(WsjtProfile):
    def getInterval(self):
        return 60

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M"

    def decoder_commandline(self, file):
        return ["jt9", "--jt9", "-d", str(self.decoding_depth("jt9")), file]


class Ft4Profile(WsjtProfile):
    def getInterval(self):
        return 7.5

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M%S"

    def decoder_commandline(self, file):
        return ["jt9", "--ft4", "-d", str(self.decoding_depth("ft4")), file]


class WsjtParser(Parser):
    modes = {"~": "FT8", "#": "JT65", "@": "JT9", "+": "FT4"}

    def parse(self, messages):
        for data in messages:
            try:
                freq, raw_msg = data
                self.setDialFrequency(freq)
                msg = raw_msg.decode().rstrip()
                # known debug messages we know to skip
                if msg.startswith("<DecodeFinished>"):
                    return
                if msg.startswith(" EOF on input file"):
                    return

                modes = list(WsjtParser.modes.keys())
                if msg[21] in modes or msg[19] in modes:
                    decoder = Jt9Decoder()
                else:
                    decoder = WsprDecoder()
                out = decoder.parse(msg, freq)
                if "mode" in out:
                    self.pushDecode(out["mode"])
                    if "callsign" in out and "locator" in out:
                        Map.getSharedInstance().updateLocation(
                            out["callsign"], LocatorLocation(out["locator"]), out["mode"], self.band
                        )
                        PskReporter.getSharedInstance().spot(out)

                self.handler.write_wsjt_message(out)
            except ValueError:
                logger.exception("error while parsing wsjt message")

    def pushDecode(self, mode):
        metrics = Metrics.getSharedInstance()
        band = "unknown"
        if self.band is not None:
            band = self.band.getName()
        if band is None:
            band = "unknown"

        if mode is None:
            mode = "unknown"

        name = "wsjt.decodes.{band}.{mode}".format(band=band, mode=mode)
        metric = metrics.getMetric(name)
        if metric is None:
            metric = CounterMetric()
            metrics.addMetric(name, metric)

        metric.inc()


class Decoder(ABC):
    def parse_timestamp(self, instring, dateformat):
        ts = datetime.strptime(instring, dateformat)
        return int(
            datetime.combine(datetime.utcnow().date(), ts.time()).replace(tzinfo=timezone.utc).timestamp() * 1000
        )

    @abstractmethod
    def parse(self, msg, dial_freq):
        pass


class Jt9Decoder(Decoder):
    locator_pattern = re.compile("[A-Z0-9]+\\s([A-Z0-9]+)\\s([A-R]{2}[0-9]{2})$")

    def parse(self, msg, dial_freq):
        # ft8 sample
        # '222100 -15 -0.0  508 ~  CQ EA7MJ IM66'
        # jt65 sample
        # '2352  -7  0.4 1801 #  R0WAS R2ABM KO85'
        # '0003  -4  0.4 1762 #  CQ R2ABM KO85'
        modes = list(WsjtParser.modes.keys())
        if msg[19] in modes:
            dateformat = "%H%M"
        else:
            dateformat = "%H%M%S"
        timestamp = self.parse_timestamp(msg[0 : len(dateformat)], dateformat)
        msg = msg[len(dateformat) + 1 :]
        modeChar = msg[14:15]
        mode = WsjtParser.modes[modeChar] if modeChar in WsjtParser.modes else "unknown"
        wsjt_msg = msg[17:53].strip()

        result = {
            "timestamp": timestamp,
            "db": float(msg[0:3]),
            "dt": float(msg[4:8]),
            "freq": dial_freq + int(msg[9:13]),
            "mode": mode,
            "msg": wsjt_msg,
        }
        result.update(self.parseMessage(wsjt_msg))
        return result

    def parseMessage(self, msg):
        m = Jt9Decoder.locator_pattern.match(msg)
        if m is None:
            return {}
        # this is a valid locator in theory, but it's somewhere in the arctic ocean, near the north pole, so it's very
        # likely this just means roger roger goodbye.
        if m.group(2) == "RR73":
            return {"callsign": m.group(1)}
        return {"callsign": m.group(1), "locator": m.group(2)}


class WsprDecoder(Decoder):
    wspr_splitter_pattern = re.compile("([A-Z0-9]*)\\s([A-R]{2}[0-9]{2})\\s([0-9]+)")

    def parse(self, msg, dial_freq):
        # wspr sample
        # '2600 -24  0.4   0.001492 -1  G8AXA JO01 33'
        # '0052 -29  2.6   0.001486  0  G02CWT IO92 23'
        wsjt_msg = msg[29:].strip()
        result = {
            "timestamp": self.parse_timestamp(msg[0:4], "%H%M"),
            "db": float(msg[5:8]),
            "dt": float(msg[9:13]),
            "freq": dial_freq + int(float(msg[14:24]) * 1e6),
            "drift": int(msg[25:28]),
            "mode": "WSPR",
            "msg": wsjt_msg,
        }
        result.update(self.parseMessage(wsjt_msg))
        return result

    def parseMessage(self, msg):
        m = WsprDecoder.wspr_splitter_pattern.match(msg)
        if m is None:
            return {}
        return {"callsign": m.group(1), "locator": m.group(2)}
