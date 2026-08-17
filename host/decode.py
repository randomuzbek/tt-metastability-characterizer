#!/usr/bin/env python3
"""tt_um_randomuzbek_charinst UART akisini cozer (14-byte cerceve, XOR checksum).

Wire-format KAYNAGI: src/uart_packet.v (2026-07-16 karari), little-endian:

    [0]     0xA5 sync
    [1]     {7'b0, mode}          0=shmoo, 1=mtbf
    [2..3]  tap         LE16
    [4..7]  fail_count  LE32
    [8..11] trial_count LE32
    [12]    die_id
    [13]    checksum = XOR(byte[0..12])  ->  XOR(tum 14 byte) == 0

UART: 8N1, 115200 baud @ 25 MHz (CLKS_PER_BIT=217), hat = uo_out[0].

Kullanim:
    python decode.py capture.bin              # ham dosyadan
    python decode.py capture.bin --csv out.csv
"""
import argparse
import struct
import sys
from dataclasses import dataclass

SYNC = 0xA5
PKT_LEN = 14
_FMT = "<BBHIIB"          # sync, mode, tap, fail, trial, die  (checksum ayri)


@dataclass(frozen=True)
class Record:
    die_id: int
    mode: int
    tap: int
    fail_count: int
    trial_count: int

    @property
    def fail_rate(self):
        """Tap basina olcum: fail / trial (0..1). trial=0 ise None."""
        return self.fail_count / self.trial_count if self.trial_count else None


def pack(die_id, mode, tap, fail, trial):
    """RTL ile AYNI cerceveyi uretir (test + host self-check icin)."""
    body = struct.pack(_FMT, SYNC, mode & 1, tap, fail, trial, die_id)
    chk = 0
    for b in body:
        chk ^= b
    return body + bytes([chk])


def parse_packet(pkt):
    """14 byte -> Record, ya da None (sync/uzunluk/checksum tutmuyorsa)."""
    if len(pkt) != PKT_LEN or pkt[0] != SYNC:
        return None
    chk = 0
    for b in pkt:
        chk ^= b
    if chk != 0:                       # tum cercevenin XOR'u 0 olmali
        return None
    _sync, mode, tap, fail, trial, die = struct.unpack(_FMT, pkt[:PKT_LEN - 1])
    return Record(die_id=die, mode=mode, tap=tap, fail_count=fail, trial_count=trial)


def decode_stream(raw):
    """Byte akisini tarar: SYNC'e gore resync, checksum tutmayani atar.

    Cop veri / yarim cerceve / hat gurultusu beklenen durumdur (silikon bring-up).
    """
    out, i = [], 0
    while i + PKT_LEN <= len(raw):
        if raw[i] != SYNC:
            i += 1
            continue
        rec = parse_packet(raw[i:i + PKT_LEN])
        if rec is None:
            i += 1                     # sahte sync -> bir byte kaydir
            continue
        out.append(rec)
        i += PKT_LEN
    return out


def to_csv(records):
    lines = ["die_id,mode,tap,fail_count,trial_count,fail_rate"]
    for r in records:
        rate = "" if r.fail_rate is None else f"{r.fail_rate:.9g}"
        lines.append(f"{r.die_id},{r.mode},{r.tap},{r.fail_count},{r.trial_count},{rate}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("capture", help="ham UART yakalama dosyasi (binary)")
    ap.add_argument("--csv", help="CSV cikti dosyasi")
    args = ap.parse_args(argv)

    with open(args.capture, "rb") as fh:
        raw = fh.read()
    recs = decode_stream(raw)
    print(f"{len(raw)} byte -> {len(recs)} gecerli paket "
          f"({len(recs) * PKT_LEN / len(raw) * 100:.1f}% verim)" if raw else "bos dosya")
    if args.csv:
        with open(args.csv, "w", encoding="utf-8") as fh:
            fh.write(to_csv(recs))
        print(f"CSV yazildi: {args.csv}")
    else:
        sys.stdout.write(to_csv(recs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
