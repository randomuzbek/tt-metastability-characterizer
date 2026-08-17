# Run a measurement in 3 steps

You have a TTSKY26c chip. This project is already on it — every project on a
shuttle shares the same die, so there is nothing to build or flash. A sweep takes
about two minutes and the result is data that does not exist anywhere else: how
fast the flip-flops on *your* die recover from metastability.

Pick whichever path matches the hardware you have.

---

## Path A — you have a USB-UART adapter

Wire a 3.3 V USB-serial adapter to the demo board: adapter **RX ← `uo[0]`**, and
**GND ← GND**. Then, on your PC:

```bash
pip install pyserial
python capture.py                       # lists serial ports
python capture.py --port /dev/ttyUSB0 --seconds 120 --out capture.bin
```

In the Tiny Tapeout Commander, before or while capturing:

1. select **`tt_um_randomuzbek_charinst`**
2. set the project clock to **25 MHz**
3. set `ui[4:2]` (`ro_div`) to `3`, `ui[6:5]` (`dut_sel`) to `0`
4. pulse `ui[0]` (`start`) high for one clock — `uo[1]` (`busy`) goes high

`capture.py` reports how many valid frames it decoded, so you know within seconds
whether it is working. If it decodes zero frames it prints what to check.

## Path B — you have only the demo board

The demo board's microcontroller can do the whole job: it receives the UART
stream on `uo[0]` in software (PIO) and also measures the ring frequency on
`uio[1]`. Copy `demoboard_capture.py` and `decode.py` onto the board, then:

```python
>>> import demoboard_capture as c
>>> c.run(seconds=120)
```

It prints the measured `Fd` and writes `capture.bin`.

⚠️ This script has **never been run on real hardware** — it was written before the
chips existed. If it fails, fall back to Path A and please open an issue with the
error; fixing it helps everyone.

## Step 3 — send the data

```bash
python decode.py capture.bin --csv sweep.csv
```

Open an issue on this repository with:

- `sweep.csv` (or the raw `capture.bin`)
- the **measured `Fd`** if you have it (Path B prints it; otherwise a frequency
  counter or scope on `uio[1]`)
- the `ro_div` and `dut_sel` settings you used
- ambient temperature, if you know it
- optionally your chip's position on the wafer, if the Commander tells you

That is enough. You do not need to interpret anything — but if you are curious:

```bash
python extract.py sweep.csv --fd-hz <Fd> --fc-hz 25e6 --tw-s 15e-12
```

prints τ, W and MTBF estimates, with an R² so you can see whether the fit is
trustworthy (below 0.9 it is not — usually too little dwell).

---

## What good data looks like

- Event counts **zero at most taps**, rising steeply over the last few taps. That
  exponential tail is the measurement.
- Counts **zero everywhere**: either the aperture is not being crossed at this
  `ro_div` (try a faster setting, `ro_div = 0` or `1`) or the dwell is too short —
  repeat the sweep several times and sum per tap.
- Counts **high and flat**: something else is wrong; the UART framing may be
  misaligned. Send it anyway — a bad capture with a description is more useful to
  us than silence.

## Repeating for more statistics

Metastability events are rare by design, so more trials is strictly better. The
on-chip dwell per tap is fixed at synthesis time; longer effective dwell comes
from running the sweep repeatedly and summing the counts per tap on the host.
Multiple `capture.bin` files from the same chip and settings are ideal.

## Different flip-flop flavours

`ui[6:5]` selects which physical cell is measured: `0` = `dfxtp_1`,
`1` = `dfxtp_2`, `2` = `dfrtp_1`, `3` = `sdfxtp_1`. One sweep per setting, on the
same chip at the same temperature, gives a within-die comparison across cell
types — that comparison is free of every die-to-die confounder, which makes it
some of the most valuable data this chip can produce.
