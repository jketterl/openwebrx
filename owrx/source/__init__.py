from owrx.config import Config
import threading
import subprocess
import os
import socket
import shlex
import time
import signal
import pkgutil
from abc import ABC, abstractmethod
from owrx.command import CommandMapper
from owrx.socket import getAvailablePort
from owrx.property import PropertyStack, PropertyLayer, PropertyFilter, PropertyCarousel, PropertyDeleted
from owrx.property.filter import ByLambda
from owrx.form.input import Input, TextInput, NumberInput, CheckboxInput, ModesInput, ExponentialInput, DropdownInput, Option
from owrx.form.input.converter import OptionalConverter, IntConverter
from owrx.form.input.device import GainInput, SchedulerInput, WaterfallLevelsInput
from owrx.form.input.validator import RequiredValidator
from owrx.form.section import OptionalSection
from owrx.feature import FeatureDetector
from typing import List
from enum import Enum

from pycsdr.modules import TcpSource, Buffer
from pycsdr.types import Format

import logging

logger = logging.getLogger(__name__)


class SdrSourceState(Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    STOPPING = "Stopping"
    TUNING = "Tuning"

    def __str__(self):
        return self.value


class SdrBusyState(Enum):
    IDLE = 1
    BUSY = 2


class SdrClientClass(Enum):
    INACTIVE = 1
    BACKGROUND = 2
    USER = 3


class SdrSourceEventClient(object):
    def onStateChange(self, state: SdrSourceState):
        pass

    def onBusyStateChange(self, state: SdrBusyState):
        pass

    def onFail(self):
        pass

    def onShutdown(self):
        pass

    def onDisable(self):
        pass

    def onEnable(self):
        pass

    def getClientClass(self) -> SdrClientClass:
        return SdrClientClass.INACTIVE


class SdrProfileCarousel(PropertyCarousel):
    def __init__(self, props):
        super().__init__()
        if "profiles" not in props:
            return

        for profile_id, profile in props["profiles"].items():
            self.addLayer(profile_id, profile)
        # activate first available profile
        self.switch()

        props["profiles"].wire(self.handleProfileUpdate)

    def addLayer(self, profile_id, profile):
        profile_stack = PropertyStack()
        profile_stack.addLayer(0, PropertyLayer(profile_id=profile_id).readonly())
        profile_stack.addLayer(1, profile)
        super().addLayer(profile_id, profile_stack)

    def handleProfileUpdate(self, changes):
        for profile_id, profile in changes.items():
            if profile is PropertyDeleted:
                self.removeLayer(profile_id)
            else:
                self.addLayer(profile_id, profile)

    def _getDefaultLayer(self):
        # return the first available profile, or the default empty layer if we don't have any
        if self.layers:
            return next(iter(self.layers.values()))
        return super()._getDefaultLayer()


class SdrSource(ABC):
    def __init__(self, id, props):
        self.id = id

        self.commandMapper = None
        self.tcpSource = None
        self.buffer = None

        self.props = PropertyStack()

        # layer 0 reserved for profile properties
        self.profileCarousel = SdrProfileCarousel(props)
        # prevent profile names from overriding the device name
        self.props.addLayer(0, PropertyFilter(self.profileCarousel, ByLambda(lambda x: x != "name")))

        # props from our device config
        self.props.addLayer(1, props)

        # the sdr_id is constant, so we put it in a separate layer
        # this is used to detect device changes, that are then sent to the client
        self.props.addLayer(2, PropertyLayer(sdr_id=id).readonly())

        # finally, accept global config properties from the top-level config
        self.props.addLayer(3, Config.get())

        self.sdrProps = self.props.filter(*self.getEventNames())

        self.wireEvents()

        self.port = getAvailablePort()
        self.monitor = None
        self.clients = []
        self.spectrumClients = []
        self.spectrumThread = None
        self.spectrumLock = threading.Lock()
        self.process = None
        self.modificationLock = threading.Lock()
        self.state = SdrSourceState.STOPPED
        self.enabled = "enabled" not in props or props["enabled"]
        props.filter("enabled").wire(self._handleEnableChanged)
        self.failed = False
        self.busyState = SdrBusyState.IDLE

        self.validateProfiles()

        if self.isAlwaysOn() and self.isEnabled():
            self.start()

    def isEnabled(self):
        return self.enabled

    def _handleEnableChanged(self, changes):
        if "enabled" in changes and changes["enabled"] is not PropertyDeleted:
            self.enabled = changes["enabled"]
        else:
            self.enabled = True
        if not self.enabled:
            self.stop()
        for c in self.clients.copy():
            if self.isEnabled():
                c.onEnable()
            else:
                c.onDisable()

    def isFailed(self):
        return self.failed

    def fail(self):
        self.failed = True
        for c in self.clients.copy():
            c.onFail()

    def validateProfiles(self):
        props = PropertyStack()
        props.addLayer(1, self.props)
        for id, p in self.props["profiles"].items():
            props.replaceLayer(0, p)
            if "center_freq" not in props:
                logger.warning('Profile "%s" does not specify a center_freq', id)
                continue
            if "samp_rate" not in props:
                logger.warning('Profile "%s" does not specify a samp_rate', id)
                continue
            if "start_freq" in props:
                start_freq = props["start_freq"]
                srh = props["samp_rate"] / 2
                center_freq = props["center_freq"]
                if start_freq < center_freq - srh or start_freq > center_freq + srh:
                    logger.warning('start_freq for profile "%s" is out of range', id)

    def isAlwaysOn(self):
        return "always-on" in self.props and self.props["always-on"]

    def getEventNames(self):
        return [
            "samp_rate",
            "center_freq",
            "ppm",
            "rf_gain",
            "lfo_offset",
        ] + list(self.getCommandMapper().keys())

    def getCommandMapper(self):
        if self.commandMapper is None:
            self.commandMapper = CommandMapper()
        return self.commandMapper

    @abstractmethod
    def onPropertyChange(self, changes):
        pass

    def wireEvents(self):
        self.sdrProps.wire(self.onPropertyChange)

    def getCommand(self):
        return [self.getCommandMapper().map(self.getCommandValues())]

    def activateProfile(self, profile_id):
        logger.debug("activating profile {0} for {1}".format(profile_id, self.getId()))
        try:
            self.profileCarousel.switch(profile_id)
        except KeyError:
            logger.warning("invalid profile %s for sdr %s. ignoring", profile_id, self.getId())

    def getId(self):
        return self.id

    def getProfileId(self):
        return self.props["profile_id"]

    def getProfiles(self):
        return self.props["profiles"]

    def getName(self):
        return self.props["name"]

    def getProps(self):
        return self.props

    def getPort(self):
        return self.port

    def _getTcpSource(self):
        with self.modificationLock:
            if self.tcpSource is None:
                self.tcpSource = TcpSource(self.port, Format.COMPLEX_FLOAT)
        return self.tcpSource

    def getBuffer(self):
        if self.buffer is None:
            self.buffer = Buffer(Format.COMPLEX_FLOAT)
            self._getTcpSource().setWriter(self.buffer)
        return self.buffer

    def getCommandValues(self):
        dict = self.sdrProps.__dict__()
        if "lfo_offset" in dict and dict["lfo_offset"] is not None:
            dict["tuner_freq"] = dict["center_freq"] + dict["lfo_offset"]
        else:
            dict["tuner_freq"] = dict["center_freq"]
        return dict

    def start(self):
        with self.modificationLock:
            if self.monitor:
                return

            if self.isFailed():
                return

            try:
                self.preStart()
            except Exception:
                logger.exception("Exception during preStart()")

            cmd = self.getCommand()
            cmd = [c for c in cmd if c is not None]

            # don't use shell mode for commands without piping
            if len(cmd) > 1:
                # multiple commands with pipes
                cmd = "|".join(cmd)
                self.process = subprocess.Popen(cmd, shell=True, start_new_session=True)
            else:
                # single command
                cmd = cmd[0]
                # start_new_session can go as soon as there's no piped commands left
                # the os.killpg call must be replaced with something more reasonable at the same time
                self.process = subprocess.Popen(shlex.split(cmd), start_new_session=True)
            logger.info("Started sdr source: " + cmd)

            available = False
            failed = False

            def wait_for_process_to_end():
                nonlocal failed
                rc = self.process.wait()
                logger.debug("shut down with RC={0}".format(rc))
                self.process = None
                self.monitor = None
                if self.getState() is SdrSourceState.RUNNING:
                    self.fail()
                else:
                    failed = True
                self.setState(SdrSourceState.STOPPED)

            self.monitor = threading.Thread(target=wait_for_process_to_end, name="source_monitor")
            self.monitor.start()

            retries = 1000
            while retries > 0 and not failed:
                retries -= 1
                if self.monitor is None:
                    break
                testsock = socket.socket()
                testsock.settimeout(1)
                try:
                    testsock.connect(("127.0.0.1", self.getPort()))
                    testsock.close()
                    available = True
                    break
                except:
                    time.sleep(0.1)

            if not available:
                failed = True

            try:
                self.postStart()
            except Exception:
                logger.exception("Exception during postStart()")
                failed = True

        if failed:
            self.fail()
        else:
            self.setState(SdrSourceState.RUNNING)

    def preStart(self):
        """
        override this method in subclasses if there's anything to be done before starting up the actual SDR
        """
        pass

    def postStart(self):
        """
        override this method in subclasses if there's things to do after the actual SDR has started up
        """
        pass

    def isAvailable(self):
        return self.monitor is not None

    def stop(self):
        with self.modificationLock:
            if self.process is not None:
                self.setState(SdrSourceState.STOPPING)
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    if self.monitor:
                        # wait 10 seconds for a regular shutdown
                        self.monitor.join(10)
                        # if the monitor is still running, the process still hasn't ended, so kill it
                    if self.monitor:
                        logger.warning("source has not shut down normally within 10 seconds, sending SIGKILL")
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    # been killed by something else, ignore
                    pass
                except AttributeError:
                    # self.process has been overwritten by the monitor since we checked it, which is fine
                    pass
            if self.monitor:
                self.monitor.join()
            if self.tcpSource is not None:
                self.tcpSource.stop()
                self.tcpSource = None
                self.buffer = None

    def shutdown(self):
        self.stop()
        for c in self.clients.copy():
            c.onShutdown()

    def getClients(self, *args):
        if not args:
            return self.clients
        return [c for c in self.clients if c.getClientClass() in args]

    def hasClients(self, *args):
        return len(self.getClients(*args)) > 0

    def addClient(self, c: SdrSourceEventClient):
        if c in self.clients:
            return
        self.clients.append(c)
        c.onStateChange(self.getState())
        hasUsers = self.hasClients(SdrClientClass.USER)
        hasBackgroundTasks = self.hasClients(SdrClientClass.BACKGROUND)
        if hasUsers or hasBackgroundTasks:
            self.start()
            self.setBusyState(SdrBusyState.BUSY if hasUsers else SdrBusyState.IDLE)

    def removeClient(self, c: SdrSourceEventClient):
        if c not in self.clients:
            return

        self.clients.remove(c)

        self.checkStatus()

    def checkStatus(self):
        hasUsers = self.hasClients(SdrClientClass.USER)
        self.setBusyState(SdrBusyState.BUSY if hasUsers else SdrBusyState.IDLE)

        # no need to check for users if we are always-on
        if self.isAlwaysOn():
            return

        hasBackgroundTasks = self.hasClients(SdrClientClass.BACKGROUND)
        if not hasUsers and not hasBackgroundTasks:
            self.stop()

    def addSpectrumClient(self, c):
        if c in self.spectrumClients:
            return

        # local import due to circular depencency
        from owrx.fft import SpectrumThread

        self.spectrumClients.append(c)
        with self.spectrumLock:
            if self.spectrumThread is None:
                self.spectrumThread = SpectrumThread(self)
                self.spectrumThread.start()

    def removeSpectrumClient(self, c):
        try:
            self.spectrumClients.remove(c)
        except ValueError:
            pass
        with self.spectrumLock:
            if not self.spectrumClients and self.spectrumThread is not None:
                self.spectrumThread.stop()
                self.spectrumThread = None

    def writeSpectrumData(self, data):
        for c in self.spectrumClients:
            c.write_spectrum_data(data)

    def getState(self) -> SdrSourceState:
        return self.state

    def setState(self, state: SdrSourceState):
        if state == self.state:
            return
        self.state = state
        for c in self.clients.copy():
            c.onStateChange(state)

    def setBusyState(self, state: SdrBusyState):
        if state == self.busyState:
            return
        self.busyState = state
        for c in self.clients.copy():
            c.onBusyStateChange(state)


class SdrDeviceDescriptionMissing(Exception):
    pass


class SdrDeviceDescription(object):
    @staticmethod
    def getByType(sdr_type: str) -> "SdrDeviceDescription":
        try:
            className = "".join(x for x in sdr_type.title() if x.isalnum()) + "DeviceDescription"
            module = __import__("owrx.source.{0}".format(sdr_type), fromlist=[className])
            cls = getattr(module, className)
            return cls()
        except (ImportError, AttributeError):
            raise SdrDeviceDescriptionMissing("Device description for type {} not available".format(sdr_type))

    @staticmethod
    def getTypes():
        def get_description(module_name):
            try:
                description = SdrDeviceDescription.getByType(module_name)
                return description.getName()
            except SdrDeviceDescriptionMissing:
                return None

        descriptions = {
            module_name: get_description(module_name) for _, module_name, _ in pkgutil.walk_packages(__path__)
        }
        # filter out empty names and unavailable types
        fd = FeatureDetector()
        return {k: v for k, v in descriptions.items() if v is not None and fd.is_available(k)}

    def getName(self):
        """
        must be overridden with a textual representation of the device, to be used for device type selection

        :return: str
        """
        return None

    def supportsPpm(self):
        """
        can be overridden if the device does not support configuring PPM correction

        :return: bool
        """
        return True

    def getDeviceInputs(self) -> List[Input]:
        keys = self.getDeviceMandatoryKeys() + self.getDeviceOptionalKeys()
        return [TextInput("name", "Device name", validator=RequiredValidator())] + [
            i for i in self.getInputs() if i.id in keys
        ]

    def getProfileInputs(self) -> List[Input]:
        keys = self.getProfileMandatoryKeys() + self.getProfileOptionalKeys()
        return [TextInput("name", "Profile name", validator=RequiredValidator())] + [
            i for i in self.getInputs() if i.id in keys
        ]

    def getInputs(self) -> List[Input]:
        return [
            CheckboxInput("enabled", "Enable this device", converter=OptionalConverter(defaultFormValue=True)),
            GainInput("rf_gain", "Device gain", self.hasAgc()),
            NumberInput(
                "ppm",
                "Frequency correction",
                append="ppm",
            ),
            CheckboxInput(
                "always-on",
                "Keep device running at all times",
                infotext="Prevents shutdown of the device when idle. Useful for devices with unreliable startup.",
            ),
            CheckboxInput(
                "services",
                "Run background services on this device",
            ),
            ExponentialInput(
                "lfo_offset",
                "Oscillator offset",
                "Hz",
                infotext="Use this when the actual receiving frequency differs from the frequency to be tuned on the"
                + " device. <br/> Formula: Center frequency + oscillator offset = sdr tune frequency",
            ),
            WaterfallLevelsInput("waterfall_levels", "Waterfall levels"),
            SchedulerInput("scheduler", "Scheduler"),
            ExponentialInput("center_freq", "Center frequency", "Hz"),
            ExponentialInput("samp_rate", "Sample rate", "S/s"),
            ExponentialInput("start_freq", "Initial frequency", "Hz"),
            ModesInput("start_mod", "Initial modulation"),
            DropdownInput(
                "tuning_step",
                "Tuning step",
                options=[Option(str(i), "{} Hz".format(i)) for i in [1, 100, 500, 1000, 2500, 3000, 3125, 5000, 6000, 9000, 10000, 12000, 12500, 25000, 50000, 100000]],
                converter=IntConverter(),
            ),
            NumberInput("initial_squelch_level", "Initial squelch level", append="dBFS"),
        ]

    def hasAgc(self):
        # default is True since most devices have agc. override in subclasses if agc is not available
        return True

    def getDeviceMandatoryKeys(self):
        return ["name", "enabled"]

    def getDeviceOptionalKeys(self):
        keys = [
            "always-on",
            "services",
            "rf_gain",
            "lfo_offset",
            "waterfall_levels",
            "scheduler",
        ]
        if self.supportsPpm():
            keys += ["ppm"]
        return keys

    def getProfileMandatoryKeys(self):
        return ["name", "center_freq", "samp_rate", "start_freq", "start_mod", "tuning_step"]

    def getProfileOptionalKeys(self):
        return ["initial_squelch_level", "rf_gain", "lfo_offset", "waterfall_levels"]

    def getDeviceSection(self):
        return OptionalSection(
            "Device settings", self.getDeviceInputs(), self.getDeviceMandatoryKeys(), self.getDeviceOptionalKeys()
        )

    def getProfileSection(self):
        return OptionalSection(
            "Profile settings",
            self.getProfileInputs(),
            self.getProfileMandatoryKeys(),
            self.getProfileOptionalKeys(),
        )
