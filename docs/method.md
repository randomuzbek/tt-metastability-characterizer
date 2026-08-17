# Measurement method

Why this instrument is built the way it is, and what each design choice buys.
Companion documents: [`info.md`](info.md) (datasheet), [`hardening-summary.md`](hardening-summary.md)
(physical evidence), [`../host/README.md`](../host/README.md) (data format and extraction).

## 1. What is being measured

A flip-flop sampling data that changes near its clock edge can enter a
**metastable** state: the internal node sits near the switching threshold and the
output is undefined until it resolves. Resolution is exponential in time — the
probability that a flip-flop is still undecided after a settling time `Ts` is

```
P(unresolved at Ts) = W · Fd · e^(−Ts / τ)          per clock edge
```

- **τ** — resolution time constant. Set by the transistor gain-bandwidth of the
  storage loop. Small τ = recovers fast.
- **W** — effective aperture width, in units of time. How wide the "dangerous"
  window around the clock edge is.
- **Fd** — rate of asynchronous data transitions.
- **Fc** — sampling clock rate (25 MHz here).

Hence the synchronizer failure relation used everywhere in digital design:

```
MTBF = e^(Ts/τ) / (Tw · Fc · Fd)
```

τ and W are properties of the manufactured device, not of the RTL. For SKY130
they are **not** in the published PDK: corner libraries give deterministic
setup/hold constraints at nominal corners, not the statistical resolution
behaviour of a real die.

## 2. Why the data source must be a ring oscillator

The single most important constraint: **the data must be genuinely asynchronous
to the sampling clock.** A synchronous pattern generator (LFSR, counter) clocked
by the same clock produces edges at fixed phase relative to that clock; it either
never lands in the aperture or always lands outside it. Either way the failure
count is a constant, and no τ can be extracted. `Fd` appears explicitly in the
MTBF relation for this reason.

So the data comes from an on-chip **3-stage inverting ring oscillator**
(`nand2_4` + 2 × `inv_4`, combinational loop) followed by a programmable ripple
divider (`ui[4:2]` selects ÷1 … ÷256), and then a ÷2 toggle so that transitions
are spread across clock phases. The ring runs at its own natural, PVT-dependent
frequency, uncorrelated with the 25 MHz clock — which is exactly the property
required, and also the reason `Fd` must be **measured**, not assumed.

Two consequences the design handles explicitly:

- **The ring is a deliberate combinational loop.** It is instantiated from named
  standard cells with `keep` attributes so synthesis cannot optimize it away, and
  it is excluded from resizing (see §5).
- **A ring needs a kick to start in simulation.** Held at a constant enable, every
  node in the loop stays at `X` in a Verilog simulator forever — the oscillator
  looks dead and, worse, silently produces *no* data. The enable is therefore
  driven by a flip-flop that is 0 during reset and 1 afterwards; that 0→1
  transition starts the loop deterministically in RTL simulation, gate-level
  simulation and silicon alike.

An external async source can be substituted on `uio[0]` (`ui[7] = 1`) to
cross-check the on-chip ring against a known-frequency generator.

## 3. Sweeping the aperture: the delay line

To map the exponential tail, the data edge is moved through the aperture in small
steps. The delay line is a Vernier structure: 8 coarse stages
(`sky130_fd_sc_hd__dlymetal6s2s_1`, ~87 ps each) each followed by 4 fine buffers
(`buf_1`, ~54 ps each), tapped to give **41 positions**. `sweep_ctrl` selects the
tap; `Ts = tap · tw_s` where `tw_s` is the per-step delay.

Sizing rationale, from the SKY130 `dfxtp_1` liberty data:

| Corner | setup | hold | raw window (setup + \|hold\|) |
|---|---|---|---|
| tt 025C 1v80 | +84 ps | −60 ps | ~144 ps |
| ss 100C 1v60 | +280 ps | −225 ps | ~505 ps |
| ff n40C 1v95 | +50 ps | −37 ps | ~87 ps |

Covering the slow-corner window (~505 ps) while resolving the typical one
(~144 ps) with 10–15 samples sets the target step at **~10–15 ps** and the total
range in the hundreds of ps. A single `inv_1` is ~17 ps, so a plain inverter
chain would be too coarse — hence coarse + fine.

`tw_s` is a **measured** quantity, like `Fd`. An error in it rescales τ linearly
(the shape of the curve, and therefore the comparison between flip-flop flavours,
survives).

## 4. Detecting an event: dual-sample witness

There is no way to observe "undecided" directly from outside. Instead the DUT
output is sampled **twice, a short delay apart**, by two witness flip-flops
clocked on the inverted clock, the second through a `keep`-protected buffer. If
the two samples disagree, the DUT output was still moving between them — that is,
it had not resolved. `metastable_witness` XORs the pair and reports the event for
the selected DUT (`ui[6:5]`).

This is the standard late-resolution detection scheme (cf. Beer & Ginosar,
ISCAS 2011): it counts *slow resolutions*, which is precisely the quantity whose
distribution in `Ts` carries τ.

Four DUT flavours are measured on the same die — `dfxtp_1`, `dfxtp_2`, `dfrtp_1`,
`sdfxtp_1` — logically identical (plain D flip-flops, special pins tied off) but
physically different cells. Their relative τ/W is therefore a within-die
comparison, free of die-to-die and temperature confounders.

## 5. Keeping synthesis from destroying the instrument

Every measurement element is a **structurally instantiated named standard cell**
with `(* keep = "true" *)`, never inferred logic. That is not enough on its own:
the placer's resizer will happily upsize or buffer cells to fix slew or timing,
which changes the very delays being measured. `src/config.json` therefore sets

- `SYNTH_KEEP_HIERARCHY_MODULES` for `delay_line`, `dut_ff_bank`, `witness_bank`,
  `ring_osc`
- `RSZ_DONT_TOUCH_RX` matching all measurement instance names — **without a `^`
  anchor**, because after flattening the names are hierarchical
  (`u_delay.dly_coarse`)

One instance is deliberately *outside* `dont_touch`: `ff_dfrtp1`, whose `RESET_B`
pin sits on the global reset net. Locking it prevents the tool from buffering the
reset tree at all, which is a hard error. Instead it is left resizable and the
netlist is checked afterwards (`scripts/verify_netlist.py` verifies that every
measurement instance still has its expected cell type — it does).

`scripts/verify_netlist.py` is the guard for this whole class of failure: a green
GDS is not the same as a working instrument.

## 6. Data path out

`sweep_ctrl` runs `TRIALS` trials per tap, counting events, then raises a
one-cycle `emit`. `uart_packet` latches the record and serializes a 14-byte
little-endian frame through `uart_tx` (8N1, 115200 baud at 25 MHz) onto `uo[0]`.

Back-pressure closes the loop: `sweep_ctrl.stall = uart_packet.busy`, so the sweep
freezes while a frame is in flight and no record is ever dropped. The tap sequence
observed by the host is therefore strictly sequential — which the integration test
asserts, making a dropped record a test failure rather than silent data loss.

Note that the packet latch is *not* redundant: `emit` is combinational and on that
same clock edge the sweep controller already advances the tap and clears its
counters, so the latch is what captures the correct instant.

Longer dwell than the compile-time `TRIALS` is obtained by repeating sweeps and
summing per tap on the host — statistically equivalent and it keeps the on-chip
counters small.

## 7. Evidence levels — do not conflate these

| Question | Answered by | Where |
|---|---|---|
| Is the control logic and framing correct? | RTL simulation, 36 cocotb tests | `test/` |
| Does it fit, close timing, pass DRC/LVS? | LibreLane signoff, 9 corners | [`hardening-summary.md`](hardening-summary.md) |
| Did synthesis preserve the measurement cells? | netlist inspection of the real GDS netlist | `scripts/verify_netlist.py` |
| Does the ring actually oscillate, and at what rate? | gate-level simulation, then silicon | `uio[1]` |
| Are metastability events actually captured? Do τ and W come out? | **silicon only** | 2027 |

**RTL simulation cannot show metastability.** The simulation models used for the
named cells have zero delay, so the DUT never enters an undecided state and the
event count is zero by construction. A zero in RTL is the *correct* result, and it
is evidence of nothing about silicon behaviour. This is why the extraction
software (`host/`) was written and tested against synthetic data before tapeout,
rather than after the chips arrive.

## 8. Scope of the crowd dataset claim

Every project on a Tiny Tapeout shuttle is printed on the same die, and each
participant receives a different die cut from the wafer. So:

- **Within one chip**, comparing the four DUT flavours measures cell-to-cell
  differences and local mismatch.
- **Across chips from different users**, the same measurement gives die-to-die and
  wafer-position spread.
- **Corner spread (ss/tt/ff) is not observable** in a single shuttle — every chip
  comes from one real process corner. PDK corner libraries are design margins,
  not the distribution of a production lot.

The contribution is therefore a measured distribution of resolution behaviour on
open silicon — mismatch and die-to-die spread — not a corner characterization.

## References

- SKY130 `sky130_fd_sc_hd` liberty timing data (`google/skywater-pdk-libs-sky130_fd_sc_hd`)
- D. Beer, R. Ginosar et al., metastability measurement and late-resolution
  detection, ISCAS 2011
- htfab, `cell-tester` (Tiny Tapeout 05) — silicon-proven std-cell ring oscillator
  on this flow
