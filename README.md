OpenWebRX
=========

OpenWebRX is a multi-user SDR receiver software with a web interface.

![OpenWebRX](https://www.openwebrx.de/gfx/openwebrx-screenshot.png)

It has the following features:

- [csdr](https://github.com/jketterl/csdr) based demodulators (AM/FM/SSB/CW/BPSK31/BPSK63)
- filter passband can be set from GUI
- it extensively uses HTML5 features like WebSocket, Web Audio API, and Canvas
- it works in Google Chrome, Chromium and Mozilla Firefox
- currently supports RTL-SDR, HackRF, SDRplay, AirSpy, LimeSDR, PlutoSDR
- Multiple SDR devices can be used simultaneously
- [digiham](https://github.com/jketterl/digiham) based demodularors (DMR, YSF, Pocsag)
- [dsd](https://github.com/f4exb/dsdcc) based demodulators (D-Star, NXDN)
- [wsjt-x](https://physics.princeton.edu/pulsar/k1jt/wsjtx.html) based demodulators (FT8, FT4, WSPR, JT65, JT9)

## Setup

The following methods of setting up a receiver are currently available:

- Raspberry Pi SD card images
- Debian repository
- Docker images
- Manual installation

Please checkout the [setup guide on the wiki](https://github.com/jketterl/openwebrx/wiki/Setup-Guide) for more details
on the respective methods.

## Community

If you have trouble setting up or configuring your receiver, you have some great idea you want to see implemented, or
you just generally want to have some OpenWebRX-related chat, come visit us over on
[our groups.io group](https://groups.io/g/openwebrx).

## Usage tips

You can zoom the waterfall display by the mouse wheel. You can also drag the waterfall to pan across it.

The filter envelope can be dragged at its ends and moved around to set the passband.

However, if you hold down the shift key, you can drag the center line (BFO) or the whole passband (PBS).

## Licensing

OpenWebRX is available under Affero GPL v3 license
([summary](https://tldrlegal.com/license/gnu-affero-general-public-license-v3-(agpl-3.0))).

OpenWebRX is also available under a commercial license on request. Please contact me at the address
*&lt;randras@sdr.hu&gt;* for licensing options. 
