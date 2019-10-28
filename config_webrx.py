# -*- coding: utf-8 -*-

"""
config_webrx: configuration options for OpenWebRX

    This file is part of OpenWebRX,
    an open-source SDR receiver software with a web UI.
    Copyright (c) 2013-2015 by Andras Retzler <randras@sdr.hu>

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

# NOTE: you can find additional information about configuring OpenWebRX in the Wiki:
#       https://github.com/simonyiszk/openwebrx/wiki

# ==== Server settings ====
web_port = 8073
max_clients = 20

# ==== Web GUI configuration ====
receiver_name = "[Callsign]"
receiver_location = "Budapest, Hungary"
receiver_asl = 200
receiver_admin = "example@example.com"
receiver_gps = (47.000000, 19.000000)
photo_title = "Panorama of Budapest from Schönherz Zoltán Dormitory"
photo_desc = """
You can add your own background photo and receiver information.<br />
Receiver is operated by: <a href="mailto:%[RX_ADMIN]">%[RX_ADMIN]</a><br/>
Device: %[RX_DEVICE]<br />
Antenna: %[RX_ANT]<br />
Website: <a href="http://localhost" target="_blank">http://localhost</a>
"""

# ==== sdr.hu listing ====
# If you want your ham receiver to be listed publicly on sdr.hu, then take the following steps:
# 1. Register at: http://sdr.hu/register
# 2. You will get an unique key by email. Copy it and paste here:
sdrhu_key = ""
# 3. Set this setting to True to enable listing:
sdrhu_public_listing = False
server_hostname = "localhost"

# ==== DSP/RX settings ====
fft_fps = 9
fft_size = 4096  # Should be power of 2
fft_voverlap_factor = (
    0.3
)  # If fft_voverlap_factor is above 0, multiple FFTs will be used for creating a line on the diagram.

audio_compression = "adpcm"  # valid values: "adpcm", "none"
fft_compression = "adpcm"  # valid values: "adpcm", "none"

digimodes_enable = True  # Decoding digimodes come with higher CPU usage.
digimodes_fft_size = 1024

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

#################################################################################################
# Is my SDR hardware supported?                                                                 #
# Check here: https://github.com/simonyiszk/openwebrx/wiki#guides-for-receiver-hardware-support #
#################################################################################################

# Currently supported types of sdr receivers: "rtl_sdr", "sdrplay", "hackrf", "airspy"
# With "hackrf, airspy" , "device" is the device of specified serial number

sdrs = {
    "rtlsdr": {
        "name": "RTL-SDR USB Stick",
        "type": "rtl_sdr",
        "ppm": 0,
        "device": "0",
        # you can change this if you use an upconverter. formula is:
        # shown_center_freq = center_freq + lfo_offset
        # "lfo_offset": 0,
        "profiles": {
            "70cm": {
                "name": "70cm Relais",
                "center_freq": 438800000,
                "rf_gain": 30,
                "samp_rate": 2400000,
                "start_freq": 439275000,
                "start_mod": "nfm",
            },
            "2m": {
                "name": "2m komplett",
                "center_freq": 145000000,
                "rf_gain": 30,
                "samp_rate": 2400000,
                "start_freq": 145725000,
                "start_mod": "nfm",
            },
        },
    },
    "sdrplay": {
        "name": "SDRPlay RSP2",
        "type": "sdrplay",
        "ppm": 0,
        "device": "0",
        "profiles": {
            "20m": {
                "name": "20m",
                "center_freq": 14150000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 14070000,
                "start_mod": "usb",
                "antenna": "Antenna A",
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
                "start_mod": "usb",
                "antenna": "Antenna A",
            },
            "80m": {
                "name": "80m",
                "center_freq": 3650000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 3570000,
                "start_mod": "usb",
                "antenna": "Antenna A",
            },
            "49m": {
                "name": "49m Broadcast",
                "center_freq": 6000000,
                "rf_gain": 0,
                "samp_rate": 500000,
                "start_freq": 6070000,
                "start_mod": "am",
                "antenna": "Antenna A",
            },
        },
    },
}

# ==== Misc settings ====

client_audio_buffer_size = 5
# increasing client_audio_buffer_size will:
# - also increase the latency
# - decrease the chance of audio underruns

iq_port_range = [
    4950,
    4960,
]  # TCP port for range ncat to listen on. It will send I/Q data over its connections, for internal use in OpenWebRX. It is only accessible from the localhost by default.

# ==== Color themes ====

# A guide is available to help you set these values: https://github.com/simonyiszk/openwebrx/wiki/Calibrating-waterfall-display-levels

### default theme by teejez:
waterfall_colors = [0x000000FF, 0x0000FFFF, 0x00FFFFFF, 0x00FF00FF, 0xFFFF00FF, 0xFF0000FF, 0xFF00FFFF, 0xFFFFFFFF]
waterfall_min_level = -88  # in dB
waterfall_max_level = -20
waterfall_auto_level_margin = (5, 40)
### old theme by HA7ILM:
# waterfall_colors = "[0x000000ff,0x2e6893ff, 0x69a5d0ff, 0x214b69ff, 0x9dc4e0ff,  0xfff775ff, 0xff8a8aff, 0xb20000ff]"
# waterfall_min_level = -115 #in dB
# waterfall_max_level = 0
# waterfall_auto_level_margin = (20, 30)
##For the old colors, you might also want to set [fft_voverlap_factor] to 0.

# Note: When the auto waterfall level button is clicked, the following happens:
#   [waterfall_min_level] = [current_min_power_level] - [waterfall_auto_level_margin[0]]
#   [waterfall_max_level] = [current_max_power_level] + [waterfall_auto_level_margin[1]]
#
#   ___|____________________________________|____________________________________|____________________________________|___> signal power
#        \_waterfall_auto_level_margin[0]_/ |__ current_min_power_level          | \_waterfall_auto_level_margin[1]_/
#                                                      current_max_power_level __|

# 3D view settings
mathbox_waterfall_frequency_resolution = 128  # bins
mathbox_waterfall_history_length = 10  # seconds
mathbox_waterfall_colors = [
    0x000000FF,
    0x2E6893FF,
    0x69A5D0FF,
    0x214B69FF,
    0x9DC4E0FF,
    0xFFF775FF,
    0xFF8A8AFF,
    0xB20000FF,
]

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

# wsjt decoder queue configuration
# due to the nature of the wsjt operating modes (ft8, ft8, jt9, jt65 and wspr), the data is recorded for a given amount
# of time (6.5 seconds up to 2 minutes) and decoded at the end. this can lead to very high peak loads.
# to mitigate this, the recordings will be queued and processed in sequence.
# the number of workers will limit the total amount of work (one worker will losely occupy one cpu / thread)
wsjt_queue_workers = 2
# the maximum queue length will cause decodes to be dumped if the workers cannot keep up
# if you are running background services, make sure this number is high enough to accept the task influx during peaks
# i.e. this should be higher than the number of wsjt services running at the same time
wsjt_queue_length = 10
# wsjt decoding depth will allow more results, but will also consume more cpu
wsjt_decoding_depth = 3
# can also be set for each mode separately
# jt65 seems to be somewhat prone to erroneous decodes, this setting handles that to some extent
wsjt_decoding_depths = {"jt65": 1}

temporary_directory = "/dev/shm"

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
aprs_symbols_path = "/opt/aprs-symbols/png"

# === PSK Reporter setting ===
# enable this if you want to upload all ft8, ft4 etc spots to pskreporter.info
# this also uses the receiver_gps setting from above, so make sure it contains a correct locator
pskreporter_enabled = False
pskreporter_callsign = "N0CALL"
