OpenWebRX
=========

[:floppy_disk: Setup guide for Ubuntu](http://blog.sdr.hu/2015/06/30/quick-setup-openwebrx.html)  |  [:blue_book: Knowledge base on the Wiki](https://github.com/simonyiszk/openwebrx/wiki/)  |  [:earth_americas: Receivers on SDR.hu](http://sdr.hu/) 

OpenWebRX is a multi-user SDR receiver software with a web interface.

![OpenWebRX](http://blog.sdr.hu/images/openwebrx/screenshot.png)

It has the following features:

- [csdr](https://github.com/jketterl/csdr) based demodulators (AM/FM/SSB/CW/BPSK31),
- filter passband can be set from GUI,
- it extensively uses HTML5 features like WebSocket, Web Audio API, and Canvas
- it works in Google Chrome, Chromium and Mozilla Firefox
- currently supports RTL-SDR, HackRF, SDRplay, AirSpy
- Multiple SDR devices can be used simultaneously
- [digiham](https://github.com/jketterl/digiham) based demodularors (DMR, YSF)
- [dsd](https://github.com/f4exb/dsdcc) based demodulators (D-Star, NXDN)
- [wsjt-x](https://physics.princeton.edu/pulsar/k1jt/wsjtx.html) based demodulators (FT8, FT4, WSPR, JT65, JT9)

**News (2020-01-11 by SM4XAS)**
- Merged modifications for fine-tuning of frequency from DJ1AN to DD5JFK fork.

**News (2019-11-24 by DD5JFK)**
- There is now a new way to interface with SDR hardware, [owrx_connectors](https://github.com/jketterl/owrx_connector).
  They talk directly to the hardware (no rtl_sdr / rx_sdr necessary) and offer I/Q data on a socket, just like nmux
  did before. They additionally offer a control socket that allows openwebrx to control the SDR parameters directly,
  without the need for repeated restarts. This allows for quicker profile changes, and also reduces the risk of your
  SDR hardware from failing during the switchover. See `config_webrx.py` for further information and instructions.
- Offset tuning using the `lfo_offset` has been reworked in a way that `center_freq` has to be set to the frequency you
  actually want to listen to. If you're using an `lfo_offset` already, you will probably need to change its sign.
- `initial_squelch_level` can now be set on each profile.
- As usual, plenty of fixes and improvements.

**News (2019-10-27 by DD5JFK)**
- Part of the frontend code has been reworked
  - Audio buffer minimums have been completely stripped. As a result, you should get better latency. Unfortunately, this also means there will be some skipping when audio starts.
  - Now also supports AudioWorklets (for those browser that have it). The Raspberry Pi image has been updated to include https due to the SecureContext requirement.
  - Mousewheel controls for the receiver sliders
- Error handling for failed SDR devices

**News (2019-09-29 by DD5FJK)**
- One of the most-requested features is finally coming to OpenWebRX: Bookmarks (sometimes also referred to as labels). There's two kinds of bookmarks available:
  - Serverside bookmarks that are set up by the receiver administrator. Check the file `bookmarks.json` for examples!
  - Clientside bookmarks which every user can store for themselves. They are stored in the browser's localStorage.
- Some more bugs in the websocket handling have been fixed.

**News (2019-09-25 by DD5JFK)**
- Automatic reporting of spots to [pskreporter](https://pskreporter.info/) is now possible. Please have a look at the configuration on how to set it up.
- Websocket communication has been overhauled in large parts. It should now be more reliable, and failing connections should now have no impact on other users.
- Profile scheduling allows to set up band-hopping if you are running background services.
- APRS now has the ability to show symbols on the map, if a corresponding symbol set has been installed. Check the config!
- Debug logging has been disabled in a handful of modules, expect vastly reduced output on the shell.

**News (2019-09-13 by DD5JFK)**
- New set of APRS-related features
  - Decode Packet transmissions using [direwolf](https://github.com/wb2osz/direwolf) (1k2 only for now)
  - APRS packets are mostly decoded and shown both in a new panel and on the map
  - APRS is also available as a background service
  - direwolfs I-gate functionality can be enabled, which allows your receiver to work as a receive-only I-gate for the APRS network in the background
- Demodulation for background services has been optimized to use less total bandwidth, saving CPU
- More metrics have been added; they can be used together with collectd and its curl_json plugin for now, with some limitations.

**News (2019-07-21 by DD5JFK)**
- Latest Features:
  - More WSJT-X modes have been added, including the new FT4 mode
  - I started adding a bandplan feature, the first thing visible is the "dial" indicator that brings you right to the dial frequency for digital modes
  - fixed some bugs in the websocket communication which broke the map

**News (2019-07-13 by DD5JFK)**
- Latest Features:
  - FT8 Integration (using wsjt-x demodulators)
  - New Map Feature that shows both decoded grid squares from FT8 and Locations decoded from YSF digital voice
  - New Feature report that will show what functionality is available
- There's a new Raspbian SD Card image available (see below)

**News (2019-06-30 by DD5JFK)**
- I have done some major rework on the openwebrx core, and I am planning to continue adding more features in the near future. Please check this place for updates.
- My work has not been accepted into the upstream repository, so you will need to chose between my fork and the official version.
- I have enabled the issue tracker on this project, so feel free to file bugs or suggest enhancements there!
- This version sports the following new and amazing features:
  - Support of multiple SDR devices simultaneously
  - Support for multiple profiles per SDR that allow the user to listen to different frequencies
  - Support for digital voice decoding
  - Feature detection that will disable functionality when dependencies are not available (if you're missing the digital buttons, this is probably why)
- Raspbian SD Card Images and Docker builds available (see below)
- I am currently working on the feature set for a stable release, but you are more than welcome to test development versions!

> When upgrading OpenWebRX, please make sure that you also upgrade *csdr* and *digiham*!

## OpenWebRX servers on SDR.hu

[SDR.hu](http://sdr.hu) is a site which lists the active, public OpenWebRX servers. Your receiver [can also be part of it](http://sdr.hu/openwebrx), if you want.

![sdr.hu](http://blog.sdr.hu/images/openwebrx/screenshot-sdrhu.png)

## Setup

### Raspberry Pi SD Card Images

Probably the quickest way to get started is to download the [latest Raspberry Pi SD Card Image](https://s3.eu-central-1.amazonaws.com/de.dd5jfk.openwebrx/2019-11-24-OpenWebRX-full.zip). It contains all the depencencies out of the box, and should work on all Raspberries up to the 3B+.

This is based off the Raspbian Lite distribution, so [their installation instructions](https://www.raspberrypi.org/documentation/installation/installing-images/) apply.

Please note: I have not updated this to include the Raspberry Pi 4 yet. (It seems to be impossible to build Rasbpian Buster images on x86 hardware right now. Stay tuned!)

Once you have booted a Raspberry with the SD Card, it will appear in your network with the hostname "openwebrx", which should make it available as https://openwebrx/ on most networks. This may vary depending on your specific setup.

For Digital voice, the minimum requirement right now seems to be a Rasbperry Pi 3B+. I would like to work on optimizing this for lower specs, but at this point I am not sure how much can be done. 

### Docker Images

For those familiar with docker, I am providing [recent builds and Releases for both x86 and arm processors on the Docker hub](https://hub.docker.com/r/jketterl/openwebrx). You can find a short introduction there.

### Manual Installation

OpenWebRX currently requires Linux and python >= 3.6 to run. 

First you will need to install the dependencies:

- [csdr](https://github.com/jketterl/csdr)
- [rtl-sdr](http://sdr.osmocom.org/trac/wiki/rtl-sdr)

Optional dependency for improved hardware access (to become mandatory at some point):

- [owrx_connector](https://github.com/jketterl/owrx_connector)

Optional dependencies if you want to be able to listen do digital voice:

- [digiham](https://github.com/jketterl/digiham)
- [dsd](https://github.com/f4exb/dsdcc)

Optional dependency if you want to decode WSJT-X modes:

- [wsjt-x](https://physics.princeton.edu/pulsar/k1jt/wsjtx.html)

After cloning this repository and connecting an RTL-SDR dongle to your computer, you can run the server:

	./openwebrx.py
	
You can now open the GUI at <a href="http://localhost:8073">http://localhost:8073</a>.

Please note that the server is also listening on the following ports (on localhost only):

- ports 4950 to 4960 for the multi-user I/Q servers.

Now the next step is to customize the parameters of your server in `config_webrx.py`.

Actually, if you do something cool with OpenWebRX, please drop me a mail:  
*Jakob Ketterl, DD5JFK &lt;dd5jfk@darc.de&gt;*

## Usage tips

You can zoom the waterfall display by the mouse wheel. You can also drag the waterfall to pan across it.

The filter envelope can be dragged at its ends and moved around to set the passband.

However, if you hold down the shift key, you can drag the center line (BFO) or the whole passband (PBS).

## Setup tips

If you have any problems installing OpenWebRX, you should check out the <a href="https://github.com/simonyiszk/openwebrx/wiki">Wiki</a> about it, which has a page on the <a href="https://github.com/simonyiszk/openwebrx/wiki/Common-problems-and-their-solutions">common problems and their solutions</a>.

Sometimes the actual error message is not at the end of the terminal output, you may have to look at the whole output to find it.

## Licensing

OpenWebRX is available under Affero GPL v3 license (<a href="https://tldrlegal.com/license/gnu-affero-general-public-license-v3-(agpl-3.0)">summary</a>).

OpenWebRX is also available under a commercial license on request. Please contact me at the address *&lt;randras@sdr.hu&gt;* for licensing options. 
