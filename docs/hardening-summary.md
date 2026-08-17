# Hardening evidence (TTSKY26c, sky130A)

Physical implementation results, so that anyone using the measurements can judge
how much to trust the instrument. Flow: `TinyTapeout/tt-gds-action@ttsky26c`
(LibreLane, sky130A) in GitHub Actions.

## Result

| Stage | Result |
|---|---|
| Synthesis + place & route (`gds`) | ✅ pass |
| Tiny Tapeout precheck | ✅ 15/15 checks |
| Measurement-cell integrity | ✅ 54 named-cell instances, all with the expected cell type |
| Gate-level simulation | see workflow `gl_test` |

## Physical

| Metric | Value |
|---|---|
| Tiles | 1 (core 161 × 111 µm, 16493 µm²) |
| Standard cells | 1374 (1986 including fill / decap / tap) |
| Instance utilization | 90.5 % |
| Magic DRC errors | 0 |
| KLayout DRC (FEOL, BEOL, offgrid, zero-area, pin-label) | 0 |
| Routing DRC errors | 0 (converged from 1293 over 13 iterations) |
| LVS device / net / pin mismatches | 0 |
| Antenna violations | 0 (6 diodes inserted) |
| Total power | ~0.665 mW |

## Timing — signoff across 9 corners (min/nom/max × tt/ss/ff)

| | WNS | TNS | worst slack | worst corner |
|---|---|---|---|---|
| Setup | 0 | 0 | **+12.49 ns** | ss 100C 1v60 |
| Hold | 0 | 0 | **+56 ps** | ff n40C 1v95 |

Clock period 40 ns (25 MHz). Hold buffers inserted: **2**. Setup buffers: 0.

The generous setup margin is deliberate: the design is a slow control loop around
a picosecond-scale measurement path, so there is no reason to run it fast.

### Known, accepted violations

- **209 max-slew violations at the slow corner** (11 at typical, 0 at fast) and
  **15 max-fanout violations**. These are on the measurement paths — the delay
  line, ring oscillator and witness clock — which are deliberately excluded from
  the resizer (`RSZ_DONT_TOUCH_RX`), because letting the tool buffer them would
  change the delays being measured.
  Functional risk is low given +12.49 ns of setup margin. The real effect is on
  the **delay-line step size at slow corners** (steps get longer) — and that step
  is a measured parameter anyway, not an assumed one.
- 60 Verilator lint warnings: 56 × `PINMISSING` (power pins on named standard-cell
  instances — normal in this flow, connected by the PDN) and 4 × `WIDTHEXPAND`
  (cosmetic width comparisons).

## Measurement-cell integrity

`scripts/verify_netlist.py`, run on the final gate-level netlist from the signed-off
run:

| Cell | Expected | In netlist | Source |
|---|---|---|---|
| `nand2_4` | ≥ 1 | 1 | `ring_osc.u_ro_nand` |
| `inv_4` | ≥ 2 | 2 | `ring_osc.u_ro_inv0/1` |
| `dlymetal6s2s_1` | ≥ 8 | 8 | delay line, coarse stages |
| `buf_1` | ≥ 33 | 33 | delay line fine (8 × 4) + witness clock buffer |
| `dfxtp_1` | ≥ 10 | 10 | DUT + reference + 8 witness flip-flops |
| `dfxtp_2` | ≥ 1 | 1 | DUT flavour |
| `dfrtp_1` | ≥ 1 | 1 | DUT flavour |
| `sdfxtp_1` | ≥ 1 | 1 | DUT flavour |

Beyond counting, the check is **name-aware**: it parses instance names from the
flattened netlist (e.g. `u_delay.dly_coarse[0]`) and verifies each measurement
instance still has its intended cell type. None were resized — including
`ff_dfrtp1`, which is intentionally left outside `dont_touch` so that the reset
tree can be buffered (see `method.md` §5).

## Verification carried out before tapeout

| Suite | Count | What it covers |
|---|---|---|
| Block-level cocotb (`test/unit/`) | 33 | Each block in isolation, written test-first |
| Top-level integration (`test/test.py`) | 3 + 2 gate-level | Packet framing, checksum, sequential tap order (proves back-pressure), `Fd` monitor pin toggling |
| Host tools (`host/`) | 12 | Frame layout against the RTL, resync, bad checksum, τ recovery from synthetic exponential data |
| Netlist integrity (`scripts/`) | 12 | The checker itself, including false-positive resistance |

## What silicon still has to settle

1. **Ring frequency `Fd`** — PVT dependent; exposed on `uio[1]` precisely so it can
   be counted rather than assumed. Without it, τ still follows from the slope but
   `W` cannot be given in absolute units.
2. **Delay-line step `tw_s`** — target 10–15 ps from liberty data; the real value
   needs gate-level SDF or on-chip calibration. An error rescales τ.
3. **Whether events are captured at all** — RTL simulation cannot answer this (the
   cell models have zero delay); gate-level simulation gives partial evidence, the
   chip gives the answer.

One class of bug found late in verification is worth recording, because it is the
kind that survives to silicon unnoticed: the ring oscillator's enable was tied to
a constant, so no node in the loop ever transitioned in simulation and the
oscillator sat at `X` — the asynchronous data path was silently dead while all
integration tests still passed (they were asserting a zero event count, which was
"correct" for the wrong reason). It is now started by a registered enable, and the
`Fd` monitor pin makes the same failure observable on the chip itself.
