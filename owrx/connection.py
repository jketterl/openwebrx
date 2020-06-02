from owrx.config import Config
from owrx.details import ReceiverDetails
from owrx.dsp import DspManager
from owrx.cpu import CpuUsageThread
from owrx.sdr import SdrService
from owrx.source import SdrSource
from owrx.client import ClientRegistry, TooManyClientsException
from owrx.feature import FeatureDetector
from owrx.version import openwebrx_version
from owrx.bands import Bandplan
from owrx.bookmarks import Bookmarks
from owrx.map import Map
from owrx.property import PropertyStack
from owrx.modes import Modes, DigitalMode
from multiprocessing import Queue
from queue import Full
from js8py import Js8Frame
from abc import ABC, ABCMeta, abstractmethod
import json
import threading

import logging

logger = logging.getLogger(__name__)


class Client(ABC):
    def __init__(self, conn):
        self.conn = conn
        self.multiprocessingPipe = Queue(100)

        def mp_passthru():
            run = True
            while run:
                try:
                    data = self.multiprocessingPipe.get()
                    self.send(data)
                except (EOFError, OSError):
                    run = False

        threading.Thread(target=mp_passthru).start()

    def send(self, data):
        self.conn.send(data)

    def close(self):
        self.conn.close()
        self.multiprocessingPipe.close()

    def mp_send(self, data):
        try:
            self.multiprocessingPipe.put(data, block=False)
        except Full:
            self.close()

    @abstractmethod
    def handleTextMessage(self, conn, message):
        pass

    def handleBinaryMessage(self, conn, data):
        logger.error("unsupported binary message, discarding")

    def handleClose(self):
        self.close()


class OpenWebRxClient(Client, metaclass=ABCMeta):
    def __init__(self, conn):
        super().__init__(conn)

        receiver_details = ReceiverDetails()

        def send_receiver_info(*args):
            receiver_info = receiver_details.__dict__()
            self.write_receiver_details(receiver_info)

        # TODO unsubscribe
        receiver_details.wire(send_receiver_info)
        send_receiver_info()

    def write_receiver_details(self, details):
        self.send({"type": "receiver_details", "value": details})


class OpenWebRxReceiverClient(OpenWebRxClient):
    config_keys = [
        "waterfall_colors",
        "waterfall_min_level",
        "waterfall_max_level",
        "waterfall_auto_level_margin",
        "samp_rate",
        "fft_size",
        "audio_compression",
        "fft_compression",
        "max_clients",
        "start_mod",
        "start_freq",
        "center_freq",
        "initial_squelch_level",
        "profile_id",
    ]

    def __init__(self, conn):
        super().__init__(conn)

        self.dsp = None
        self.sdr = None
        self.configSub = None
        self.connectionProperties = {}

        try:
            ClientRegistry.getSharedInstance().addClient(self)
        except TooManyClientsException:
            self.write_backoff_message("Too many clients")
            self.close()
            raise

        self.setSdr()

        features = FeatureDetector().feature_availability()
        self.write_features(features)

        modes = Modes.getModes()
        self.write_modes(modes)

        self.__sendProfiles()

        CpuUsageThread.getSharedInstance().add_client(self)

    def __sendProfiles(self):
        profiles = [
            {"name": s.getName() + " " + p["name"], "id": sid + "|" + pid}
            for (sid, s) in SdrService.getSources().items()
            for (pid, p) in s.getProfiles().items()
        ]
        self.write_profiles(profiles)

    def handleTextMessage(self, conn, message):
        try:
            message = json.loads(message)
            logger.debug(message)
            if "type" in message:
                if message["type"] == "dspcontrol":
                    if "action" in message and message["action"] == "start":
                        self.startDsp()

                    if "params" in message:
                        dsp = self.getDsp()
                        if dsp is None:
                            logger.warning("DSP not available; discarding client data")
                        else:
                            params = message["params"]
                            dsp.setProperties(params)

                elif message["type"] == "config":
                    if "params" in message:
                        self.setParams(message["params"])
                elif message["type"] == "setsdr":
                    if "params" in message:
                        self.setSdr(message["params"]["sdr"])
                elif message["type"] == "selectprofile":
                    if "params" in message and "profile" in message["params"]:
                        profile = message["params"]["profile"].split("|")
                        self.setSdr(profile[0])
                        self.sdr.activateProfile(profile[1])
                elif message["type"] == "connectionproperties":
                    if "params" in message:
                        self.connectionProperties = message["params"]
                        if self.dsp:
                            self.getDsp().setProperties(self.connectionProperties)

            else:
                logger.warning("received message without type: {0}".format(message))

        except json.JSONDecodeError:
            logger.warning("message is not json: {0}".format(message))

    def setSdr(self, id=None):
        while True:
            next = None
            if id is not None:
                next = SdrService.getSource(id)
            if next is None:
                next = SdrService.getFirstSource()
            if next is None:
                # exit condition: no sdrs available
                logger.warning("no more SDR devices available")
                self.handleNoSdrsAvailable()
                return

            # exit condition: no change
            if next == self.sdr:
                return

            self.stopDsp()

            if self.configSub is not None:
                self.configSub.cancel()
                self.configSub = None

            self.sdr = next

            self.getDsp()

            # found a working sdr, exit the loop
            if self.sdr.getState() != SdrSource.STATE_FAILED:
                break

            logger.warning('SDR device "%s" has failed, selecing new device', self.sdr.getName())
            self.write_log_message('SDR device "{0}" has failed, selecting new device'.format(self.sdr.getName()))

        # send initial config
        self.getDsp().setProperties(self.connectionProperties)

        stack = PropertyStack()
        stack.addLayer(0, self.sdr.getProps())
        stack.addLayer(1, Config.get())
        configProps = stack.filter(*OpenWebRxReceiverClient.config_keys)

        def sendConfig(key, value):
            config = configProps.__dict__()
            # TODO mathematical properties? hmmmm
            config["start_offset_freq"] = configProps["start_freq"] - configProps["center_freq"]
            # TODO this is a hack to support multiple sdrs
            config["sdr_id"] = self.sdr.getId()
            self.write_config(config)

            cf = configProps["center_freq"]
            srh = configProps["samp_rate"] / 2
            frequencyRange = (cf - srh, cf + srh)
            self.write_dial_frequendies(Bandplan.getSharedInstance().collectDialFrequencies(frequencyRange))
            bookmarks = [b.__dict__() for b in Bookmarks.getSharedInstance().getBookmarks(frequencyRange)]
            self.write_bookmarks(bookmarks)

        self.configSub = configProps.wire(sendConfig)
        sendConfig(None, None)
        self.__sendProfiles()

        self.sdr.addSpectrumClient(self)

    def handleNoSdrsAvailable(self):
        self.write_sdr_error("No SDR Devices available")

    def startDsp(self):
        self.getDsp().start()

    def close(self):
        self.stopDsp()
        CpuUsageThread.getSharedInstance().remove_client(self)
        ClientRegistry.getSharedInstance().removeClient(self)
        if self.configSub is not None:
            self.configSub.cancel()
            self.configSub = None
        super().close()

    def stopDsp(self):
        if self.dsp is not None:
            self.dsp.stop()
            self.dsp = None
        if self.sdr is not None:
            self.sdr.removeSpectrumClient(self)

    def setParams(self, params):
        config = Config.get()
        # allow direct configuration only if enabled in the config
        if "configurable_keys" not in config:
            return
        keys = config["configurable_keys"]
        if not keys:
            return
        # only the keys in the protected property manager can be overridden from the web
        stack = PropertyStack()
        stack.addLayer(0, self.sdr.getProps())
        stack.addLayer(1, config)
        protected = stack.filter(*keys)
        for key, value in params.items():
            try:
                protected[key] = value
            except KeyError:
                pass

    def getDsp(self):
        if self.dsp is None and self.sdr is not None:
            self.dsp = DspManager(self, self.sdr)
        return self.dsp

    def write_spectrum_data(self, data):
        self.mp_send(bytes([0x01]) + data)

    def write_dsp_data(self, data):
        self.send(bytes([0x02]) + data)

    def write_s_meter_level(self, level):
        self.send({"type": "smeter", "value": level})

    def write_cpu_usage(self, usage):
        self.mp_send({"type": "cpuusage", "value": usage})

    def write_clients(self, clients):
        self.mp_send({"type": "clients", "value": clients})

    def write_secondary_fft(self, data):
        self.send(bytes([0x03]) + data)

    def write_secondary_demod(self, data):
        message = data.decode("ascii", "replace")
        self.send({"type": "secondary_demod", "value": message})

    def write_secondary_dsp_config(self, cfg):
        self.send({"type": "secondary_config", "value": cfg})

    def write_config(self, cfg):
        self.send({"type": "config", "value": cfg})

    def write_profiles(self, profiles):
        self.send({"type": "profiles", "value": profiles})

    def write_features(self, features):
        self.send({"type": "features", "value": features})

    def write_metadata(self, metadata):
        self.send({"type": "metadata", "value": metadata})

    def write_wsjt_message(self, message):
        self.send({"type": "wsjt_message", "value": message})

    def write_dial_frequendies(self, frequencies):
        self.send({"type": "dial_frequencies", "value": frequencies})

    def write_bookmarks(self, bookmarks):
        self.send({"type": "bookmarks", "value": bookmarks})

    def write_aprs_data(self, data):
        self.send({"type": "aprs_data", "value": data})

    def write_log_message(self, message):
        self.send({"type": "log_message", "value": message})

    def write_sdr_error(self, message):
        self.send({"type": "sdr_error", "value": message})

    def write_pocsag_data(self, data):
        self.send({"type": "pocsag_data", "value": data})

    def write_backoff_message(self, reason):
        self.send({"type": "backoff", "reason": reason})

    def write_js8_message(self, frame: Js8Frame, freq: int):
        self.send({"type": "js8_message", "value": {
            "msg": str(frame),
            "timestamp": frame.timestamp,
            "db": frame.db,
            "dt": frame.dt,
            "freq": freq + frame.freq,
            "thread_type": frame.thread_type,
            "mode": frame.mode
        }})

    def write_modes(self, modes):
        def to_json(m):
            res = {
                "modulation": m.modulation,
                "name": m.name,
                "type": "digimode" if isinstance(m, DigitalMode) else "analog",
                "requirements": m.requirements,
                "squelch": m.squelch,
            }
            if m.bandpass is not None:
                res["bandpass"] = {
                    "low_cut": m.bandpass.low_cut,
                    "high_cut": m.bandpass.high_cut
                }
            if isinstance(m, DigitalMode):
                res["underlying"] = m.underlying
            return res

        self.send({"type": "modes", "value": [to_json(m) for m in modes]})


class MapConnection(OpenWebRxClient):
    def __init__(self, conn):
        super().__init__(conn)

        pm = Config.get()
        self.write_config(pm.filter("google_maps_api_key", "receiver_gps", "map_position_retention_time").__dict__())

        Map.getSharedInstance().addClient(self)

    def handleTextMessage(self, conn, message):
        pass

    def close(self):
        Map.getSharedInstance().removeClient(self)
        super().close()

    def write_config(self, cfg):
        self.send({"type": "config", "value": cfg})

    def write_update(self, update):
        self.mp_send({"type": "update", "value": update})


class WebSocketMessageHandler(object):
    def __init__(self):
        self.handshake = None

    def handleTextMessage(self, conn, message):
        if message[:16] == "SERVER DE CLIENT":
            meta = message[17:].split(" ")
            self.handshake = {v[0]: "=".join(v[1:]) for v in map(lambda x: x.split("="), meta)}

            conn.send("CLIENT DE SERVER server=openwebrx version={version}".format(version=openwebrx_version))
            logger.debug("client connection intitialized")

            if "type" in self.handshake:
                if self.handshake["type"] == "receiver":
                    client = OpenWebRxReceiverClient(conn)
                if self.handshake["type"] == "map":
                    client = MapConnection(conn)
            # backwards compatibility
            else:
                client = OpenWebRxReceiverClient(conn)

            # hand off all further communication to the correspondig connection
            conn.setMessageHandler(client)

            return

        if not self.handshake:
            logger.warning("not answering client request since handshake is not complete")
            return

    def handleBinaryMessage(self, conn, data):
        pass

    def handleClose(self):
        pass
