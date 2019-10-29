import subprocess
from owrx.config import PropertyManager
from owrx.feature import FeatureDetector, UnknownFeatureException
from owrx.meta import MetaParser
from owrx.wsjt import WsjtParser
from owrx.aprs import AprsParser
from owrx.metrics import Metrics, DirectMetric
import threading
import csdr
import time
import os
import signal
import sys
import socket
import logging

logger = logging.getLogger(__name__)


class SdrService(object):
    sdrProps = None
    sources = {}
    lastPort = None

    @staticmethod
    def getNextPort():
        pm = PropertyManager.getSharedInstance()
        (start, end) = pm["iq_port_range"]
        if SdrService.lastPort is None:
            SdrService.lastPort = start
        else:
            SdrService.lastPort += 1
            if SdrService.lastPort > end:
                raise IndexError("no more available ports to start more sdrs")
        return SdrService.lastPort

    @staticmethod
    def loadProps():
        if SdrService.sdrProps is None:
            pm = PropertyManager.getSharedInstance()
            featureDetector = FeatureDetector()

            def loadIntoPropertyManager(dict: dict):
                propertyManager = PropertyManager()
                for (name, value) in dict.items():
                    propertyManager[name] = value
                return propertyManager

            def sdrTypeAvailable(value):
                try:
                    if not featureDetector.is_available(value["type"]):
                        logger.error(
                            'The RTL source type "{0}" is not available. please check requirements.'.format(
                                value["type"]
                            )
                        )
                        return False
                    return True
                except UnknownFeatureException:
                    logger.error(
                        'The RTL source type "{0}" is invalid. Please check your configuration'.format(value["type"])
                    )
                    return False

            # transform all dictionary items into PropertyManager object, filtering out unavailable ones
            SdrService.sdrProps = {
                name: loadIntoPropertyManager(value) for (name, value) in pm["sdrs"].items() if sdrTypeAvailable(value)
            }
            logger.info(
                "SDR sources loaded. Availables SDRs: {0}".format(
                    ", ".join(map(lambda x: x["name"], SdrService.sdrProps.values()))
                )
            )

    @staticmethod
    def getSource(id=None):
        SdrService.loadProps()
        if id is None:
            # TODO: configure default sdr in config? right now it will pick the first one off the list.
            id = list(SdrService.sdrProps.keys())[0]
        sources = SdrService.getSources()
        return sources[id]

    @staticmethod
    def getSources():
        SdrService.loadProps()
        for id in SdrService.sdrProps.keys():
            if not id in SdrService.sources:
                props = SdrService.sdrProps[id]
                className = "".join(x for x in props["type"].title() if x.isalnum()) + "Source"
                cls = getattr(sys.modules[__name__], className)
                SdrService.sources[id] = cls(id, props, SdrService.getNextPort())
        return SdrService.sources


class SdrSourceException(Exception):
    pass


class SdrSource(object):
    def __init__(self, id, props, port):
        self.id = id
        self.props = props
        self.profile_id = None
        self.activateProfile()
        self.rtlProps = self.props.collect(
            "samp_rate", "nmux_memory", "center_freq", "ppm", "rf_gain", "lna_gain", "rf_amp", "antenna", "if_gain", "device"
        ).defaults(PropertyManager.getSharedInstance())

        def restart(name, value):
            logger.debug("restarting sdr source due to property change: {0} changed to {1}".format(name, value))
            self.stop()
            self.start()

        self.rtlProps.wire(restart)
        self.port = port
        self.monitor = None
        self.clients = []
        self.spectrumClients = []
        self.spectrumThread = None
        self.process = None
        self.modificationLock = threading.Lock()

    # override this in subclasses
    def getCommand(self):
        pass

    # override this in subclasses, if necessary
    def getFormatConversion(self):
        return None

    def activateProfile(self, profile_id=None):
        profiles = self.props["profiles"]
        if profile_id is None:
            profile_id = list(profiles.keys())[0]
        if profile_id == self.profile_id:
            return;
        logger.debug("activating profile {0}".format(profile_id))
        self.profile_id = profile_id
        profile = profiles[profile_id]
        for (key, value) in profile.items():
            # skip the name, that would overwrite the source name.
            if key == "name":
                continue
            self.props[key] = value

    def getId(self):
        return self.id

    def getProfileId(self):
        return self.profile_id

    def getProfiles(self):
        return self.props["profiles"]

    def getName(self):
        return self.props["name"]

    def getProps(self):
        return self.props

    def getPort(self):
        return self.port

    def start(self):
        self.modificationLock.acquire()
        if self.monitor:
            self.modificationLock.release()
            return

        props = self.rtlProps

        start_sdr_command = self.getCommand().format(
            **props.collect(
                "samp_rate", "center_freq", "ppm", "rf_gain", "lna_gain", "rf_amp", "antenna", "if_gain", "device"
            ).__dict__()
        )

        format_conversion = self.getFormatConversion()
        if format_conversion is not None:
            start_sdr_command += " | " + format_conversion

        nmux_bufcnt = nmux_bufsize = 0
        while nmux_bufsize < props["samp_rate"] / 4:
            nmux_bufsize += 4096
        while nmux_bufsize * nmux_bufcnt < props["nmux_memory"] * 1e6:
            nmux_bufcnt += 1
        if nmux_bufcnt == 0 or nmux_bufsize == 0:
            logger.error(
                "Error: nmux_bufsize or nmux_bufcnt is zero. These depend on nmux_memory and samp_rate options in config_webrx.py"
            )
            self.modificationLock.release()
            return
        logger.debug("nmux_bufsize = %d, nmux_bufcnt = %d" % (nmux_bufsize, nmux_bufcnt))
        cmd = start_sdr_command + " | nmux --bufsize %d --bufcnt %d --port %d --address 127.0.0.1" % (
            nmux_bufsize,
            nmux_bufcnt,
            self.port,
        )
        self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setpgrp)
        logger.info("Started rtl source: " + cmd)

        available = False

        def wait_for_process_to_end():
            rc = self.process.wait()
            logger.debug("shut down with RC={0}".format(rc))
            self.monitor = None

        self.monitor = threading.Thread(target=wait_for_process_to_end)
        self.monitor.start()

        retries = 1000
        while retries > 0:
            retries -= 1
            if self.monitor is None:
                break
            testsock = socket.socket()
            try:
                testsock.connect(("127.0.0.1", self.getPort()))
                testsock.close()
                available = True
                break
            except:
                time.sleep(0.1)

        self.modificationLock.release()

        if not available:
            raise SdrSourceException("rtl source failed to start up")

        for c in self.clients:
            c.onSdrAvailable()

    def isAvailable(self):
        return self.monitor is not None

    def stop(self):
        for c in self.clients:
            c.onSdrUnavailable()

        self.modificationLock.acquire()

        if self.process is not None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                # been killed by something else, ignore
                pass
        if self.monitor:
            self.monitor.join()
        self.sleepOnRestart()
        self.modificationLock.release()

    def sleepOnRestart(self):
        pass

    def hasActiveClients(self):
        activeClients = [c for c in self.clients if c.isActive()]
        return len(activeClients) > 0

    def addClient(self, c):
        self.clients.append(c)
        if self.hasActiveClients():
            self.start()

    def removeClient(self, c):
        try:
            self.clients.remove(c)
        except ValueError:
            pass
        if not self.hasActiveClients():
            self.stop()

    def addSpectrumClient(self, c):
        self.spectrumClients.append(c)
        if self.spectrumThread is None:
            self.spectrumThread = SpectrumThread(self)
            self.spectrumThread.start()

    def removeSpectrumClient(self, c):
        try:
            self.spectrumClients.remove(c)
        except ValueError:
            pass
        if not self.spectrumClients and self.spectrumThread is not None:
            self.spectrumThread.stop()
            self.spectrumThread = None

    def writeSpectrumData(self, data):
        for c in self.spectrumClients:
            c.write_spectrum_data(data)


class Resampler(SdrSource):
    def __init__(self, props, port, sdr):
        sdrProps = sdr.getProps()
        self.shift = (sdrProps["center_freq"] - props["center_freq"]) / sdrProps["samp_rate"]
        self.decimation = int(float(sdrProps["samp_rate"]) / props["samp_rate"])
        if_samp_rate = sdrProps["samp_rate"] / self.decimation
        self.transition_bw = 0.15 * (if_samp_rate / float(sdrProps["samp_rate"]))
        props["samp_rate"] = if_samp_rate

        self.sdr = sdr
        super().__init__(None, props, port)

    def start(self):
        self.modificationLock.acquire()
        if self.monitor:
            self.modificationLock.release()
            return

        props = self.rtlProps

        resampler_command = [
            "nc -v 127.0.0.1 {nc_port}".format(nc_port=self.sdr.getPort()),
            "csdr shift_addition_cc {shift}".format(shift=self.shift),
            "csdr fir_decimate_cc {decimation} {ddc_transition_bw} HAMMING".format(
                decimation=self.decimation, ddc_transition_bw=self.transition_bw
            ),
        ]

        nmux_bufcnt = nmux_bufsize = 0
        while nmux_bufsize < props["samp_rate"] / 4:
            nmux_bufsize += 4096
        while nmux_bufsize * nmux_bufcnt < props["nmux_memory"] * 1e6:
            nmux_bufcnt += 1
        if nmux_bufcnt == 0 or nmux_bufsize == 0:
            logger.error(
                "Error: nmux_bufsize or nmux_bufcnt is zero. These depend on nmux_memory and samp_rate options in config_webrx.py"
            )
            self.modificationLock.release()
            return
        logger.debug("nmux_bufsize = %d, nmux_bufcnt = %d" % (nmux_bufsize, nmux_bufcnt))
        resampler_command += [
            "nmux --bufsize %d --bufcnt %d --port %d --address 127.0.0.1" % (nmux_bufsize, nmux_bufcnt, self.port)
        ]
        cmd = " | ".join(resampler_command)
        logger.debug("resampler command: %s", cmd)
        self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setpgrp)
        logger.info("Started resampler source: " + cmd)

        available = False

        def wait_for_process_to_end():
            rc = self.process.wait()
            logger.debug("shut down with RC={0}".format(rc))
            self.monitor = None

        self.monitor = threading.Thread(target=wait_for_process_to_end)
        self.monitor.start()

        retries = 1000
        while retries > 0:
            retries -= 1
            if self.monitor is None:
                break
            testsock = socket.socket()
            try:
                testsock.connect(("127.0.0.1", self.getPort()))
                testsock.close()
                available = True
                break
            except:
                time.sleep(0.1)

        self.modificationLock.release()

        if not available:
            raise SdrSourceException("resampler source failed to start up")

        for c in self.clients:
            c.onSdrAvailable()

    def activateProfile(self, profile_id=None):
        pass


class RtlSdrSource(SdrSource):
    def getCommand(self):
        command = "rtl_sdr -s {samp_rate} -f {center_freq} -p {ppm} -g {rf_gain}"
        if self.rtlProps["device"] != "" :
            command += " -d {device}"
        command += " -"
        return command

    def getFormatConversion(self):
        return "csdr convert_u8_f"


class HackrfSource(SdrSource):
    def getCommand(self):
        command="hackrf_transfer -s {samp_rate} -f {center_freq} -g {rf_gain} -l{lna_gain} -a{rf_amp} "
        if self.rtlProps["device"] != "" :
            command += " -d {device}"
        command += " -r-"
        return command

    def getFormatConversion(self):
        return "csdr convert_s8_f"


class SdrplaySource(SdrSource):
    def getCommand(self):
        command = "rx_sdr -F CF32 -s {samp_rate} -f {center_freq} -p {ppm}"
        gainMap = {"rf_gain": "RFGR", "if_gain": "IFGR"}
        gains = [
            "{0}={{{1}}}".format(gainMap[name], name)
            for (name, value) in self.rtlProps.collect("rf_gain", "if_gain").__dict__().items()
            if value is not None
        ]
        if gains:
            command += " -g {gains}".format(gains=",".join(gains))
        if self.rtlProps["antenna"] is not None:
            command += ' -a "{antenna}"'
        if self.rtlProps["device"] != "" :
            command += " -d {device}"
        command += " -"
        return command

    def sleepOnRestart(self):
        time.sleep(1)


class AirspySource(SdrSource):
    def getCommand(self):
        frequency = self.props["center_freq"] / 1e6
        command = "airspy_rx"
        command += " -f{0}".format(frequency)
        command += " -r /dev/stdout -a{samp_rate} -g {rf_gain}"
        if self.rtlProps["device"] != "" :
            command += " -s {device}"
        return command

    def getFormatConversion(self):
        return "csdr convert_s16_f"


class SpectrumThread(csdr.output):
    def __init__(self, sdrSource):
        self.sdrSource = sdrSource
        super().__init__()

        self.props = props = self.sdrSource.props.collect(
            "samp_rate",
            "fft_size",
            "fft_fps",
            "fft_voverlap_factor",
            "fft_compression",
            "csdr_dynamic_bufsize",
            "csdr_print_bufsizes",
            "csdr_through",
            "temporary_directory",
        ).defaults(PropertyManager.getSharedInstance())

        self.dsp = dsp = csdr.dsp(self)
        dsp.nc_port = self.sdrSource.getPort()
        dsp.set_demodulator("fft")

        def set_fft_averages(key, value):
            samp_rate = props["samp_rate"]
            fft_size = props["fft_size"]
            fft_fps = props["fft_fps"]
            fft_voverlap_factor = props["fft_voverlap_factor"]

            dsp.set_fft_averages(
                int(round(1.0 * samp_rate / fft_size / fft_fps / (1.0 - fft_voverlap_factor)))
                if fft_voverlap_factor > 0
                else 0
            )

        self.subscriptions = [
            props.getProperty("samp_rate").wire(dsp.set_samp_rate),
            props.getProperty("fft_size").wire(dsp.set_fft_size),
            props.getProperty("fft_fps").wire(dsp.set_fft_fps),
            props.getProperty("fft_compression").wire(dsp.set_fft_compression),
            props.getProperty("temporary_directory").wire(dsp.set_temporary_directory),
            props.collect("samp_rate", "fft_size", "fft_fps", "fft_voverlap_factor").wire(set_fft_averages),
        ]

        set_fft_averages(None, None)

        dsp.csdr_dynamic_bufsize = props["csdr_dynamic_bufsize"]
        dsp.csdr_print_bufsizes = props["csdr_print_bufsizes"]
        dsp.csdr_through = props["csdr_through"]
        logger.debug("Spectrum thread initialized successfully.")

    def start(self):
        self.sdrSource.addClient(self)
        if self.sdrSource.isAvailable():
            self.dsp.start()

    def supports_type(self, t):
        return t == "audio"

    def receive_output(self, type, read_fn):
        if self.props["csdr_dynamic_bufsize"]:
            read_fn(8)  # dummy read to skip bufsize & preamble
            logger.debug("Note: CSDR_DYNAMIC_BUFSIZE_ON = 1")

        threading.Thread(target=self.pump(read_fn, self.sdrSource.writeSpectrumData)).start()

    def stop(self):
        self.dsp.stop()
        self.sdrSource.removeClient(self)
        for c in self.subscriptions:
            c.cancel()
        self.subscriptions = []

    def isActive(self):
        return True

    def onSdrAvailable(self):
        self.dsp.start()

    def onSdrUnavailable(self):
        self.dsp.stop()


class DspManager(csdr.output):
    def __init__(self, handler, sdrSource):
        self.handler = handler
        self.sdrSource = sdrSource
        self.metaParser = MetaParser(self.handler)
        self.wsjtParser = WsjtParser(self.handler)
        self.aprsParser = AprsParser(self.handler)

        self.localProps = (
            self.sdrSource.getProps()
            .collect(
                "audio_compression",
                "fft_compression",
                "digimodes_fft_size",
                "csdr_dynamic_bufsize",
                "csdr_print_bufsizes",
                "csdr_through",
                "digimodes_enable",
                "samp_rate",
                "digital_voice_unvoiced_quality",
                "dmr_filter",
                "temporary_directory",
                "center_freq",
            )
            .defaults(PropertyManager.getSharedInstance())
        )

        self.dsp = csdr.dsp(self)
        self.dsp.nc_port = self.sdrSource.getPort()

        def set_low_cut(cut):
            bpf = self.dsp.get_bpf()
            bpf[0] = cut
            self.dsp.set_bpf(*bpf)

        def set_high_cut(cut):
            bpf = self.dsp.get_bpf()
            bpf[1] = cut
            self.dsp.set_bpf(*bpf)

        def set_dial_freq(key, value):
            freq = self.localProps["center_freq"] + self.localProps["offset_freq"]
            self.wsjtParser.setDialFrequency(freq)
            self.aprsParser.setDialFrequency(freq)
            self.metaParser.setDialFrequency(freq)

        self.subscriptions = [
            self.localProps.getProperty("audio_compression").wire(self.dsp.set_audio_compression),
            self.localProps.getProperty("fft_compression").wire(self.dsp.set_fft_compression),
            self.localProps.getProperty("digimodes_fft_size").wire(self.dsp.set_secondary_fft_size),
            self.localProps.getProperty("samp_rate").wire(self.dsp.set_samp_rate),
            self.localProps.getProperty("output_rate").wire(self.dsp.set_output_rate),
            self.localProps.getProperty("offset_freq").wire(self.dsp.set_offset_freq),
            self.localProps.getProperty("squelch_level").wire(self.dsp.set_squelch_level),
            self.localProps.getProperty("low_cut").wire(set_low_cut),
            self.localProps.getProperty("high_cut").wire(set_high_cut),
            self.localProps.getProperty("mod").wire(self.dsp.set_demodulator),
            self.localProps.getProperty("digital_voice_unvoiced_quality").wire(self.dsp.set_unvoiced_quality),
            self.localProps.getProperty("dmr_filter").wire(self.dsp.set_dmr_filter),
            self.localProps.getProperty("temporary_directory").wire(self.dsp.set_temporary_directory),
            self.localProps.collect("center_freq", "offset_freq").wire(set_dial_freq),
        ]

        self.dsp.set_offset_freq(0)
        self.dsp.set_bpf(-4000, 4000)
        self.dsp.csdr_dynamic_bufsize = self.localProps["csdr_dynamic_bufsize"]
        self.dsp.csdr_print_bufsizes = self.localProps["csdr_print_bufsizes"]
        self.dsp.csdr_through = self.localProps["csdr_through"]

        if self.localProps["digimodes_enable"]:

            def set_secondary_mod(mod):
                if mod == False:
                    mod = None
                self.dsp.set_secondary_demodulator(mod)
                if mod is not None:
                    self.handler.write_secondary_dsp_config(
                        {
                            "secondary_fft_size": self.localProps["digimodes_fft_size"],
                            "if_samp_rate": self.dsp.if_samp_rate(),
                            "secondary_bw": self.dsp.secondary_bw(),
                        }
                    )

            self.subscriptions += [
                self.localProps.getProperty("secondary_mod").wire(set_secondary_mod),
                self.localProps.getProperty("secondary_offset_freq").wire(self.dsp.set_secondary_offset_freq),
            ]

        self.sdrSource.addClient(self)

        super().__init__()

    def start(self):
        if self.sdrSource.isAvailable():
            self.dsp.start()

    def receive_output(self, t, read_fn):
        logger.debug("adding new output of type %s", t)
        writers = {
            "audio": self.handler.write_dsp_data,
            "smeter": self.handler.write_s_meter_level,
            "secondary_fft": self.handler.write_secondary_fft,
            "secondary_demod": self.handler.write_secondary_demod,
            "meta": self.metaParser.parse,
            "wsjt_demod": self.wsjtParser.parse,
            "packet_demod": self.aprsParser.parse,
        }
        write = writers[t]

        threading.Thread(target=self.pump(read_fn, write)).start()

    def stop(self):
        self.dsp.stop()
        self.sdrSource.removeClient(self)
        for sub in self.subscriptions:
            sub.cancel()
        self.subscriptions = []

    def setProperty(self, prop, value):
        self.localProps.getProperty(prop).setValue(value)

    def isActive(self):
        return True

    def onSdrAvailable(self):
        logger.debug("received onSdrAvailable, attempting DspSource restart")
        self.dsp.start()

    def onSdrUnavailable(self):
        logger.debug("received onSdrUnavailable, shutting down DspSource")
        self.dsp.stop()


class CpuUsageThread(threading.Thread):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if CpuUsageThread.sharedInstance is None:
            CpuUsageThread.sharedInstance = CpuUsageThread()
        return CpuUsageThread.sharedInstance

    def __init__(self):
        self.clients = []
        self.doRun = True
        self.last_worktime = 0
        self.last_idletime = 0
        self.endEvent = threading.Event()
        super().__init__()

    def run(self):
        while self.doRun:
            try:
                cpu_usage = self.get_cpu_usage()
            except:
                cpu_usage = 0
            for c in self.clients:
                c.write_cpu_usage(cpu_usage)
            self.endEvent.wait(timeout=3)
        logger.debug("cpu usage thread shut down")

    def get_cpu_usage(self):
        try:
            f = open("/proc/stat", "r")
        except:
            return 0  # Workaround, possibly we're on a Mac
        line = ""
        while not "cpu " in line:
            line = f.readline()
        f.close()
        spl = line.split(" ")
        worktime = int(spl[2]) + int(spl[3]) + int(spl[4])
        idletime = int(spl[5])
        dworktime = worktime - self.last_worktime
        didletime = idletime - self.last_idletime
        rate = float(dworktime) / (didletime + dworktime)
        self.last_worktime = worktime
        self.last_idletime = idletime
        if self.last_worktime == 0:
            return 0
        return rate

    def add_client(self, c):
        self.clients.append(c)
        if not self.is_alive():
            self.start()

    def remove_client(self, c):
        try:
            self.clients.remove(c)
        except ValueError:
            pass
        if not self.clients:
            self.shutdown()

    def shutdown(self):
        CpuUsageThread.sharedInstance = None
        self.doRun = False
        self.endEvent.set()


class TooManyClientsException(Exception):
    pass


class ClientRegistry(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with ClientRegistry.creationLock:
            if ClientRegistry.sharedInstance is None:
                ClientRegistry.sharedInstance = ClientRegistry()
        return ClientRegistry.sharedInstance

    def __init__(self):
        self.clients = []
        Metrics.getSharedInstance().addMetric("openwebrx.users", DirectMetric(self.clientCount))
        super().__init__()

    def broadcast(self):
        n = self.clientCount()
        for c in self.clients:
            c.write_clients(n)

    def addClient(self, client):
        pm = PropertyManager.getSharedInstance()
        if len(self.clients) >= pm["max_clients"]:
            raise TooManyClientsException()
        self.clients.append(client)
        self.broadcast()

    def clientCount(self):
        return len(self.clients)

    def removeClient(self, client):
        try:
            self.clients.remove(client)
        except ValueError:
            pass
        self.broadcast()
