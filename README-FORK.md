# dom-robinson/openwebrx fork – DAB+ sample rate fix

This is a clone of [dom-robinson/openwebrx](https://github.com/dom-robinson/openwebrx) with branch **feature/dab-audio-fix** containing improvements over upstream [jketterl/openwebrx PR #419](https://github.com/jketterl/openwebrx/pull/419): **Fix DAB+ audio sample rate issues using ffmpeg resampling**.

## What’s in this branch

- **owrx/dab/dablin.py** – DAB+ audio fix with **automatic handling of all sample rates (24/32/48 kHz)** and mono/stereo:
  - **Default (WAV path):** `dablin -w` so ffmpeg reads sample rate and channel count from the WAV header; resample to 48 kHz stereo. All DAB+ services play at correct speed without configuration.
  - **Fallback (PCM path):** Set `OPENWEBRX_DAB_USE_WAV=0` and optionally `OPENWEBRX_DAB_INPUT_RATE=24000|32000|48000` if WAV causes issues. Optional `OPENWEBRX_DAB_CAPTURE_RAW=1` tees raw PCM to `/tmp/dablin_capture.raw` for analysis.
  - **Critical fix:** Treat dablin output as **stereo** (`-ac 2`) when using PCM; using mono caused consistently slow playback.
- **docker/scripts/install-dependencies.sh** – Add `sox` to static packages.
- **Dockerfile.hotfix** – Optional image that builds dablin from source and applies the dablin.py patch.

## Environment variables (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENWEBRX_DAB_USE_WAV` | `1` | Use dablin WAV output so rate/channels are automatic. Set `0` to use PCM path with fixed rate. |
| `OPENWEBRX_DAB_INPUT_RATE` | `32000` | Only when `OPENWEBRX_DAB_USE_WAV=0`: input rate 24000, 32000, or 48000. |
| `OPENWEBRX_DAB_CAPTURE_RAW` | unset | Set to `1` to tee raw PCM to `/tmp/dablin_capture.raw` (PCM path only, for analysis). |

## Push this branch to the fork

From this directory, with GitHub auth set up:

```bash
git push -u origin feature/dab-audio-fix
```

After pushing, the fork on GitHub will list the branch and you can open or update a PR to jketterl/openwebrx, or build images from it.
