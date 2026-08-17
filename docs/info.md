<!---
Datasheet kaynagi (TT web sitesi + PDF bunu basar).
Iddia disiplini: burada yalnizca RTL/GL ile DOGRULANMIS seyler "calisir" diye
yazilir; silikonda teyit bekleyenler "Limitations" altinda acikca isaretlidir.
-->

## How it works

This is a **silicon characterization instrument**: it measures the metastability
behaviour of flip-flops fabricated on this die, and streams the raw measurement
out over UART so anyone with a USB-serial adapter can reproduce the numbers.

Measuring metastability requires data that is genuinely **asynchronous** to the
sampling clock (a synchronous pattern generator cannot produce it — the MTBF
relation `MTBF = e^(Ts/τ) / (Tw · Fc · Fd)` contains `Fd`, the async data rate).
So the data source is an on-chip oscillator:

```
ring_osc (3-stage std-cell ring, ÷N divider)   -> async data, rate Fd
   -> ÷2 toggle                                -> uncorrelated transitions
   -> delay_line (8 coarse dlymetal6s2s + 4 fine buf_1 per stage, 41 taps)
   -> DUT flip-flop bank, sampled by the 25 MHz system clock  -> may go metastable
   -> witness_bank (samples DUT.Q twice, on inverse clock and a delayed copy)
   -> metastable_witness (q_a ^ q_b = late resolution detected)
   -> sweep_ctrl (per tap: TRIALS=256 trials, counts events)
   -> uart_packet (14-byte frame) -> uo[0]
```

The **delay line** slides the data transition through the sampling aperture in
~10–15 ps steps (41 taps). Close to the aperture the failure count rises
exponentially; the slope of `ln(failure rate)` versus delay gives **τ** (the
resolution time constant) and the intercept gives **W**. Four *different physical*
DUT cells are measured (`dfxtp_1`, `dfxtp_2`, `dfrtp_1`, `sdfxtp_1`), selected by
`ui[6:5]`, so the same die yields a comparison across cell flavours.

All measurement elements are **structurally instantiated named standard cells**
with `keep` attributes, and synthesis/placement is told not to resize them
(`SYNTH_KEEP_HIERARCHY_MODULES`, `RSZ_DONT_TOUCH_RX`) — otherwise the toolchain
would optimize the instrument away. Back-pressure (`sweep_ctrl.stall =
uart_packet.busy`) guarantees no record is dropped while a frame is transmitted.

Because every Tiny Tapeout participant's design sits on the **same die**, a crowd
of these measurements characterizes **within-die device mismatch and spatial
gradients** — something PDK corner libraries do not contain (they are deterministic
nominal corners, not Monte-Carlo mismatch).

## How to test

**1. Wire up.** UART receiver (3.3 V) on `uo[0]`, **115200 baud, 8N1** (25 MHz
clock, `CLKS_PER_BIT = 217`). Optionally a frequency counter or scope on `uio[1]`.

**2. Set inputs.**

| Pin | Function |
|---|---|
| `ui[0]` | `start` — pulse high for one clock to launch a sweep |
| `ui[1]` | `mode` — copied into the packet (0 = shmoo, 1 = mtbf) |
| `ui[4:2]` | `ro_div` — ring divider, selects `Fd` (0 = fastest … 7 = ÷256) |
| `ui[6:5]` | `dut_sel` — 0: `dfxtp_1`, 1: `dfxtp_2`, 2: `dfrtp_1`, 3: `sdfxtp_1` |
| `ui[7]` | `ext_data` — 1: take async data from `uio[0]` instead of the ring |
| `uo[0]` | **UART TX** |
| `uo[1]` / `uo[2]` | `busy` / `done` |
| `uo[3]` | heartbeat (clk / 2²⁴ ≈ 1.5 Hz — "the chip is alive") |
| `uo[7:4]` | live `tap[3:0]` (debug) |
| `uio[0]` | external async data in (when `ui[7]=1`) |
| `uio[1]` | **`ro_clk` out — the `Fd` monitor** (measure this!) |

**3. Measure `Fd` first.** Put a counter on `uio[1]` and record the frequency for
the `ro_div` setting you use. `Fd` appears in the MTBF relation; without it only
τ (from the slope) can be extracted, not `W`.

**4. Capture and decode.** One 14-byte little-endian frame per tap:
`0xA5 | mode | tap(16) | fail_count(32) | trial_count(32) | die_id | XOR checksum`
(XOR over all 14 bytes is 0). Then:

```
python host/decode.py capture.bin --csv sweep.csv
python host/extract.py sweep.csv --fd-hz <measured Fd> --fc-hz 25e6 --tw-s <step>
```

`host/` prints τ, `W`, an R² for the fit, and MTBF estimates. Repeat sweeps and
accumulate on the host for longer effective dwell.

## External hardware

- USB-to-UART adapter (3.3 V) on `uo[0]` — required.
- Frequency counter, logic analyser or scope on `uio[1]` — strongly recommended
  (this is how `Fd` is obtained).
- Optional: external async source driven into `uio[0]` with `ui[7]=1`, to compare
  against the on-chip ring.

## Limitations (read before trusting a number)

- **RTL simulation cannot show metastability** — the simulation models of the named
  cells have zero delay, so `fail_count = 0` there by construction. Event capture
  is a property of real silicon (and, partially, gate-level simulation).
- **Two numbers must be measured, not assumed:** `Fd` (ring frequency — PVT
  dependent, hence the `uio[1]` monitor) and the **delay-line step** `tw_s`
  (target ~10–15 ps, from `sky130_fd_sc_hd` timing data). An incorrect `tw_s`
  rescales τ; an incorrect `Fd` corrupts `W` (τ, coming from the slope, survives).
- The extraction uses a first-order model (`P(fail) = W·Fd·e^(−Ts/τ)`) fitted in
  log space. If the reported R² is below 0.9 the numbers are **not** trustworthy —
  usually too little dwell, noise, or a tap range that does not cover the aperture.
- The ring oscillator is a deliberate combinational loop. It is held stopped
  during reset and starts on reset release; static timing analysis treats it as
  the exception it is.
- `TRIALS` (dwell) and the tap count are fixed at synthesis time in v1. Longer
  dwell is obtained by repeating sweeps and summing on the host.
