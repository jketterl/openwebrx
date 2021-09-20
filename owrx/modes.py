from owrx.feature import FeatureDetector
from owrx.audio import ProfileSource
from functools import reduce
from abc import ABCMeta, abstractmethod


class Bandpass(object):
    def __init__(self, low_cut, high_cut):
        self.low_cut = low_cut
        self.high_cut = high_cut


class Mode(object):
    def __init__(self, modulation, name, bandpass: Bandpass = None, requirements=None, service=False, squelch=True):
        self.modulation = modulation
        self.name = name
        self.requirements = requirements if requirements is not None else []
        self.service = service
        self.bandpass = bandpass
        self.squelch = squelch

    def is_available(self):
        fd = FeatureDetector()
        return reduce(lambda a, b: a and b, [fd.is_available(r) for r in self.requirements], True)

    def is_service(self):
        return self.service

    def get_bandpass(self):
        return self.bandpass

    def get_modulation(self):
        return self.modulation


class AnalogMode(Mode):
    pass


class DigitalMode(Mode):
    def __init__(
        self, modulation, name, underlying, bandpass: Bandpass = None, requirements=None, service=False, squelch=True
    ):
        super().__init__(modulation, name, bandpass, requirements, service, squelch)
        self.underlying = underlying

    def get_bandpass(self):
        if self.bandpass is not None:
            return self.bandpass
        return Modes.findByModulation(self.underlying[0]).get_bandpass()

    def get_modulation(self):
        return Modes.findByModulation(self.underlying[0]).get_modulation()


class AudioChopperMode(DigitalMode, metaclass=ABCMeta):
    def __init__(self, modulation, name, bandpass=None, requirements=None):
        if bandpass is None:
            bandpass = Bandpass(0, 3000)
        super().__init__(modulation, name, ["usb"], bandpass=bandpass, requirements=requirements, service=True)

    @abstractmethod
    def get_profile_source(self) -> ProfileSource:
        pass


class WsjtMode(AudioChopperMode):
    def __init__(self, modulation, name, bandpass=None, requirements=None):
        if requirements is None:
            requirements = ["wsjt-x"]
        super().__init__(modulation, name, bandpass=bandpass, requirements=requirements)

    def get_profile_source(self) -> ProfileSource:
        # inline import due to circular dependencies
        from owrx.wsjt import WsjtProfiles
        return WsjtProfiles.getSource(self.modulation)


class Js8Mode(AudioChopperMode):
    def __init__(self, modulation, name, bandpass=None, requirements=None):
        if requirements is None:
            requirements = ["js8call"]
        super().__init__(modulation, name, bandpass, requirements)

    def get_profile_source(self) -> ProfileSource:
        # inline import due to circular dependencies
        from owrx.js8 import Js8ProfileSource
        return Js8ProfileSource()


class Modes(object):
    mappings = [
        AnalogMode("nfm", "FM", bandpass=Bandpass(-4000, 4000)),
        AnalogMode("wfm", "WFM", bandpass=Bandpass(-75000, 75000)),
        AnalogMode("am", "AM", bandpass=Bandpass(-4000, 4000)),
        AnalogMode("lsb", "LSB", bandpass=Bandpass(-3000, -100)),
        AnalogMode("usb", "USB", bandpass=Bandpass(100, 3000)),
        AnalogMode("cw", "CW", bandpass=Bandpass(700, 900)),
        AnalogMode("dmr", "DMR", bandpass=Bandpass(-4000, 4000), requirements=["digital_voice_digiham"], squelch=False),
        AnalogMode(
            "dstar", "D-Star", bandpass=Bandpass(-3250, 3250), requirements=["digital_voice_digiham"], squelch=False
        ),
        AnalogMode("nxdn", "NXDN", bandpass=Bandpass(-3250, 3250), requirements=["digital_voice_digiham"], squelch=False),
        AnalogMode("ysf", "YSF", bandpass=Bandpass(-4000, 4000), requirements=["digital_voice_digiham"], squelch=False),
        AnalogMode("m17", "M17", bandpass=Bandpass(-4000, 4000), requirements=["digital_voice_m17"], squelch=False),
        AnalogMode(
            "freedv", "FreeDV", bandpass=Bandpass(300, 3000), requirements=["digital_voice_freedv"], squelch=False
        ),
        AnalogMode("drm", "DRM", bandpass=Bandpass(-5000, 5000), requirements=["drm"], squelch=False),
        DigitalMode("bpsk31", "BPSK31", underlying=["usb"]),
        DigitalMode("bpsk63", "BPSK63", underlying=["usb"]),
        WsjtMode("ft8", "FT8"),
        WsjtMode("ft4", "FT4"),
        WsjtMode("jt65", "JT65"),
        WsjtMode("jt9", "JT9"),
        WsjtMode("wspr", "WSPR", bandpass=Bandpass(1350, 1650)),
        WsjtMode("fst4", "FST4", requirements=["wsjt-x-2-3"]),
        WsjtMode("fst4w", "FST4W", bandpass=Bandpass(1350, 1650), requirements=["wsjt-x-2-3"]),
        WsjtMode("q65", "Q65", requirements=["wsjt-x-2-4"]),
        Js8Mode("js8", "JS8Call"),
        DigitalMode(
            "packet",
            "Packet",
            underlying=["nfm", "usb", "lsb"],
            bandpass=Bandpass(-6250, 6250),
            requirements=["packet"],
            service=True,
            squelch=False,
        ),
        DigitalMode(
            "pocsag",
            "Pocsag",
            underlying=["nfm"],
            bandpass=Bandpass(-6000, 6000),
            requirements=["pocsag"],
            squelch=False,
        ),
    ]

    @staticmethod
    def getModes():
        return Modes.mappings

    @staticmethod
    def getAvailableModes():
        return [m for m in Modes.getModes() if m.is_available()]

    @staticmethod
    def getAvailableServices():
        return [m for m in Modes.getAvailableModes() if m.is_service()]

    @staticmethod
    def findByModulation(modulation):
        modes = [m for m in Modes.getAvailableModes() if m.modulation == modulation]
        if modes:
            return modes[0]
