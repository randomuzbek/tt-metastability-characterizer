# host/ — capture, decode, extract

Post-silicon tooling. The chips arrive ~2027-05; this was written and tested
against synthetic data **before** tapeout, so that first light is a measurement
session and not a software project.

**If you have a chip and want to contribute a measurement, start with
[QUICKSTART.md](QUICKSTART.md).** This file is the reference for the data format
and the tools.

```bash
python -m pytest -q        # 12 tests, no hardware needed
```

| File | What it does |
|---|---|
| `capture.py` | Record the UART stream via a PC USB-serial adapter, report frame count |
| `demoboard_capture.py` | Same, but running on the demo board's MCU — also measures `Fd` (untested on hardware) |
| `decode.py` | Byte stream → records → CSV. Resyncs on garbage, drops bad checksums |
| `extract.py` | CSV → τ, W, R², MTBF estimates |

## Measurement chain

`ring_osc(÷N)` → asynchronous data at rate `Fd` → `delay_line(tap)` → DUT
flip-flop sampled by the 25 MHz clock → `witness_bank` (dual sample) →
`metastable_witness` → `sweep_ctrl` counts events per tap → `uart_packet` →
`uo[0]`. See [`../docs/method.md`](../docs/method.md) for why each stage exists.

## Wire format — 14 bytes, little-endian

Source of truth: [`../src/uart_packet.v`](../src/uart_packet.v).

| Byte | Field | Notes |
|---|---|---|
| 0 | `0xA5` | sync |
| 1 | `{7'b0, mode}` | from `ui[1]` |
| 2..3 | `tap` | LE16, 0…40 |
| 4..7 | `fail_count` | LE32 — metastability events at this tap |
| 8..11 | `trial_count` | LE32 — trials (dwell) at this tap |
| 12 | `die_id` | `0x5A` in v1 |
| 13 | `checksum` | `XOR(bytes 0..12)`, so `XOR(all 14) == 0` |

UART: **8N1, 115200 baud at a 25 MHz project clock** (`CLKS_PER_BIT = 217`). The
baud rate scales with the clock — at 10 MHz the stream is 46080 baud.

## Pin map

| Pin | Direction | Function |
|---|---|---|
| `ui[0]` | in | `start` — pulse high for one clock |
| `ui[1]` | in | `mode` — copied into the packet |
| `ui[4:2]` | in | `ro_div` — ring divider, selects `Fd` (0 = fastest … 7 = ÷256) |
| `ui[6:5]` | in | `dut_sel` — 0: `dfxtp_1`, 1: `dfxtp_2`, 2: `dfrtp_1`, 3: `sdfxtp_1` |
| `ui[7]` | in | `ext_data` — 1: take async data from `uio[0]` |
| `uo[0]` | out | **UART TX** |
| `uo[1]` / `uo[2]` | out | `busy` / `done` |
| `uo[3]` | out | heartbeat, clk / 2²⁴ ≈ 1.5 Hz |
| `uo[7:4]` | out | live `tap[3:0]` |
| `uio[0]` | in | external async data |
| `uio[1]` | out | **`ro_clk` — the `Fd` monitor** |

## The two numbers that must be measured, not assumed

`extract.py` needs two inputs that cannot be known from RTL:

1. **`--fd-hz` (`Fd`)** — the asynchronous data rate, i.e. the divided ring
   frequency on `uio[1]`. It is PVT dependent, which is the whole point of an
   on-chip oscillator, and it appears directly in
   `MTBF = e^(Ts/τ)/(Tw·Fc·Fd)`. Without it, τ still comes out (it depends only
   on the slope) but `W` cannot be given in absolute units.
2. **`--tw-s`** — the delay-line step, since `Ts = tap · tw_s`. Target is
   ~10–15 ps from the SKY130 liberty data; the real value needs gate-level SDF or
   on-chip calibration. An error here rescales τ linearly — the *shape*, and
   therefore comparisons between flip-flop flavours and between dies, survives.

## Model and its limits

`extract_tau_w` fits `ln(rate) = ln(W·Fd·Fc) − Ts/τ` by least squares, i.e. the
first-order model `P(fail) = W·Fd·e^(−Ts/τ)`. It reports R²; **below 0.9 the
numbers are not trustworthy** — usually too little dwell, noise, or a tap range
that does not span the aperture.

It deliberately refuses to produce a number when the data cannot mean what the
model assumes: fewer than 3 non-zero points, or a failure rate that *increases*
with settling time, both raise `ValueError` rather than returning a plausible-looking
τ. A silent wrong number is worse than an error.
