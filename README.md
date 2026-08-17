# Metastability Characterizer — a measuring instrument on silicon

[![gds](https://github.com/randomuzbek/tt-metastability-characterizer/actions/workflows/gds.yaml/badge.svg)](https://github.com/randomuzbek/tt-metastability-characterizer/actions/workflows/gds.yaml)
[![test](https://github.com/randomuzbek/tt-metastability-characterizer/actions/workflows/test.yaml/badge.svg)](https://github.com/randomuzbek/tt-metastability-characterizer/actions/workflows/test.yaml)

A 1-tile [Tiny Tapeout](https://tinytapeout.com) design (SKY130, TTSKY26c) that
measures the **metastability parameters of the flip-flops on its own die** and
streams the raw counts out over UART.

When data arrives at a flip-flop too close to the clock edge, the flip-flop
becomes momentarily undecided — its output is neither 0 nor 1 until it resolves.
Every clock-domain crossing in every chip relies on this resolving fast enough.
The two numbers that quantify it are **τ** (the resolution time constant) and
**W** (the effective aperture width), and together with the data and clock rates
they give the synchronizer failure rate:

```
MTBF = e^(Ts/τ) / (Tw · Fc · Fd)
```

τ and W are process-specific and **are not published in the open SKY130 PDK**.
This chip measures them, on real silicon, and hands you the raw data.

## How it measures

```
ring oscillator (÷N)      async data — deliberately uncorrelated with the clock
        ↓
delay line (41 taps)      slides the data edge through the sampling aperture
        ↓                 in ~10–15 ps steps
4 DUT flip-flops          sampled by the 25 MHz system clock  ← metastability happens here
        ↓                 (dfxtp_1 / dfxtp_2 / dfrtp_1 / sdfxtp_1)
witness flip-flops        sample the DUT output twice, a short delay apart
        ↓                 disagreement ⇒ it had not resolved yet ⇒ one event
sweep controller          per tap: N trials, count events
        ↓
UART, 14-byte frames  →  uo[0]
```

Failure counts stay at zero while the data edge is far from the aperture and rise
**exponentially** as it approaches. The slope of `ln(rate)` against delay yields τ;
the intercept yields W. Full reasoning, including why a synchronous pattern
generator cannot do this: **[`docs/method.md`](docs/method.md)**.

## Quick start

Select the project in the Tiny Tapeout Commander, then:

| Pin | Function |
|---|---|
| `ui[0]` | `start` — pulse high for one clock |
| `ui[1]` | `mode` — copied into the packet |
| `ui[4:2]` | `ro_div` — ring divider, selects `Fd` (0 = fastest … 7 = ÷256) |
| `ui[6:5]` | `dut_sel` — 0: `dfxtp_1`, 1: `dfxtp_2`, 2: `dfrtp_1`, 3: `sdfxtp_1` |
| `ui[7]` | `ext_data` — 1: use external async data on `uio[0]` |
| `uo[0]` | **UART TX**, 115200 8N1 |
| `uo[1]` / `uo[2]` | `busy` / `done` |
| `uo[3]` | heartbeat (≈1.5 Hz) |
| `uo[7:4]` | live `tap[3:0]` |
| `uio[0]` | external async data in |
| `uio[1]` | **`ro_clk` out — the `Fd` monitor** (put a counter here) |

```bash
# capture, decode, extract
python host/decode.py capture.bin --csv sweep.csv
python host/extract.py sweep.csv --fd-hz <measured Fd> --fc-hz 25e6 --tw-s <step>
```

See [`host/README.md`](host/README.md) for the wire format and the two quantities
you must measure rather than assume (`Fd` and the delay step).

## Contributing measurements — **[3-step guide](host/QUICKSTART.md)**

Every project on a Tiny Tapeout shuttle shares one die, so **every TTSKY26c chip
already contains this instrument** — nothing to build, nothing to flash.

A sweep takes about two minutes:

```bash
# with a USB-UART adapter on uo[0]
python host/capture.py --port /dev/ttyUSB0 --seconds 120 --out capture.bin
python host/decode.py capture.bin --csv sweep.csv
```

No adapter? [`host/demoboard_capture.py`](host/demoboard_capture.py) runs on the
demo board's own microcontroller — it receives the UART stream in PIO and also
measures `Fd`, which is the one number you cannot get any other way.

Then open an issue with `sweep.csv`, your `ro_div`/`dut_sel` settings, the measured
`Fd` if you have it, and the ambient temperature if you know it. You do not have to
interpret anything — the analysis is in this repo.

Why it is worth two minutes: within-die differences between flip-flop flavours and
die-to-die spread across the wafer are exactly what corner libraries do not
contain, and nobody has published them for open SKY130 silicon.

## Verification status

Be precise about what is proven and what is not:

| Claim | Evidence | Status |
|---|---|---|
| Control logic, wiring, packet framing correct | 36 cocotb tests (RTL) | ✅ |
| Host decode + τ/W extraction correct | 12 pytest tests (synthetic data) | ✅ |
| Hardens into 1 tile; DRC/LVS clean; timing closed | LibreLane signoff, 9 corners | ✅ |
| Measurement cells survive synthesis unmodified | netlist check on the real GDS netlist | ✅ |
| Ring oscillates on silicon; τ/W actually extractable | **physical chip** | ⏳ 2027 |

Details and numbers: [`docs/hardening-summary.md`](docs/hardening-summary.md).
RTL simulation **cannot** show metastability — the simulation models of the named
cells have zero delay, so simulated failure counts are zero by construction. That
is expected, and it is why the analysis software was written before tapeout.

## Repository layout

```
src/            Verilog sources + LibreLane config (config.json)
test/           cocotb testbenches: unit/ per block, test.py for the top level
host/           post-silicon decode + τ/W extraction (pure Python)
scripts/        verify_netlist.py — proves the instrument survived synthesis
docs/           info.md (datasheet) · method.md (physics) · hardening-summary.md
```

Run the tests (needs `iverilog` + `cocotb`):

```bash
cd test/unit && bash run_all.sh          # 33 block-level tests
cd test && make -B                       # top-level integration
cd host && python -m pytest -q           # 12 host tests
```

## License

Apache-2.0. Built from the
[Tiny Tapeout Verilog template](https://github.com/TinyTapeout/ttsky-verilog-template).
