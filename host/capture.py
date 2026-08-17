#!/usr/bin/env python3
"""Capture a measurement sweep from the chip over a USB-serial adapter.

Path A of two (see QUICKSTART.md): you have a 3.3 V USB-UART adapter wired to
`uo[0]` (and GND). If you have no adapter, use `demoboard_capture.py` instead —
it runs on the demo board's own microcontroller.

    pip install pyserial
    python capture.py --port COM5 --seconds 120 --out capture.bin

The chip sends one 14-byte frame per delay tap, 115200 baud 8N1. This script
just records bytes and reports how many valid frames it saw, so you can tell
immediately whether the wiring and the project selection are right.
"""
import argparse
import sys
import time

from decode import PKT_LEN, decode_stream


def list_ports():
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        return []
    return [(p.device, p.description) for p in lp.comports()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port (e.g. COM5, /dev/ttyUSB0). "
                                   "Omitted: list the ports and exit")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=120.0,
                    help="how long to record (default 120)")
    ap.add_argument("--out", default="capture.bin")
    args = ap.parse_args(argv)

    if not args.port:
        ports = list_ports()
        if not ports:
            print("No serial ports found (is pyserial installed?)", file=sys.stderr)
            return 2
        print("Available ports:")
        for dev, desc in ports:
            print(f"  {dev}\t{desc}")
        print("\nRe-run with --port <device>")
        return 0

    try:
        import serial
    except ImportError:
        print("pyserial is required:  pip install pyserial", file=sys.stderr)
        return 2

    with serial.Serial(args.port, args.baud, timeout=0.5) as ser, \
            open(args.out, "wb") as fh:
        print(f"Recording {args.seconds:.0f} s from {args.port} at {args.baud} baud…")
        print("Pulse ui[0] (start) now if you have not already.")
        deadline = time.monotonic() + args.seconds
        total = 0
        last_report = 0.0
        while time.monotonic() < deadline:
            chunk = ser.read(4096)
            if chunk:
                fh.write(chunk)
                total += len(chunk)
            now = time.monotonic()
            if now - last_report > 5.0:
                print(f"  {total} bytes (~{total // PKT_LEN} frames)")
                last_report = now

    with open(args.out, "rb") as fh:
        raw = fh.read()
    recs = decode_stream(raw)
    print(f"\n{len(raw)} bytes written to {args.out}")
    print(f"{len(recs)} valid frames decoded")

    if not recs:
        print("\nNo valid frames. Things to check, in order:")
        print("  1. Is this project selected on the demo board?")
        print("  2. Is the project clock running at 25 MHz? (baud scales with it:")
        print("     at 10 MHz the stream is 46080 baud, not 115200)")
        print("  3. Is uo[0] wired to the adapter's RX, and are grounds common?")
        print("  4. Did you pulse ui[0] (start)? uo[1] (busy) should be high.")
        return 1

    taps = sorted({r.tap for r in recs})
    print(f"taps seen: {taps[0]}..{taps[-1]} ({len(taps)} distinct)")
    print(f"events: {sum(r.fail_count for r in recs)} over "
          f"{sum(r.trial_count for r in recs)} trials")
    print(f"\nNext:  python decode.py {args.out} --csv sweep.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
