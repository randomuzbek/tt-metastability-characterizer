#!/usr/bin/env python3
"""Gate-level netlist'te olcum aparatinin hayatta kaldigini dogrular.

Yesil GDS != calisan enstruman: Yosys opt_clean named-cell'i silebilir, OpenROAD
resizer UPSIZE edebilir (baseline kosusunda bir dfxtp_1 -> dfxtp_2 olmustu,
docs/hardening-summary.md). Ikisi de olcum gecikmesini bozar ->
cip ureilir ama olcmez.

Kullanim:
    python verify_netlist.py <gate_level_netlist.v>
    python verify_netlist.py --yosys-stat <gds-run.log>   # Yosys stat tablosundan

Cikis: hucre tablosu + NETLIST_OK, ya da AssertionError (eksik/upsize).
"""
import re
import sys

CELL_RX = re.compile(r"sky130_fd_sc_hd__(\w+)")

# Gercek silikon config (NCOARSE=8, NFINE=4, NDUT=4) icin beklenen minimumlar.
MIN_CELLS = {
    "nand2_4": 1,           # ring_osc.u_ro_nand
    "inv_4": 2,             # ring_osc.u_ro_inv0/1
    "inv_1": 1,             # witness_bank.u_clkinv
    "dlymetal6s2s_1": 8,    # delay_line coarse = NCOARSE
    "buf_1": 33,            # delay_line fine (8*4) + witness_bank.u_clkdly
    "dfxtp_1": 10,          # dut_ff_bank (ff_dfxtp1 + ff_ref) + witness_bank 2*4
    "dfxtp_2": 1,           # dut_ff_bank.ff_dfxtp2 -- KASITLI DUT cesidi, upsize DEGIL
    "dfrtp_1": 1,           # dut_ff_bank.ff_dfrtp1
    "sdfxtp_1": 1,          # dut_ff_bank.ff_sdfxtp1
}

# Olcum hucrelerinin "buyutulmus" varyantlari: bunlarin VARLIGI dont_touch'in
# tutmadiginin isaretidir (silinme degil, karakteristik degisimi).
UPSIZE_SUSPECTS = {
    # dfxtp_2 BURADA YOK: dut_ff_bank.ff_dfxtp2 kasitli bir DUT cesidi (beklenen 1).
    "dfxtp_1": ["dfxtp_4"],
    # ff_dfrtp1 dont_touch DISINDA (rst_n buffer'lama zorunlulugu) -> upsize riski
    # GERCEK; bu yuzden varyantlari raporlanir.
    "dfrtp_1": ["dfrtp_2", "dfrtp_4"],
    "sdfxtp_1": ["sdfxtp_2", "sdfxtp_4"],
    "inv_1": ["inv_2", "inv_8", "inv_16"],
    "buf_1": ["buf_2", "buf_4", "buf_6", "buf_8"],
    "dlymetal6s2s_1": ["dlymetal6s4s_1", "dlymetal6s6s_1"],
}


def count_cells(text):
    """Netlist metnindeki sky130 hucre orneklerini sayar."""
    counts = {}
    for m in CELL_RX.finditer(text):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def verify_netlist(text, minimums=None):
    """Minimumlarin altinda kalan hucre varsa AssertionError, yoksa sayimlari dondurur."""
    minimums = MIN_CELLS if minimums is None else minimums
    counts = count_cells(text)
    missing = {c: (need, counts.get(c, 0)) for c, need in minimums.items()
               if counts.get(c, 0) < need}
    assert not missing, (
        "olcum aparati eksik/optimize edildi (hucre: (beklenen, bulunan)): "
        f"{missing}"
    )
    return counts


def upsize_report(counts, minimums=None):
    """GLOBAL sayimla upsize suphesi. ⚠️ Kaba: tasarimin kendi mantigi da ayni
    varyantlari kullanir (or. dfrtp_2 = sweep/uart register'lari, inv_2/buf_2 =
    normal lojik) -> FALSE POSITIVE uretir. Ismi-farkinda kontrol icin
    upsize_report_by_instance() kullan."""
    minimums = MIN_CELLS if minimums is None else minimums
    hits = []
    for base in minimums:
        for variant in UPSIZE_SUSPECTS.get(base, []):
            n = counts.get(variant, 0)
            if n:
                hits.append((base, variant, n))
    return hits


# Olcum instance'larini adindan tanir (flatten sonrasi u_delay.dly_coarse gibi
# hiyerarsik/escape'li adlar) -> hangi hucre tipiyle gerceklenmis olmasi gerekir.
MEASUREMENT_INSTANCES = [
    ("dly_coarse", "dlymetal6s2s_1"),
    ("dly_buf", "buf_1"),
    ("ff_dfxtp1", "dfxtp_1"),
    ("ff_dfxtp2", "dfxtp_2"),
    ("ff_dfrtp1", "dfrtp_1"),
    ("ff_sdfxtp1", "sdfxtp_1"),
    ("ff_ref", "dfxtp_1"),
    ("ff_a", "dfxtp_1"),
    ("ff_b", "dfxtp_1"),
    ("u_clkinv", "inv_1"),
    ("u_clkdly", "buf_1"),
    ("u_ro_nand", "nand2_4"),
    ("u_ro_inv0", "inv_4"),
    ("u_ro_inv1", "inv_4"),
]

INSTANCE_RX = re.compile(r"sky130_fd_sc_hd__(\w+)\s+(\\?[\w.$\[\]:]+)\s*\(")


def instances(text):
    """[(hucre_tipi, instance_adi)] -- netlist'teki tum sky130 instance'lari."""
    return [(m.group(1), m.group(2).lstrip("\\")) for m in INSTANCE_RX.finditer(text)]


def upsize_report_by_instance(text):
    """Olcum instance'i BEKLENEN hucre tipiyle mi gerceklenmis? Sapmalari dondurur.

    Doner: [(instance_adi, beklenen_hucre, bulunan_hucre)] -- bos liste = temiz.
    Tasarimin geri kalanindaki ayni-varyant hucreleri KARISMAZ (isim filtresi).
    """
    deviations = []
    for cell, name in instances(text):
        for frag, expected in MEASUREMENT_INSTANCES:
            if frag in name and cell != expected:
                deviations.append((name, expected, cell))
                break
    return deviations


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    counts = verify_netlist(text)
    for cell, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{n:5d}  {cell}")

    dev = upsize_report_by_instance(text)
    if dev:
        for name, expected, found in dev:
            print(f"UPSIZE: {name}  beklenen {expected}  bulunan {found} "
                  f"(RSZ_DONT_TOUCH_RX kacagi -> olcum gecikmesi degisti)")
        print(f"NETLIST_FAIL: {len(dev)} olcum instance'i yeniden boyutlandirilmis")
        return 1

    named = sum(1 for cell, name in instances(text)
                if any(frag in name for frag, _ in MEASUREMENT_INSTANCES))
    print(f"NETLIST_OK: olcum aparati netlist'te duruyor "
          f"({named} named-cell instance, hepsi beklenen hucre tipinde)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
