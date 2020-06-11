import subprocess
from functools import reduce
from operator import and_, or_
import re
from distutils.version import LooseVersion
import inspect
from owrx.config import Config
import shlex

import logging

logger = logging.getLogger(__name__)


class UnknownFeatureException(Exception):
    pass


class FeatureDetector(object):
    features = {
        # core features; we won't start without these
        "core": ["csdr", "nmux", "nc"],
        # different types of sdrs and their requirements
        "rtl_sdr": ["rtl_connector"],
        "rtl_sdr_soapy": ["soapy_connector", "soapy_rtl_sdr"],
        "sdrplay": ["soapy_connector", "soapy_sdrplay"],
        "hackrf": ["soapy_connector", "soapy_hackrf"],
        "perseussdr": ["perseustest"],
        "airspy": ["soapy_connector", "soapy_airspy"],
        "airspyhf": ["soapy_connector", "soapy_airspyhf"],
        "lime_sdr": ["soapy_connector", "soapy_lime_sdr"],
        "fifi_sdr": ["alsa", "rockprog"],
        "file_player": ["xzcat"],
        "pluto_sdr": ["soapy_connector", "soapy_pluto_sdr"],
        "soapy_remote": ["soapy_connector", "soapy_remote"],
        "uhd": ["soapy_connector", "soapy_uhd"],
        "red_pitaya": ["soapy_connector", "soapy_red_pitaya"],
        "radioberry": ["soapy_connector", "soapy_radioberry"],
        # optional features and their requirements
        "digital_voice_digiham": ["digiham", "sox"],
        "digital_voice_dsd": ["dsd", "sox", "digiham"],
        "wsjt-x": ["wsjtx", "sox"],
        "packet": ["direwolf", "sox"],
        "pocsag": ["digiham", "sox"],
        "js8call": ["js8", "sox"],
    }

    def feature_availability(self):
        return {name: self.is_available(name) for name in FeatureDetector.features}

    def feature_report(self):
        def requirement_details(name):
            available = self.has_requirement(name)
            return {
                "available": available,
                # as of now, features are always enabled as soon as they are available. this may change in the future.
                "enabled": available,
                "description": self.get_requirement_description(name),
            }

        def feature_details(name):
            return {
                "description": "",
                "available": self.is_available(name),
                "requirements": {name: requirement_details(name) for name in self.get_requirements(name)},
            }

        return {name: feature_details(name) for name in FeatureDetector.features}

    def is_available(self, feature):
        return self.has_requirements(self.get_requirements(feature))

    def get_requirements(self, feature):
        try:
            return FeatureDetector.features[feature]
        except KeyError:
            raise UnknownFeatureException('Feature "{0}" is not known.'.format(feature))

    def has_requirements(self, requirements):
        passed = True
        for requirement in requirements:
            passed = passed and self.has_requirement(requirement)
        return passed

    def _get_requirement_method(self, requirement):
        methodname = "has_" + requirement
        if hasattr(self, methodname) and callable(getattr(self, methodname)):
            return getattr(self, methodname)
        return None

    def has_requirement(self, requirement):
        method = self._get_requirement_method(requirement)
        if method is not None:
            return method()
        else:
            logger.error("detection of requirement {0} not implement. please fix in code!".format(requirement))
        return False

    def get_requirement_description(self, requirement):
        return inspect.getdoc(self._get_requirement_method(requirement))

    def command_is_runnable(self, command):
        tmp_dir = Config.get()["temporary_directory"]
        cmd = shlex.split(command)
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=tmp_dir)
            return process.wait() != 32512
        except FileNotFoundError:
            return False

    def has_csdr(self):
        """
        OpenWebRX uses the demodulator and pipeline tools provided by the csdr project. Please check out [the project
        page on github](https://github.com/jketterl/csdr) for further details and installation instructions.
        """
        return self.command_is_runnable("csdr")

    def has_nmux(self):
        """
        Nmux is another tool provided by the csdr project. It is used for internal multiplexing of the IQ data streams.
        If you're missing nmux even though you have csdr installed, please update your csdr version.
        """
        return self.command_is_runnable("nmux --help")

    def has_nc(self):
        """
        Nc is the client used to connect to the nmux multiplexer. It is provided by either the BSD netcat (recommended
        for better performance) or GNU netcat packages. Please check your distribution package manager for options.
        """
        return self.command_is_runnable("nc --help")

    def has_perseustest(self):
        """
        To use a Microtelecom Perseus HF receiver, compile and
        install the libperseus-sdr:
        ```
         sudo apt install libusb-1.0-0-dev
         cd /tmp
         wget https://github.com/Microtelecom/libperseus-sdr/releases/download/v0.8.2/libperseus_sdr-0.8.2.tar.gz
         tar -zxvf libperseus_sdr-0.8.2.tar.gz
         cd libperseus_sdr-0.8.2/
         ./configure
         make
         sudo make install
         sudo ldconfig
         perseustest
        ```
        """
        return self.command_is_runnable("perseustest -h")


    def has_digiham(self):
        """
        To use digital voice modes, the digiham package is required. You can find the package and installation
        instructions [here](https://github.com/jketterl/digiham).

        Please note: there is close interaction between digiham and openwebrx, so older versions will probably not work.
        If you have an older verison of digiham installed, please update it along with openwebrx.
        As of now, we require version 0.3 of digiham.
        """
        required_version = LooseVersion("0.3")

        digiham_version_regex = re.compile("^digiham version (.*)$")

        def check_digiham_version(command):
            try:
                process = subprocess.Popen([command, "--version"], stdout=subprocess.PIPE)
                matches = digiham_version_regex.match(process.stdout.readline().decode())
                if matches is None:
                    return False
                version = LooseVersion(matches.group(1))
                process.wait(1)
                return version >= required_version
            except FileNotFoundError:
                return False

        return reduce(
            and_,
            map(
                check_digiham_version,
                [
                    "rrc_filter",
                    "ysf_decoder",
                    "dmr_decoder",
                    "mbe_synthesizer",
                    "gfsk_demodulator",
                    "digitalvoice_filter",
                    "fsk_demodulator",
                    "pocsag_decoder",
                ],
            ),
            True,
        )

    def _check_connector(self, command):
        required_version = LooseVersion("0.2")

        owrx_connector_version_regex = re.compile("^owrx-connector version (.*)$")

        try:
            process = subprocess.Popen([command, "--version"], stdout=subprocess.PIPE)
            matches = owrx_connector_version_regex.match(process.stdout.readline().decode())
            if matches is None:
                return False
            version = LooseVersion(matches.group(1))
            process.wait(1)
            return version >= required_version
        except FileNotFoundError:
            return False

    def has_rtl_connector(self):
        """
        The owrx_connector package offers direct interfacing between your hardware and openwebrx. It allows quicker
        frequency switching, uses less CPU and can even provide more stability in some cases.

        You can get it [here](https://github.com/jketterl/owrx_connector).
        """
        return self._check_connector("rtl_connector")

    def has_soapy_connector(self):
        """
        The owrx_connector package offers direct interfacing between your hardware and openwebrx. It allows quicker
        frequency switching, uses less CPU and can even provide more stability in some cases.

        You can get it [here](https://github.com/jketterl/owrx_connector).
        """
        return self._check_connector("soapy_connector")

    def _has_soapy_driver(self, driver):
        try:
            process = subprocess.Popen(["SoapySDRUtil", "--info"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            factory_regex = re.compile("^Available factories\\.\\.\\. ?(.*)$")

            drivers = []
            for line in process.stdout:
                matches = factory_regex.match(line.decode())
                if matches:
                    drivers = [s.strip() for s in matches.group(1).split(", ")]

            return driver in drivers
        except FileNotFoundError:
            return False

    def has_soapy_rtl_sdr(self):
        """
        The SoapySDR module for rtl-sdr devices can be used as an alternative to the rtl_connector. It provides
        additional support for the direct sampling mod.

        You can get it [here](https://github.com/pothosware/SoapyRTLSDR/wiki).
        """
        return self._has_soapy_driver("rtlsdr")

    def has_soapy_sdrplay(self):
        """
        The SoapySDR module for sdrplay devices is required for interfacing with SDRPlay devices (RSP1*, RSP2*, RSPDuo)

        You can get it [here](https://github.com/SDRplay/SoapySDRPlay).
        """
        return self._has_soapy_driver("sdrplay")

    def has_soapy_airspy(self):
        """
        The SoapySDR module for airspy devices is required for interfacing with Airspy devices (Airspy R2, Airspy Mini).

        You can get it [here](https://github.com/pothosware/SoapyAirspy/wiki).
        """
        return self._has_soapy_driver("airspy")

    def has_soapy_airspyhf(self):
        """
        The SoapySDR module for airspyhf devices is required for interfacing with Airspy HF devices (Airspy HF+,
        Airspy HF discovery).

        You can get it [here](https://github.com/pothosware/SoapyAirspyHF/wiki).
        """
        return self._has_soapy_driver("airspyhf")

    def has_soapy_lime_sdr(self):
        """
        The Lime Suite installs - amongst others - a Soapy driver for the LimeSDR device series.

        You can get it [here](https://github.com/myriadrf/LimeSuite).
        """
        return self._has_soapy_driver("lime")

    def has_soapy_pluto_sdr(self):
        """
        The SoapySDR module for PlutoSDR devices is required for interfacing with PlutoSDR devices.

        You can get it [here](https://github.com/photosware/SoapyPlutoSDR).
        """
        return self._has_soapy_driver("plutosdr")

    def has_soapy_remote(self):
        """
        The SoapyRemote allows the usage of remote SDR devices using the SoapySDRServer.

        You can get the code and find additional information [here](https://github.com/pothosware/SoapyRemote/wiki).
        """
        return self._has_soapy_driver("remote")

    def has_soapy_uhd(self):
        """
        The SoapyUHD module allows using UHD / USRP devices with SoapySDR.

        You can get it [here](https://github.com/pothosware/SoapyUHD/wiki).
        """
        return self._has_soapy_driver("uhd")

    def has_soapy_red_pitaya(self):
        """
        The SoapyRedPitaya allows Red Pitaya deviced to be used with SoapySDR.

        You can get it [here](https://github.com/pothosware/SoapyRedPitaya/wiki).
        """
        return self._has_soapy_driver("redpitaya")

    def has_soapy_radioberry(self):
        """
        The Radioberry is a SDR hat for the Raspberry Pi.

        You can find more information, along with its SoapySDR module [here](https://github.com/pa3gsb/Radioberry-2.x).
        """
        return self._has_soapy_driver("radioberry")

    def has_soapy_hackrf(self):
        """
        The SoapyHackRF allows HackRF to be used with SoapySDR.

        You can get it [here](https://github.com/pothosware/SoapyHackRF/wiki).
        """
        return self._has_soapy_driver("hackrf")

    def has_dsd(self):
        """
        The digital voice modes NXDN and D-Star can be decoded by the dsd project. Please note that you need the version
        modified by F4EXB that provides stdin/stdout support. You can find it [here](https://github.com/f4exb/dsd).
        """
        return self.command_is_runnable("dsd")

    def has_sox(self):
        """
        The sox audio library is used to convert between the typical 8 kHz audio sampling rate used by digital modes and
        the audio sampling rate requested by the client.

        It is available for most distributions through the respective package manager.
        """
        return self.command_is_runnable("sox")

    def has_direwolf(self):
        """
        OpenWebRX uses the [direwolf](https://github.com/wb2osz/direwolf) software modem to decode Packet Radio and
        report data back to APRS-IS. Direwolf is available from the package manager on many distributions, or you can
        compile it from source.
        """
        return self.command_is_runnable("direwolf --help")

    def has_airspy_rx(self):
        """
        In order to use an Airspy Receiver, you need to install the airspy_rx receiver software.
        """
        return self.command_is_runnable("airspy_rx --help")

    def has_wsjtx(self):
        """
        To decode FT8 and other digimodes, you need to install the WSJT-X software suite. Please check the
        [WSJT-X homepage](https://physics.princeton.edu/pulsar/k1jt/wsjtx.html) for ready-made packages or instructions
        on how to build from source.
        """
        return reduce(and_, map(self.command_is_runnable, ["jt9", "wsprd"]), True)

    def has_js8(self):
        """
        To decode JS8, you will need to install [JS8Call](http://js8call.com/)

        Please note that the `js8` command line decoder is not made available on $PATH by some JS8Call package builds.
        You will need to manually make it available by either linking it to `/usr/bin` or by adding its location to
        $PATH.
        """
        return self.command_is_runnable("js8")

    def has_alsa(self):
        """
        Some SDR receivers are identifying themselves as a soundcard. In order to read their data, OpenWebRX relies
        on the Alsa library. It is available as a package for most Linux distributions.
        """
        return self.command_is_runnable("arecord --help")

    def has_rockprog(self):
        """
        The "rockprog" executable is required to send commands to your FiFiSDR. It needs to be installed separately.

        You can find instructions and downloads [here](https://o28.sischa.net/fifisdr/trac/wiki/De%3Arockprog).
        """
        return self.command_is_runnable("rockprog")

    def has_xzcat(self):
        """
        The "xzcat" executable is required to use the file player. It needs to be installed separately.

        Install it from a system package manager, e.g. "sudo apt-get install xz-utils".
        """
        return self.command_is_runnable("xzcat")
