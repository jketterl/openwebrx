import threading
from owrx.source import SdrSourceEventClient, SdrSourceState, SdrClientClass
from owrx.sdr import SdrService
from owrx.bands import Bandplan
from owrx.config import Config
from owrx.source.resampler import Resampler
from owrx.property import PropertyLayer, PropertyDeleted
from owrx.service.schedule import ServiceScheduler
from owrx.service.chain import ServiceDemodulatorChain
from owrx.modes import Modes, DigitalMode
from typing import Union, Optional
from csdr.chain.demodulator import BaseDemodulatorChain, ServiceDemodulator, DialFrequencyReceiver
from pycsdr.modules import Buffer

import logging

logger = logging.getLogger(__name__)


class ServiceHandler(SdrSourceEventClient):
    def __init__(self, source):
        self.lock = threading.RLock()
        self.services = []
        self.source = source
        self.startupTimer = None
        self.activitySub = None
        self.running = False
        props = self.source.getProps()
        self.enabledSub = props.wireProperty("services", self._receiveEvent)
        self.decodersSub = None
        # need to call _start() manually if property is not set since the default is True, but the initial call is only
        # made if the property is present
        if "services" not in props:
            self._start()

    def _receiveEvent(self, state):
        # deletion means fall back to default, which is True
        if state is PropertyDeleted:
            state = True
        if self.running == state:
            return
        if state:
            self._start()
        else:
            self._stop()

    def _start(self):
        self.running = True
        self.source.addClient(self)
        props = self.source.getProps()
        self.activitySub = props.filter("center_freq", "samp_rate").wire(self.onFrequencyChange)
        self.decodersSub = Config.get().wireProperty("services_decoders", self.onFrequencyChange)
        if self.source.isAvailable():
            self._scheduleServiceStartup()

    def _stop(self):
        if self.activitySub is not None:
            self.activitySub.cancel()
            self.activitySub = None
        if self.decodersSub is not None:
            self.decodersSub.cancel()
            self.decodersSub = None
        self._cancelStartupTimer()
        self.source.removeClient(self)
        self.stopServices()
        self.running = False

    def getClientClass(self) -> SdrClientClass:
        return SdrClientClass.INACTIVE

    def onStateChange(self, state: SdrSourceState):
        if state is SdrSourceState.RUNNING:
            self._scheduleServiceStartup()
        elif state is SdrSourceState.STOPPING:
            logger.debug("sdr source becoming unavailable; stopping services.")
            self.stopServices()

    def onFail(self):
        logger.debug("sdr source failed; stopping services.")
        self.stopServices()

    def onShutdown(self):
        logger.debug("sdr source is shutting down; shutting down service handler, too.")
        self.shutdown()

    def onEnable(self):
        self._scheduleServiceStartup()

    def isSupported(self, mode):
        configured = Config.get()["services_decoders"]
        available = [m.modulation for m in Modes.getAvailableServices()]
        return mode in configured and mode in available

    def shutdown(self):
        self._stop()
        if self.enabledSub is not None:
            self.enabledSub.cancel()
            self.enabledSub = None

    def stopServices(self):
        with self.lock:
            services = self.services
            self.services = []

        for service in services:
            service.stop()

    def onFrequencyChange(self, changes):
        self.stopServices()
        if not self.source.isAvailable():
            return
        self._scheduleServiceStartup()

    def _cancelStartupTimer(self):
        if self.startupTimer:
            self.startupTimer.cancel()
            self.startupTimer = None

    def _scheduleServiceStartup(self):
        self._cancelStartupTimer()
        self.startupTimer = threading.Timer(10, self.updateServices)
        self.startupTimer.start()

    def updateServices(self):
        def addService(dial, source):
            try:
                service = self.setupService(dial, source)
                self.services.append(service)
            except Exception:
                logger.exception("Error setting up service {mode} on frequency {frequency}".format(**dial))

        with self.lock:
            logger.debug("re-scheduling services due to sdr changes")
            self.stopServices()
            if not self.source.isAvailable():
                logger.debug("sdr source is unavailable")
                return
            cf = self.source.getProps()["center_freq"]
            sr = self.source.getProps()["samp_rate"]
            srh = sr / 2
            frequency_range = (cf - srh, cf + srh)

            dials = [
                dial
                for dial in Bandplan.getSharedInstance().collectDialFrequencies(frequency_range)
                if self.isSupported(dial["mode"])
            ]

            if not dials:
                logger.debug("no services available")
                return

            groups = self.optimizeResampling(dials, sr)
            if groups is None:
                for dial in dials:
                    addService(dial, self.source)
            else:
                for group in groups:
                    if len(group) > 1:
                        cf = self.get_center_frequency(group)
                        bw = self.get_bandwidth(group)
                        logger.debug("setting up resampler on center frequency: {0}, bandwidth: {1}".format(cf, bw))
                        resampler_props = PropertyLayer(center_freq=cf, samp_rate=bw)
                        resampler = Resampler(resampler_props, self.source)

                        for dial in group:
                            addService(dial, resampler)

                        # resampler goes in after the services since it must not be shutdown as long as the services are
                        # still running
                        self.services.append(resampler)
                    else:
                        dial = group[0]
                        addService(dial, self.source)

    def get_min_max(self, group):
        def find_bandpass(dial):
            mode = Modes.findByModulation(dial["mode"])
            if "underlying" in dial:
                mode = mode.for_underlying(dial["underlying"])
            return mode.get_bandpass()

        frequencies = sorted(group, key=lambda f: f["frequency"])
        lowest = frequencies[0]
        min = lowest["frequency"] + find_bandpass(lowest).low_cut
        highest = frequencies[-1]
        max = highest["frequency"] + find_bandpass(highest).high_cut
        return min, max

    def get_center_frequency(self, group):
        min, max = self.get_min_max(group)
        return (min + max) / 2

    def get_bandwidth(self, group):
        minFreq, maxFreq = self.get_min_max(group)
        # minimum bandwidth for a resampler: 25kHz
        return max((maxFreq - minFreq) * 1.15, 25000)

    def optimizeResampling(self, freqs, bandwidth):
        freqs = sorted(freqs, key=lambda f: f["frequency"])
        distances = [
            {
                "frequency": freqs[i]["frequency"],
                "distance": freqs[i + 1]["frequency"] - freqs[i]["frequency"],
            }
            for i in range(0, len(freqs) - 1)
        ]

        distances = [d for d in distances if d["distance"] > 0]

        distances = sorted(distances, key=lambda f: f["distance"], reverse=True)

        def calculate_usage(num_splits):
            splits = sorted([f["frequency"] for f in distances[0:num_splits]])
            previous = 0
            groups = []
            for split in splits:
                groups.append([f for f in freqs if previous < f["frequency"] <= split])
                previous = split
            groups.append([f for f in freqs if previous < f["frequency"]])

            def get_total_bandwidth(group):
                if len(group) > 1:
                    return bandwidth + len(group) * self.get_bandwidth(group)
                else:
                    return bandwidth

            total_bandwidth = sum([get_total_bandwidth(group) for group in groups])
            return {
                "num_splits": num_splits,
                "total_bandwidth": total_bandwidth,
                "groups": groups,
            }

        usages = [calculate_usage(i) for i in range(0, len(freqs))]
        # another possible outcome might be that it's best not to resample at all. this is a special case.
        usages += [
            {
                "num_splits": None,
                "total_bandwidth": bandwidth * len(freqs),
                "groups": [freqs],
            }
        ]
        results = sorted(usages, key=lambda f: f["total_bandwidth"])

        for r in results:
            logger.debug("splits: {0}, total: {1}".format(r["num_splits"], r["total_bandwidth"]))

        best = results[0]
        if best["num_splits"] is None:
            return None
        return best["groups"]

    def setupService(self, dial, source):
        logger.debug("setting up service {mode} on frequency {frequency}".format(**dial))

        modeObject = Modes.findByModulation(dial["mode"])
        if not isinstance(modeObject, DigitalMode):
            logger.warning("mode is not a digimode: %s", dial["mode"])
            return None

        if "underlying" in dial:
            modeObject = modeObject.for_underlying(dial["underlying"])

        demod = self._getDemodulator(modeObject.get_modulation())
        secondaryDemod = self._getSecondaryDemodulator(modeObject.modulation)
        center_freq = source.getProps()["center_freq"]
        sampleRate = source.getProps()["samp_rate"]
        if isinstance(secondaryDemod, DialFrequencyReceiver):
            secondaryDemod.setDialFrequency(dial["frequency"])

        chain = ServiceDemodulatorChain(demod, secondaryDemod, sampleRate, dial["frequency"] - center_freq)
        bandpass = modeObject.get_bandpass()
        if bandpass:
            chain.setBandPass(bandpass.low_cut, bandpass.high_cut)
        else:
            chain.setBandPass(None, None)
        chain.setReader(source.getBuffer().getReader())

        # dummy buffer, we don't use the output right now
        buffer = Buffer(chain.getOutputFormat())
        chain.setWriter(buffer)
        return chain

    # TODO move this elsewhere
    def _getDemodulator(self, demod: Union[str, BaseDemodulatorChain]):
        if isinstance(demod, BaseDemodulatorChain):
            return demod
        # TODO: move this to Modes
        if demod == "nfm":
            from csdr.chain.analog import NFm
            return NFm(48000)
        elif demod in ["usb", "lsb", "cw"]:
            from csdr.chain.analog import Ssb
            return Ssb()

    # TODO move this elsewhere
    def _getSecondaryDemodulator(self, mod) -> Optional[ServiceDemodulator]:
        if isinstance(mod, ServiceDemodulatorChain):
            return mod
        if mod in ["ft8", "wspr", "jt65", "jt9", "jt4", "ft4", "fst4", "fst4w", "q65"]:
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
            return PacketDemodulator(service=True)
        elif mod == "adsb":
            from csdr.chain.dump1090 import Dump1090
            return Dump1090()
        elif mod == "hfdl":
            from csdr.chain.dumphfdl import DumpHFDL
            return DumpHFDL()
        elif mod == "vdl2":
            from csdr.chain.dumpvdl2 import DumpVDL2
            return DumpVDL2()
        elif mod == "pocsag":
            from csdr.chain.digiham import PocsagDemodulator
            return PocsagDemodulator()
        elif mod == "ism":
            from csdr.chain.rtl433 import Rtl433
            return Rtl433()

        raise ValueError("unsupported service modulation: {}".format(mod))


class Services(object):
    handlers = {}
    schedulers = {}

    @staticmethod
    def start():
        config = Config.get()
        config.wireProperty("services_enabled", Services._receiveEnabledEvent)
        activeSources = SdrService.getActiveSources()
        activeSources.wire(Services._receiveDeviceEvent)
        for key, source in activeSources.items():
            Services.schedulers[key] = ServiceScheduler(source)

    @staticmethod
    def _receiveEnabledEvent(state):
        if state:
            for key, source in SdrService.getActiveSources().__dict__().items():
                Services.handlers[key] = ServiceHandler(source)
        else:
            for handler in list(Services.handlers.values()):
                handler.shutdown()
            Services.handlers = {}

    @staticmethod
    def _receiveDeviceEvent(changes):
        for key, source in changes.items():
            if source is PropertyDeleted:
                if key in Services.handlers:
                    Services.handlers[key].shutdown()
                    del Services.handlers[key]
                if key in Services.schedulers:
                    Services.schedulers[key].shutdown()
                    del Services.schedulers[key]
            else:
                Services.schedulers[key] = ServiceScheduler(source)
                if Config.get()["services_enabled"]:
                    Services.handlers[key] = ServiceHandler(source)

    @staticmethod
    def stop():
        for handler in list(Services.handlers.values()):
            handler.shutdown()
        Services.handlers = {}
        for scheduler in list(Services.schedulers.values()):
            scheduler.shutdown()
        Services.schedulers = {}
