#!/usr/bin/env python3
"""Metastability parametreleri (tau, W) cikarimi + MTBF tahmini.

Fizik:
    Bir senkronizor FF'inin cozulme suresi Ts kadar beklendiginde hata olasiligi
        P(fail) = W * Fd * exp(-Ts / tau)         (olay/clock kenari basina)
    Olcum: tap her adimda veri gecisini clock kenarindan TW_S kadar oteler ->
    Ts = tap * TW_S. Fail-rate'in log'u Ts'de DOGRUSALDIR:
        ln(rate) = ln(W * Fd * Fc) - Ts / tau
    Egimden tau, kesisimden W. MTBF = e^(Ts/tau) / (Tw * Fc * Fd).

    Fd = asenkron veri frekansi (ring-osc; uio[1] pininden OLCULUR -- olculmezse
    W absolute cikmaz, sadece tau cikar). Fc = ornekleme clock'u (25 MHz).

Kullanim:
    python extract.py capture.csv --fd-hz 3.125e6 --fc-hz 25e6 --tw-s 15e-12
"""
import argparse
import csv
import math
import sys


def extract_tau_w(records, fd_hz, fc_hz, tw_s):
    """En kucuk kareler ile ln(rate) = ln(W*Fd*Fc) - Ts/tau fit eder.

    records: fail_count > 0 olan Record (ya da .tap/.fail_count/.trial_count
             niteliklerine sahip herhangi bir nesne) listesi.
    Doner: {"tau_s", "w_s", "r2", "n"}. Uygun olmayan veride ValueError.
    """
    xs, ys = [], []
    for r in records:
        if r.fail_count <= 0 or r.trial_count <= 0:
            continue                        # ln(0) -> tanimsiz; sifir-fail tap'ler atlanir
        rate = (r.fail_count / r.trial_count) * fc_hz    # olay/saniye
        xs.append(r.tap * tw_s)
        ys.append(math.log(rate))
    n = len(xs)
    if n < 3:
        raise ValueError(f"tau fit icin en az 3 sifir-olmayan nokta gerekir, {n} var")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("tum noktalar ayni tap'te -- sweep calismamis")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    if slope >= 0:
        raise ValueError("egim >= 0: fail-rate Ts ile artiyor -> bu veri "
                         "metastability cozulmesi DEGIL (wiring/aperture hatasi?)")
    tau = -1.0 / slope
    intercept = my - slope * mx
    w = math.exp(intercept) / (fd_hz * fc_hz)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"tau_s": tau, "w_s": w, "r2": r2, "n": n}


def mtbf_s(ts_s, tau_s, w_s, fc_hz, fd_hz):
    """Verilen cozulme suresi icin MTBF (saniye). Tw = W (aperture genisligi)."""
    return math.exp(ts_s / tau_s) / (w_s * fc_hz * fd_hz)


class _Row:
    """decode.py CSV satirini extract_tau_w'nin bekledigi arayuze sarar."""

    def __init__(self, tap, fail_count, trial_count):
        self.tap = tap
        self.fail_count = fail_count
        self.trial_count = trial_count


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [_Row(int(r["tap"]), int(r["fail_count"]), int(r["trial_count"]))
                for r in csv.DictReader(fh)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", help="decode.py --csv cikti dosyasi")
    ap.add_argument("--fd-hz", type=float, required=True,
                    help="asenkron veri frekansi (uio[1] Fd monitorunden OLCULEN)")
    ap.add_argument("--fc-hz", type=float, default=25e6, help="ornekleme clock'u")
    ap.add_argument("--tw-s", type=float, required=True,
                    help="delay-line adim suresi (GL/silikon olcumu, or. 15e-12)")
    args = ap.parse_args(argv)

    rows = load_csv(args.csv)
    out = extract_tau_w(rows, fd_hz=args.fd_hz, fc_hz=args.fc_hz, tw_s=args.tw_s)
    print(f"n={out['n']} nokta  r2={out['r2']:.4f}")
    print(f"tau = {out['tau_s'] * 1e12:.2f} ps")
    print(f"W   = {out['w_s'] * 1e12:.4f} ps")
    if out["r2"] < 0.9:
        print("UYARI: r2 < 0.9 -- fit zayif; tau/W guvenilir DEGIL "
              "(gurultu, yetersiz dwell, ya da tap araligi aperture'i tam taramiyor)",
              file=sys.stderr)
    for ts_ps in (100, 500, 1000):
        m = mtbf_s(ts_ps * 1e-12, out["tau_s"], out["w_s"], args.fc_hz, args.fd_hz)
        print(f"MTBF(Ts={ts_ps} ps) = {m:.3e} s  ({m / 3.15576e7:.3e} yil)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
