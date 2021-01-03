# -*- coding: utf-8 -*-

"""
config_webrx: configuration options for OpenWebRX

    This file is part of OpenWebRX,
    an open-source SDR receiver software with a web UI.
    Copyright (c) 2013-2015 by Andras Retzler <randras@sdr.hu>
    Copyright (c) 2019-2020 by Jakob Ketterl <dd5jfk@darc.de>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

    ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    In addition, as a special exception, the copyright holders
    state that config_rtl.py and config_webrx.py are not part of the
    Corresponding Source defined in GNU AGPL version 3 section 1.

    (It means that you do not have to redistribute config_rtl.py and
    config_webrx.py if you make any changes to these two configuration files,
    and use them for running your web service with OpenWebRX.)
"""

# configuration version. please only modify if you're able to perform the associated migration steps.
version = 3

# NOTE: you can find additional information about configuring OpenWebRX in the Wiki:
# https://github.com/jketterl/openwebrx/wiki/Configuration-guide

# ==== Server settings ====
web_port = 8073
max_clients = 20
#for enable or disable client count log
log_client_connected = "disable"

# ==== Web GUI configuration ====
receiver_name = "[Callsign]"
receiver_location = "Budapest, Hungary"
receiver_asl = 200
receiver_admin = "example@example.com"
receiver_gps = {"lat": 47.000000, "lon": 19.000000}
photo_title = "Panorama of Budapest from Schönherz Zoltán Dormitory"
# photo_desc allows you to put pretty much any HTML you like into the receiver description.
# The lines below should give you some examples of what's possible.
photo_desc = """
You can add your own background photo and receiver information.<br />
Receiver is operated by: <a href="mailto:openwebrx@localhost" target="_blank">Receiver Operator</a><br/>
Device: Receiver Device<br />
Antenna: Receiver Antenna<br />
Website: <a href="http://localhost" target="_blank">http://localhost</a>
"""

# ==== Public receiver listings ====
# You can publish your receiver on online receiver directories, like https://www.receiverbook.de
# You will receive a receiver key from the directory that will authenticate you as the operator of this receiver.
# Please note that you not share your receiver keys publicly since anyone that obtains your receiver key can take over
# your public listing.
# Your receiver keys should be placed into this array:
receiver_keys = []
# If you list your receiver on multiple sites, you can place all your keys into the array above, or you can append
# keys to the arraylike this:
# receiver_keys += ["my-receiver-key"]

# If you're not sure, simply copy & paste the code you received from your listing site below this line:

# ==== DSP/RX settings ====
fft_fps = 9
fft_size = 4096  # Should be power of 2
fft_voverlap_factor = (
    0.3  # If fft_voverlap_factor is above 0, multiple FFTs will be used for creating a line on the diagram.
)

audio_compression = "adpcm"  # valid values: "adpcm", "none"
fft_compression = "adpcm"  # valid values: "adpcm", "none"

# Tau setting for WFM (broadcast FM) deemphasis\
# Quote from wikipedia https://en.wikipedia.org/wiki/FM_broadcasting#Pre-emphasis_and_de-emphasis
# "In most of the world a 50 µs time constant is used. In the Americas and South Korea, 75 µs is used"
# Enable one of the following lines, depending on your location:
# wfm_deemphasis_tau = 75e-6  # for US and South Korea
wfm_deemphasis_tau = 50e-6  # for the rest of the world

digimodes_enable = True  # Decoding digimodes come with higher CPU usage.
digimodes_fft_size = 2048

# determines the quality, and thus the cpu usage, for the ambe codec used by digital voice modes
# if you're running on a Raspi (up to 3B+) you'll want to leave this on 1
digital_voice_unvoiced_quality = 1
# enables lookup of DMR ids using the radioid api
digital_voice_dmr_id_lookup = True

"""
Note: if you experience audio underruns while CPU usage is 100%, you can:
- decrease `samp_rate`,
- set `fft_voverlap_factor` to 0,
- decrease `fft_fps` and `fft_size`,
- limit the number of users by decreasing `max_clients`.
"""

# ==== I/Q sources ====
# (Uncomment the appropriate by removing # characters at the beginning of the corresponding lines.)

###############################################################################
# Is my SDR hardware supported?                                               #
# Check here: https://github.com/jketterl/openwebrx/wiki/Supported-Hardware   #
###############################################################################

# Currently supported types of sdr receivers:
# "rtl_sdr", "rtl_sdr_soapy", "sdrplay", "hackrf", "airspy", "airspyhf", "fifi_sdr",
# "perseussdr", "lime_sdr", "pluto_sdr", "soapy_remote", "hpsdr", "red_pitaya", "uhd",
# "radioberry", "fcdpp", "rtl_tcp", "sddc", "eb200"

# For more details on specific types, please checkout the wiki:
# https://github.com/jketterl/openwebrx/wiki/Supported-Hardware#sdr-devices

sdrs = {
    "rtlsdr": {
        "name": "RTL-SDR USB Stick",
        "type": "rtl_sdr",
        "ppm": 0,
        # you can change this if you use an upconverter. formula is:
        # center_freq + lfo_offset = actual frequency on the sdr
        # "lfo_offset": 0,
        "profiles": {
            "70cm": {
                "name": "70cm Relais",
                "center_freq": 438800000,
                "rf_gain": 29,
                "samp_rate": 2400000,
                "start_freq": 439275000,
                "start_mod": "nfm",
            },
            "2m": {
                "name": "2m komplett",
                "center_freq": 145000000,
                "rf_gain": 29,
                "samp_rate": 2048000,
                "start_freq": 145725000,
                "start_mod": "nfm",
            },
        },
    },
    "airspy": {
        "name": "Airspy HF+",
        "type": "airspyhf",
        "ppm": 0,
        "rf_gain": "auto",
        "profiles": {
            "20m": {
                "name": "20m",
                "center_freq": 14150000,
                "samp_rate": 384000,
                "start_freq": 14070000,
                "start_mod": "usb",
            },
            "30m": {
                "name": "30m",
                "center_freq": 10125000,
                "samp_rate": 192000,
                "start_freq": 10142000,
                "start_mod": "usb",
            },
            "40m": {
                "name": "40m",
                "center_freq": 7100000,
                "samp_rate": 256000,
                "start_freq": 7070000,
                "start_mod": "lsb",
            },
            "80m": {
                "name": "80m",
                "center_freq": 3650000,
                "samp_rate": 384000,
                "start_freq": 3570000,
                "start_mod": "lsb",
            },
            "49m": {
                "name": "49m Broadcast",
                "center_freq": 6050000,
                "samp_rate": 384000,
                "start_freq": 6070000,
                "start_mod": "am",
            },
        },
    },
    "sdrplay": {
        "name": "SDRPlay RSP2",
        "type": "sdrplay",
        "ppm": 0,
        "antenna": "Antenna A",
        "profiles": {
            "20m": {
                "name": "20m",
                "center_freq": 14150000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 14070000,
                "start_mod": "usb",
            },
            "30m": {
                "name": "30m",
                "center_freq": 10125000,
                "rf_gain": 0,
                "samp_rate": 250000,
                "start_freq": 10142000,
                "start_mod": "usb",
            },
            "40m": {
                "name": "40m",
                "center_freq": 7100000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 7070000,
                "start_mod": "lsb",
            },
            "80m": {
                "name": "80m",
                "center_freq": 3650000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 3570000,
                "start_mod": "lsb",
            },
            "49m": {
                "name": "49m Broadcast",
                "center_freq": 6000000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 6070000,
                "start_mod": "am",
            },
        },
    },
}

# ==== Color themes ====

### google turbo colormap (see: https://ai.googleblog.com/2019/08/turbo-improved-rainbow-colormap-for.html)
waterfall_colors = [0x30123b, 0x311542, 0x33184a, 0x341b51, 0x351e58, 0x36215f, 0x372466, 0x38266c, 0x392973, 0x3a2c79, 0x3b2f80, 0x3c3286, 0x3d358b, 0x3e3891, 0x3e3a97, 0x3f3d9c, 0x4040a2, 0x4043a7, 0x4146ac, 0x4248b1, 0x424bb6, 0x434eba, 0x4351bf, 0x4453c3, 0x4456c7, 0x4559cb, 0x455bcf, 0x455ed3, 0x4561d7, 0x4663da, 0x4666dd, 0x4669e1, 0x466be4, 0x466ee7, 0x4671e9, 0x4673ec, 0x4676ee, 0x4678f1, 0x467bf3, 0x467df5, 0x4680f7, 0x4682f9, 0x4685fa, 0x4587fc, 0x458afd, 0x448cfe, 0x448ffe, 0x4391ff, 0x4294ff, 0x4196ff, 0x3f99ff, 0x3e9bff, 0x3d9efe, 0x3ba1fd, 0x3aa3fd, 0x38a6fb, 0x36a8fa, 0x35abf9, 0x33adf7, 0x31b0f6, 0x2fb2f4, 0x2db5f2, 0x2cb7f0, 0x2ab9ee, 0x28bcec, 0x26beea, 0x25c0e7, 0x23c3e5, 0x21c5e2, 0x20c7e0, 0x1fc9dd, 0x1dccdb, 0x1cced8, 0x1bd0d5, 0x1ad2d3, 0x19d4d0, 0x18d6cd, 0x18d8cb, 0x18dac8, 0x17dbc5, 0x17ddc3, 0x17dfc0, 0x18e0be, 0x18e2bb, 0x19e3b9, 0x1ae5b7, 0x1be6b4, 0x1de8b2, 0x1ee9af, 0x20eaad, 0x22ecaa, 0x24eda7, 0x27eea4, 0x29efa1, 0x2cf09e, 0x2ff19b, 0x32f298, 0x35f394, 0x38f491, 0x3cf58e, 0x3ff68b, 0x43f787, 0x46f884, 0x4af980, 0x4efa7d, 0x51fa79, 0x55fb76, 0x59fc73, 0x5dfc6f, 0x61fd6c, 0x65fd69, 0x69fe65, 0x6dfe62, 0x71fe5f, 0x75ff5c, 0x79ff59, 0x7dff56, 0x80ff53, 0x84ff50, 0x88ff4e, 0x8bff4b, 0x8fff49, 0x92ff46, 0x96ff44, 0x99ff42, 0x9cfe40, 0x9ffe3e, 0xa2fd3d, 0xa4fd3b, 0xa7fc3a, 0xaafc39, 0xacfb38, 0xaffa37, 0xb1f936, 0xb4f835, 0xb7f835, 0xb9f634, 0xbcf534, 0xbff434, 0xc1f334, 0xc4f233, 0xc6f033, 0xc9ef34, 0xcbee34, 0xceec34, 0xd0eb34, 0xd2e934, 0xd5e835, 0xd7e635, 0xd9e435, 0xdbe236, 0xdde136, 0xe0df37, 0xe2dd37, 0xe4db38, 0xe6d938, 0xe7d738, 0xe9d539, 0xebd339, 0xedd139, 0xeecf3a, 0xf0cd3a, 0xf1cb3a, 0xf3c93a, 0xf4c73a, 0xf5c53a, 0xf7c33a, 0xf8c13a, 0xf9bf39, 0xfabd39, 0xfaba38, 0xfbb838, 0xfcb637, 0xfcb436, 0xfdb135, 0xfdaf35, 0xfeac34, 0xfea933, 0xfea732, 0xfea431, 0xffa12f, 0xff9e2e, 0xff9c2d, 0xff992c, 0xfe962b, 0xfe932a, 0xfe9028, 0xfe8d27, 0xfd8a26, 0xfd8724, 0xfc8423, 0xfc8122, 0xfb7e20, 0xfb7b1f, 0xfa781e, 0xf9751c, 0xf8721b, 0xf86f1a, 0xf76c19, 0xf66917, 0xf56616, 0xf46315, 0xf36014, 0xf25d13, 0xf05b11, 0xef5810, 0xee550f, 0xed530e, 0xeb500e, 0xea4e0d, 0xe94b0c, 0xe7490b, 0xe6470a, 0xe4450a, 0xe34209, 0xe14009, 0xdf3e08, 0xde3c07, 0xdc3a07, 0xda3806, 0xd83606, 0xd63405, 0xd43205, 0xd23105, 0xd02f04, 0xce2d04, 0xcc2b03, 0xca2903, 0xc82803, 0xc62602, 0xc32402, 0xc12302, 0xbf2102, 0xbc1f01, 0xba1e01, 0xb71c01, 0xb41b01, 0xb21901, 0xaf1801, 0xac1601, 0xaa1501, 0xa71401, 0xa41201, 0xa11101, 0x9e1001, 0x9b0f01, 0x980d01, 0x950c01, 0x920b01, 0x8e0a01, 0x8b0901, 0x880801, 0x850701, 0x810602, 0x7e0502, 0x7a0402]

### original theme by teejez:
#waterfall_colors = [0x000000, 0x0000FF, 0x00FFFF, 0x00FF00, 0xFFFF00, 0xFF0000, 0xFF00FF, 0xFFFFFF]

### old theme by HA7ILM:
#waterfall_colors = [0x000000, 0x2e6893, 0x69a5d0, 0x214b69, 0x9dc4e0, 0xfff775, 0xff8a8a, 0xb20000]
# waterfall_min_level = -115 #in dB
# waterfall_max_level = 0
# waterfall_auto_level_margin = {"min": 20, "max": 30}
##For the old colors, you might also want to set [fft_voverlap_factor] to 0.

waterfall_min_level = -88  # in dB
waterfall_max_level = -20
waterfall_auto_level_margin = {"min": 3, "max": 10, "min_range": 50}

# Note: When the auto waterfall level button is clicked, the following happens:
#   [waterfall_min_level] = [current_min_power_level] - [waterfall_auto_level_margin["min"]]
#   [waterfall_max_level] = [current_max_power_level] + [waterfall_auto_level_margin["max"]]
#
#   ___|________________________________________|____________________________________|________________________________________|___> signal power
#        \_waterfall_auto_level_margin["min"]_/ |__ current_min_power_level          | \_waterfall_auto_level_margin["max"]_/
#                                                          current_max_power_level __|

# This setting allows you to modify the precision of the frequency displays in OpenWebRX.
# Set this to the number of digits you would like to see:
frequency_display_precision = 4

# This setting tells the auto-squelch the offset to add to the current signal level to use as the new squelch level.
# Lowering this setting will give you a more sensitive squelch, but it may also cause unwanted squelch openings when
# using the auto squelch.
squelch_auto_margin = 10  # in dB

# === Experimental settings ===
# Warning! The settings below are very experimental.
csdr_dynamic_bufsize = False  # This allows you to change the buffering mode of csdr.
csdr_print_bufsizes = False  # This prints the buffer sizes used for csdr processes.
csdr_through = False  # Setting this True will print out how much data is going into the DSP chains.

nmux_memory = 50  # in megabytes. This sets the approximate size of the circular buffer used by nmux.

google_maps_api_key = ""

# how long should positions be visible on the map?
# they will start fading out after half of that
# in seconds; default: 2 hours
map_position_retention_time = 2 * 60 * 60

# decoder queue configuration
# due to the nature of some operating modes (ft8, ft8, jt9, jt65, wspr and js8), the data is recorded for a given amount
# of time (6 seconds up to 2 minutes) and decoded at the end. this can lead to very high peak loads.
# to mitigate this, the recordings will be queued and processed in sequence.
# the number of workers will limit the total amount of work (one worker will losely occupy one cpu / thread)
decoding_queue_workers = 2
# the maximum queue length will cause decodes to be dumped if the workers cannot keep up
# if you are running background services, make sure this number is high enough to accept the task influx during peaks
# i.e. this should be higher than the number of decoding services running at the same time
decoding_queue_length = 10

# wsjt decoding depth will allow more results, but will also consume more cpu
wsjt_decoding_depth = 3
# can also be set for each mode separately
# jt65 seems to be somewhat prone to erroneous decodes, this setting handles that to some extent
wsjt_decoding_depths = {"jt65": 1}

# FST4 can be transmitted in different intervals. This setting determines which intervals will be decoded.
# available values (in seconds): 15, 30, 60, 120, 300, 900, 1800
fst4_enabled_intervals = [15, 30]

# FST4W can be transmitted in different intervals. This setting determines which intervals will be decoded.
# available values (in seconds): 120, 300, 900, 1800
fst4w_enabled_intervals = [120, 300]

# JS8 comes in different speeds: normal, slow, fast, turbo. This setting controls which ones are enabled.
js8_enabled_profiles = ["normal", "slow"]
# JS8 decoding depth; higher value will get more results, but will also consume more cpu
js8_decoding_depth = 3

temporary_directory = "/tmp"

services_enabled = False
services_decoders = ["ft8", "ft4", "wspr", "packet"]

# === aprs igate settings ===
# if you want to share your APRS decodes with the aprs network, configure these settings accordingly
aprs_callsign = "N0CALL"
aprs_igate_enabled = False
aprs_igate_server = "euro.aprs2.net"
aprs_igate_password = ""
# beacon uses the receiver_gps setting, so if you enable this, make sure the location is correct there
aprs_igate_beacon = False

# path to the aprs symbols repository (get it here: https://github.com/hessu/aprs-symbols)
aprs_symbols_path = "/usr/share/aprs-symbols/png"

# Uncomment the following to customize gateway beacon details reported to the aprs network
#   Plese see Dire Wolf's documentation on PBEACON configuration for complete details:
#   https://github.com/wb2osz/direwolf/raw/master/doc/User-Guide.pdf 

# Symbol in its two-character form as specified by the APRS spec at http://www.aprs.org/symbols/symbols-new.txt
#   Default: Receive only IGate (do not send msgs back to RF)  
# aprs_igate_symbol = "R&"

# Custom comment about igate 
#   Default: OpenWebRX APRS gateway
# aprs_igate_comment = "OpenWebRX APRS gateway"

# Antenna Height and Gain details
#   Unspecified by default
# Antenna height above average terrain (HAAT) in meters 
# aprs_igate_height = "5"
# Antenna gain in dBi
# aprs_igate_gain = "0"
# Antenna direction (N, NE, E, SE, S, SW, W, NW).  Omnidirectional by default
# aprs_igate_dir = "NE"

# === PSK Reporter setting ===
# enable this if you want to upload all ft8, ft4 etc spots to pskreporter.info
# this also uses the receiver_gps setting from above, so make sure it contains a correct locator
pskreporter_enabled = False
pskreporter_callsign = "N0CALL"
# optional antenna information, uncomment to enable
#pskreporter_antenna_information = "Dipole"

# === Web admin settings ===
# this feature is experimental at the moment. it should not be enabled on shared receivers since it allows remote
# changes to the receiver settings. enable for testing in controlled environment only.
# webadmin_enabled = False
