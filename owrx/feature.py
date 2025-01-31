import subprocess
from functools import reduce
from operator import and_
import re
from distutils.version import LooseVersion, StrictVersion
import inspect
from owrx.config.core import CoreConfig
from owrx.config import Config
import shlex
import os
from datetime import datetime, timedelta

import logging

logger = logging.getLogger(__name__)


class UnknownFeatureException(Exception):
    pass


class FeatureCache(object):
    sharedInstance = None

    @staticmethod
    def getSharedInstance():
        if FeatureCache.sharedInstance is None:
            FeatureCache.sharedInstance = FeatureCache()
        return FeatureCache.sharedInstance

    def __init__(self):
        self.cache = {}
        self.cachetime = timedelta(hours=2)

    def has(self, feature):
        if feature not in self.cache:
            return False
        now = datetime.now()
        if self.cache[feature]["valid_to"] < now:
            return False
        return True

    def get(self, feature):
        return self.cache[feature]["value"]

    def set(self, feature, value):
        valid_to = datetime.now() + self.cachetime
        self.cache[feature] = {"value": value, "valid_to": valid_to}


class FeatureDetector(object):
    features = {
        # core features; we won't start without these
        "core": ["csdr"],
        # different types of sdrs and their requirements
        "rtl_sdr": ["rtl_connector"],
        "rtl_sdr_soapy": ["soapy_connector", "soapy_rtl_sdr"],
        "rtl_tcp": ["rtl_tcp_connector"],
        "sdrplay": ["soapy_connector", "soapy_sdrplay"],
        "hackrf": ["soapy_connector", "soapy_hackrf"],
        "perseussdr": ["perseustest", "nmux"],
        "airspy": ["soapy_connector", "soapy_airspy"],
        "airspyhf": ["soapy_connector", "soapy_airspyhf"],
        "afedri": ["soapy_connector", "soapy_afedri"],
        "lime_sdr": ["soapy_connector", "soapy_lime_sdr"],
        "fifi_sdr": ["alsa", "rockprog", "nmux"],
        "pluto_sdr": ["soapy_connector", "soapy_pluto_sdr"],
        "soapy_remote": ["soapy_connector", "soapy_remote"],
        "uhd": ["soapy_connector", "soapy_uhd"],
        "radioberry": ["soapy_connector", "soapy_radioberry"],
        "fcdpp": ["soapy_connector", "soapy_fcdpp"],
        "bladerf": ["soapy_connector", "soapy_bladerf"],
        "sddc": ["sddc_connector"],
        "hpsdr": ["hpsdr_connector"],
        "runds": ["runds_connector"],
        # optional features and their requirements
        "digital_voice_digiham": ["digiham", "codecserver_ambe"],
        "digital_voice_freedv": ["freedv_rx"],
        "digital_voice_m17": ["m17_demod"],
        "wsjt-x": ["wsjtx"],
        "wsjt-x-2-3": ["wsjtx_2_3"],
        "wsjt-x-2-4": ["wsjtx_2_4"],
        "msk144": ["msk144decoder"],
        "packet": ["direwolf"],
        "pocsag": ["digiham"],
        "js8call": ["js8", "js8py"],
        "drm": ["dream"],
        "dump1090": ["dump1090"],
        "ism": ["rtl_433"],
        "dumphfdl": ["dumphfdl"],
        "dumpvdl2": ["dumpvdl2"],
        "redsea": ["redsea"],
        "dab": ["csdreti", "dablin"],
        "mqtt": ["paho_mqtt"],
        "hdradio": ["nrsc5"],
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
                "available": self.is_available(name),
                "requirements": {name: requirement_details(name) for name in self.get_requirements(name)},
            }

        return {name: feature_details(name) for name in FeatureDetector.features}

    def is_available(self, feature):
        return self.has_requirements(self.get_requirements(feature))

    def get_failed_requirements(self, feature):
        return [req for req in self.get_requirements(feature) if not self.has_requirement(req)]

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
        cache = FeatureCache.getSharedInstance()
        if cache.has(requirement):
            return cache.get(requirement)

        method = self._get_requirement_method(requirement)
        result = False
        if method is not None:
            result = method()
        else:
            logger.error("detection of requirement {0} not implement. please fix in code!".format(requirement))

        cache.set(requirement, result)
        return result

    def get_requirement_description(self, requirement):
        return inspect.getdoc(self._get_requirement_method(requirement))

    def command_is_runnable(self, command, expected_result=None):
        tmp_dir = CoreConfig().get_temporary_directory()
        cmd = shlex.split(command)
        env = os.environ.copy()
        # prevent X11 programs from opening windows if called from a GUI shell
        env.pop("DISPLAY", None)
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=tmp_dir,
                env=env,
            )
            while True:
                try:
                    rc = process.wait(10)
                    break
                except subprocess.TimeoutExpired:
                    logger.warning("feature check command \"%s\" did not return after 10 seconds!", command)
                    process.kill()

            if expected_result is None:
                return rc != 32512
            else:
                return rc == expected_result
        except FileNotFoundError:
            return False

    def has_csdr(self):
        """
        OpenWebRX uses the demodulator and pipeline tools provided by the
        [csdr project](https://github.com/jketterl/csdr).

        In addition, [pycsdr](https://github.com/jketterl/pycsdr) must be installed to provide python bindings for the
        csdr library.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `python3-csdr`.
        """
        required_version = LooseVersion("0.19.0")

        try:
            from pycsdr.modules import csdr_version
            from pycsdr.modules import version as pycsdr_version

            return (
                LooseVersion(csdr_version) >= required_version and
                LooseVersion(pycsdr_version) >= required_version
            )
        except ImportError:
            return False

    def has_nmux(self):
        """
        Nmux is a tool provided by the csdr project. It is used for internal multiplexing of the IQ data streams.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `nmux`.
        """
        return self.command_is_runnable("nmux --help")

    def has_perseustest(self):
        """
        To use a Microtelecom Perseus HF receiver, you need the `perseustest` utility from
        [libperseus-sdr](https://github.com/Microtelecom/libperseus-sdr).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `perseus-tools`.
        """
        return self.command_is_runnable("perseustest -h")

    def has_digiham(self):
        """
        To use digital voice modes, [digiham](https://github.com/jketterl/digiham) is required.

        In addition, [pydigiham](https://github.com/jketterl/pydigiham) must be installed to provide python bindings
        for the digiham library.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `python3-digiham`.
        """
        required_version = LooseVersion("0.6")

        try:
            from digiham.modules import digiham_version as digiham_version
            from digiham.modules import version as pydigiham_version

            return (
                LooseVersion(digiham_version) >= required_version
                and LooseVersion(pydigiham_version) >= required_version
            )
        except ImportError:
            return False

    def _check_connector(self, command, required_version):
        owrx_connector_version_regex = re.compile("^{} version (.*)$".format(re.escape(command)))

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

    def _check_owrx_connector(self, command):
        return self._check_connector(command, LooseVersion("0.7"))

    def has_rtl_connector(self):
        """
        The [owrx_connector](https://github.com/jketterl/owrx_connector) offers direct interfacing between your
        hardware and OpenWebRX.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `owrx-connector`.
        """
        return self._check_owrx_connector("rtl_connector")

    def has_rtl_tcp_connector(self):
        """
        The [owrx_connector](https://github.com/jketterl/owrx_connector) offers direct interfacing between your
        hardware and OpenWebRX.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `owrx-connector`.
        """
        return self._check_owrx_connector("rtl_tcp_connector")

    def has_soapy_connector(self):
        """
        The [owrx_connector](https://github.com/jketterl/owrx_connector) offers direct interfacing between your
        hardware and OpenWebRX.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `owrx-connector`.
        """
        return self._check_owrx_connector("soapy_connector")

    def _has_soapy_driver(self, driver):
        try:
            process = subprocess.Popen(["soapy_connector", "--listdrivers"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            drivers = [line.decode().strip() for line in process.stdout]
            process.wait(1)

            return driver in drivers
        except FileNotFoundError:
            return False

    def has_soapy_rtl_sdr(self):
        """
        The [SoapyRTLSDR](https://github.com/pothosware/SoapyRTLSDR/wiki) module can be used as an alternative to
        rtl_connector.

        Debian and Ubuntu users should be able to install the package `soapysdr-module-rtlsdr` from their distribution.
        """
        return self._has_soapy_driver("rtlsdr")

    def has_soapy_sdrplay(self):
        """
        The [SoapySDRPlay3](https://github.com/pothosware/SoapySDRPlay3) module is required for interfacing with
        SDRPlay devices (RSP1\\*, RSP2\\*, RSPDuo)
        """
        return self._has_soapy_driver("sdrplay")

    def has_soapy_airspy(self):
        """
        The [SoapyAirspy](https://github.com/pothosware/SoapyAirspy/wiki) module is required for interfacing with
        Airspy devices (Airspy R2, Airspy Mini).

        Debian and Ubuntu users should be able to install the package `soapysdr-module-airspy` from their distribution.
        """
        return self._has_soapy_driver("airspy")

    def has_soapy_airspyhf(self):
        """
        The [SoapyAirspyHF](https://github.com/pothosware/SoapyAirspyHF/wiki) module is required for interfacing with
        Airspy HF devices (Airspy HF+, Airspy HF discovery).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `soapysdr-module-airspyhf`.
        """
        return self._has_soapy_driver("airspyhf")

    def has_soapy_afedri(self):
        """
        The [SoapyAfedri](https://github.com/alexander-sholohov/SoapyAfedri) module allows using Afedri SDR-Net devices
        with SoapySDR.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `soapysdr-module-afedri`.
        """
        return self._has_soapy_driver("afedri")

    def has_soapy_lime_sdr(self):
        """
        The [LimeSuite](https://github.com/myriadrf/LimeSuite) installs - amongst other software - a Soapy driver for
        the LimeSDR device series.

        Debian and Ubuntu users should be able to install the package `soapysdr-module-lms7` from their distribution.
        """
        return self._has_soapy_driver("lime")

    def has_soapy_pluto_sdr(self):
        """
        The [SoapyPlutoSDR](https://github.com/pothosware/SoapyPlutoSDR) module is required for interfacing with
        PlutoSDR devices.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `soapysdr-module-plutosdr`.
        """
        return self._has_soapy_driver("plutosdr")

    def has_soapy_remote(self):
        """
        SoapyRemote allows the usage of remote SDR devices over the network using SoapySDRServer.

        You can get the code and find additional information [here](https://github.com/pothosware/SoapyRemote/wiki).

        Debian and Ubuntu users should be able to install the package `soapysdr-module-remote` from their distribution.
        """
        return self._has_soapy_driver("remote")

    def has_soapy_uhd(self):
        """
        The [SoapyUHD](https://github.com/pothosware/SoapyUHD/wiki) module allows using UHD / USRP devices with
        SoapySDR.

        Debian and Ubuntu users should be able to install the package `soapysdr-module-uhd` from their distribution.
        """
        return self._has_soapy_driver("uhd")

    def has_soapy_radioberry(self):
        """
        The Radioberry is a SDR hat for the Raspberry Pi.

        You can find more information, along with its SoapySDR module [here](https://github.com/pa3gsb/Radioberry-2.x).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `soapysdr-module-radioberry`.
        """
        return self._has_soapy_driver("radioberry")

    def has_soapy_hackrf(self):
        """
        [SoapyHackRF](https://github.com/pothosware/SoapyHackRF/wiki) allows HackRF devices to be used with SoapySDR.

        Debian and Ubuntu users should be able to install the package `soapysdr-module-hackrf` from their distribution.
        """
        return self._has_soapy_driver("hackrf")

    def has_soapy_fcdpp(self):
        """
        The [SoapyFCDPP](https://github.com/pothosware/SoapyFCDPP) module allows the use of the Funcube Dongle Pro+.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `soapysdr-module-fcdpp`.
        """
        return self._has_soapy_driver("fcdpp")

    def has_soapy_bladerf(self):
        """
        The [SoapyBladeRF](https://github.com/pothosware/SoapyBladeRF) module allows the use of Blade RF devices.

        Debian and Ubuntu users should be able to install the package `soapysdr-module-bladerf` from their distribution.
        """
        return self._has_soapy_driver("bladerf")

    def has_m17_demod(self):
        """
        OpenWebRX uses the [M17 Demodulator](https://github.com/mobilinkd/m17-cxx-demod) to demodulate M17 digital
        voice signals.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `m17-demod`.
        """
        return self.command_is_runnable("m17-demod", 0)

    def has_direwolf(self):
        """
        OpenWebRX uses the [direwolf](https://github.com/wb2osz/direwolf) software modem to decode Packet Radio and
        report data back to APRS-IS.

        Debian and Ubuntu users should be able to install the package `direwolf` from their distribution.
        """
        return self.command_is_runnable("direwolf --help")

    def has_wsjtx(self):
        """
        To decode FT8 and other digimodes, you need to install the WSJT-X software suite. Please check the
        [WSJT-X homepage](https://wsjt.sourceforge.io/) for ready-made packages or instructions
        on how to build from source.

        Debian and Ubuntu users can also install the `wsjtx` package provided by the distribution.
        """
        return reduce(and_, map(self.command_is_runnable, ["jt9", "wsprd"]), True)

    def _has_wsjtx_version(self, required_version):
        wsjt_version_regex = re.compile("^WSJT-X (.*)$")

        try:
            process = subprocess.Popen(["wsjtx_app_version", "--version"], stdout=subprocess.PIPE)
            matches = wsjt_version_regex.match(process.stdout.readline().decode())
            if matches is None:
                return False
            version = LooseVersion(matches.group(1))
            process.wait(1)
            return version >= required_version
        except FileNotFoundError:
            return False

    def has_wsjtx_2_3(self):
        """
        Newer digital modes (e.g. FST4, FST4) require WSJT-X in at least version 2.3.
        """
        return self.has_wsjtx() and self._has_wsjtx_version(LooseVersion("2.3"))

    def has_wsjtx_2_4(self):
        """
        WSJT-X version 2.4 introduced the Q65 mode.
        """
        return self.has_wsjtx() and self._has_wsjtx_version(LooseVersion("2.4"))

    def has_msk144decoder(self):
        """
        To decode the MSK144 digimode please install
        [msk144decoder](https://github.com/alexander-sholohov/msk144decoder).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `msk144decoder`.
        """
        return self.command_is_runnable("msk144decoder")

    def has_js8(self):
        """
        To decode JS8, you will need to install [JS8Call](http://js8call.com/).

        Debian and Ubuntu users should be able to install the package `js8call` from their distribution.
        """
        return self.command_is_runnable("js8")

    def has_js8py(self):
        """
        OpenWebRX uses [js8py](https://github.com/jketterl/js8py) to decode binary JS8 messages into readable text.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `python3-js8py`.
        """
        required_version = StrictVersion("0.2")
        try:
            from js8py.version import strictversion

            return strictversion >= required_version
        except ImportError:
            return False

    def has_alsa(self):
        """
        Some SDR receivers are identifying themselves as a soundcard. In order to read their data, OpenWebRX relies
        on the Alsa library.

        Debian and Ubuntu users should be able to install the package `alsa-utils` from their distribution.
        """
        return self.command_is_runnable("arecord --help")

    def has_rockprog(self):
        """
        The `rockprog` executable is required to send commands to your FiFiSDR. It needs to be installed separately.

        You can find instructions and downloads [here](https://o28.sischa.net/fifisdr/trac/wiki/De%3Arockprog).
        """
        return self.command_is_runnable("rockprog")

    def has_freedv_rx(self):
        """
        The `freedv_rx` executable is required to demodulate FreeDV digital transmissions. It comes together with the
        codec2 library, but it's only a supplemental part and not installed by default or contained in its packages.
        To install it, you will need to compile codec2 from source and manually install freedv\\_rx.

        Detailed installation instructions are available on the
        [OpenWebRX wiki](https://github.com/jketterl/openwebrx/wiki/FreeDV-demodulator-notes).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `codec2`.
        """
        return self.command_is_runnable("freedv_rx")

    def has_dream(self):
        """
        In order to be able to decode DRM broadcasts, OpenWebRX needs the "dream" DRM decoder.

        A custom set of commands is recommended when compiling from source. Detailed installation instructions are
        available on the [OpenWebRX wiki](https://github.com/jketterl/openwebrx/wiki/DRM-demodulator-notes).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `dream-headless`.
        """
        return self.command_is_runnable("dream --help", 0)

    def has_sddc_connector(self):
        """
        The sddc_connector allows connectivity with SDR devices powered by libsddc, e.g. RX666, RX888, HF103.

        You can find more information [here](https://github.com/jketterl/sddc_connector).
        """
        return self._check_connector("sddc_connector", LooseVersion("0.1"))

    def has_hpsdr_connector(self):
        """
        The [HPSDR Connector](https://github.com/jancona/hpsdrconnector) is required to interface OpenWebRX with
        Hermes Lite 2, Red Pitaya, and similar networked SDR devices.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `hpsdrconnector`.
        """
        return self.command_is_runnable("hpsdrconnector -h")

    def has_runds_connector(self):
        """
        To use radios supporting R&S radios via EB200 or Ammos, you need to install
        [runds_connector](https://github.com/jketterl/runds_connector).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `runds-connector`.
        """
        return self._check_connector("runds_connector", LooseVersion("0.2"))

    def has_codecserver_ambe(self):
        """
        [Codecserver](https://github.com/jketterl/codecserver) is used to decode audio data from digital voice modes using the AMBE codec.

        NOTE: this feature flag checks both the availability of codecserver as well as the availability of the AMBE
        codec in the configured codecserer instance.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `codecserver`.
        """

        config = Config.get()
        server = ""
        if "digital_voice_codecserver" in config:
            server = config["digital_voice_codecserver"]
        try:
            from digiham.modules import MbeSynthesizer

            return MbeSynthesizer.hasAmbe(server)
        except ImportError:
            return False
        except ConnectionError:
            return False
        except RuntimeError as e:
            logger.exception("Codecserver error while checking for AMBE support:")
            return False

    def has_dump1090(self):
        """
        To be able to decode Mode-S and ADS-B traffic originating from airplanes, you need to install the dump1090
        decoder. There is a number of forks available, any version that supports the `--ifile` and `--iformat` arguments
        should work.

        Recommended fork: [dump1090 by Flightaware](https://github.com/flightaware/dump1090)

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `dump1090-fa-minimal`.

        If you are running a different fork, please make sure that the command `dump1090` (without suffixes) runs the
        version you would like to use. You can use symbolic links or the
        [Debian alternatives system](https://wiki.debian.org/DebianAlternatives) to achieve this.
        """
        return self.command_is_runnable("dump1090 --version")

    def has_rtl_433(self):
        """
        OpenWebRX can make use of [`rtl_433`](https://github.com/merbanan/rtl_433) to decode various signals in the
        ISM bands.

        Debian and Ubuntu users should be able to install the package `rtl-433` from their distribution.
        """
        return self.command_is_runnable("rtl_433 -h")

    def has_dumphfdl(self):
        """
        OpenWebRX supports decoding HFDL airplane communications using
        [`dumphfdl`](https://github.com/szpajder/dumphfdl).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `dumphfdl`.
        """
        return self.command_is_runnable("dumphfdl --version")

    def has_dumpvdl2(self):
        """
        OpenWebRX supports decoding VDL Mode 2 airplane communications using
        [`dumpvdl2`](https://github.com/szpajder/dumpvdl2).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `dumpvdl2`.
        """
        return self.command_is_runnable("dumpvdl2 --version")

    def has_redsea(self):
        """
        OpenWebRX can decode RDS data on WFM broadcast station if the [`redsea`](https://github.com/windytan/redsea)
        decoder is available.

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `redsea`.
        """
        return self.command_is_runnable("redsea --version")

    def has_csdreti(self):
        """
        To decode DAB broadcast signals, OpenWebRX needs the ETI decoder from the
        [`csdr-eti`](https://github.com/jketterl/csdr-eti) project, together with the
        associated python bindings from [`pycsdr-eti`](https://github.com/jketterl/pycsdr-eti).

        If you are using the OpenWebRX Debian or Ubuntu repository, you should be able to install the package
        `python3-csdr-eti`.
        """
        required_version = LooseVersion("0.1")

        try:
            from csdreti.modules import csdreti_version
            from csdreti.modules import version as pycsdreti_version

            return (
                LooseVersion(csdreti_version) >= required_version
                and LooseVersion(pycsdreti_version) >= required_version
            )
        except ImportError:
            return False

    def has_dablin(self):
        """
        To decode DAB broadcast signals, OpenWebRX needs the [`dablin`](https://github.com/Opendigitalradio/dablin)
        decoding software.

        Debian and Ubuntu users should be able to install the package `dablin` from their distribution.
        """
        return self.command_is_runnable("dablin -h")

    def has_paho_mqtt(self):
        """
        OpenWebRX can pass decoded signal data to an MQTT broker for processing in third-party applications. To be able
        to do this, the [paho-mqtt](https://pypi.org/project/paho-mqtt/) library is required.

        Debian and Ubuntu users should be able to install the package `python3-paho-mqtt` from their distribution.
        """
        try:
            from paho.mqtt import __version__
            return True
        except ImportError:
            return False

    def has_nrsc5(self):
        """
        OpenWebRX uses the [nrsc5](https://github.com/theori-io/nrsc5) tool to decode HDRadio
        FM broadcasts. Nrsc5 is not yet available as a package and thus you will have
        to compile it from source.
        """
        return self.command_is_runnable("nrsc5 -v")
