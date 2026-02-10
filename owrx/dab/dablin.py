import os
from pycsdr.modules import ExecModule
from pycsdr.types import Format


class DablinModule(ExecModule):
    def __init__(self):
        self.serviceId = 0
        super().__init__(
            Format.CHAR,
            Format.FLOAT,
            self._buildArgs()
        )

    def _buildArgs(self):
        # Two paths:
        # 1) WAV (default): dablin -w so ffmpeg reads rate and channels from header → 24/32/48 kHz and mono/stereo all work.
        # 2) PCM: set OPENWEBRX_DAB_USE_WAV=0 and OPENWEBRX_DAB_INPUT_RATE=24000|32000|48000 if WAV causes issues.
        # Optional: OPENWEBRX_DAB_CAPTURE_RAW=1 tees raw PCM to /tmp/dablin_capture.raw (PCM path only).
        use_wav = os.environ.get("OPENWEBRX_DAB_USE_WAV", "1") != "0"
        if use_wav:
            dab_cmd = (
                "dablin -w -s {:#06x} | mbuffer -q -m 4M | "
                "ffmpeg -v error -probesize 4096 -analyzeduration 0 -f wav -i pipe:0 "
                "-af aresample=48000 -f f32le -ar 48000 -ac 2 pipe:1"
            ).format(self.serviceId)
        else:
            rate = int(os.environ.get("OPENWEBRX_DAB_INPUT_RATE", "32000"))
            if rate not in (24000, 32000, 48000):
                rate = 32000
            dab_cmd = "echo {} > /tmp/dablin_rate.txt 2>/dev/null; dablin -p -s {:#06x}".format(rate, self.serviceId)
            if os.environ.get("OPENWEBRX_DAB_CAPTURE_RAW"):
                dab_cmd += " | tee >(dd of=/tmp/dablin_capture.raw bs=1M count=5 2>/dev/null)"
            dab_cmd += (
                " | mbuffer -q -m 4M | "
                "ffmpeg -v error -f s16le -ar {} -ac 2 -i pipe:0 "
                "-af aresample=48000 -f f32le -ar 48000 -ac 2 pipe:1"
            ).format(rate)
        return ["bash", "-c", dab_cmd]

    def setDabServiceId(self, serviceId: int) -> None:
        self.serviceId = serviceId
        self.setArgs(self._buildArgs())
        self.restart()
