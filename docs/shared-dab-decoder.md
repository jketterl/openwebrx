# Shared DAB EtiDecoder

## Problem

In the default OpenWebRX implementation, each WebSocket client tuning to a DAB
multiplex spawns its own independent `EtiDecoder` (the OFDM demodulator). With
multiple simultaneous clients on the same multiplex, N identical demodulators
compete for CPU:

- 5 clients → 5 EtiDecoder instances → ~52–55% CPU on a Raspberry Pi 5
- CPU starvation causes OFDM lock-loss (`Lock lost` in logs), coarse time shift
  spikes to ~130,000, and audible breakup for all listeners including Chrome

## Fix

A single `SharedDabDecoder` runs one `Shift + EtiDecoder + MetaProcessor`
pipeline per DAB multiplex. All clients consume from the shared ETI output
buffer via independent readers (`pycsdr.Buffer` supports multiple independent
reader cursors — the same mechanism used by `SpectrumThread` in `owrx/fft.py`).

Each client retains its own:
- `DablinModule` subprocess — service ID selection is per-client
- `MetaForwarder` — forwards programme labels / service list to the client's
  meta WebSocket channel

## Architecture

```
                   DabDecoderManager (singleton)
                           |
            SharedDabDecoder(sdr_id, center_freq)
            [Shift → EtiDecoder → ETI Buffer]
                            |
               MetaProcessor → Meta Buffer
              /              |              \
        reader 1         reader 2        reader N
           |                |               |
     DablinModule(A)  DablinModule(B)  DablinModule(N)
     MetaForwarder(A) MetaForwarder(B) MetaForwarder(N)
```

## Results (measured on Raspberry Pi 5, 4 concurrent clients)

| Metric | Before | After |
|--------|--------|-------|
| CPU (4 clients) | ~52–55% | ~35% |
| Coarse time shift | ~130,000 (losing lock) | 1–8 (solid lock) |
| `Lock lost` events | frequent | zero |
| Programme list in browser | ✅ works | ✅ works |

## Files Changed

| File | Change |
|------|--------|
| `owrx/dab/__init__.py` | New — makes `owrx.dab` a proper Python package |
| `owrx/dab/manager.py` | New — `SharedDabDecoder` + `DabDecoderManager` |
| `csdr/chain/dablin.py` | Modified — `MetaForwarder` class + `shared_decoder` param |
| `owrx/dsp.py` | Modified — injects shared decoder, releases on stop/demod-change |

## Known Limitations

**Service switch race:** If the only client on a multiplex switches DAB service,
`setDemodulator` releases then immediately re-acquires the same key. Refcount
transiently hits 0, causing the shared decoder to stop and restart (~1s
re-lock). Acceptable — service switches are rare and user-initiated.
