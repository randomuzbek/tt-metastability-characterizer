"""verify_netlist icin unit testler -- sentetik netlist, PDK/CI gerektirmez.

Kosum:  cd scripts && python -m pytest test_verify_netlist.py -v
"""
import pytest

from verify_netlist import MIN_CELLS, count_cells, upsize_report, verify_netlist

GOOD = r"""
module tt_um_randomuzbek_charinst (clk, rst_n);
 sky130_fd_sc_hd__nand2_4 \u_ro.u_ro_nand (.A(x), .B(y), .Y(z));
 sky130_fd_sc_hd__inv_4 \u_ro.u_ro_inv0 (.A(z), .Y(w));
 sky130_fd_sc_hd__inv_4 \u_ro.u_ro_inv1 (.A(w), .Y(x));
 sky130_fd_sc_hd__inv_1 \u_wit.u_clkinv (.A(clk), .Y(clk_n));
 sky130_fd_sc_hd__dlymetal6s2s_1 \u_delay.dly_coarse[0] (.A(a), .X(b));
 sky130_fd_sc_hd__buf_1 \u_delay.dly_buf[0] (.A(b), .X(c));
 sky130_fd_sc_hd__dfxtp_1 \u_ffbank.ff_dfxtp1 (.CLK(clk), .D(c), .Q(q));
 sky130_fd_sc_hd__dfrtp_1 \u_ffbank.ff_dfrtp1 (.CLK(clk), .D(c), .Q(q2));
 sky130_fd_sc_hd__sdfxtp_1 \u_ffbank.ff_sdfxtp1 (.CLK(clk), .D(c), .Q(q3));
endmodule
"""

# Kucuk-config minimumlari (sentetik netlist gercek 8x4 delay-line'i icermez).
SMALL = {"nand2_4": 1, "inv_4": 2, "inv_1": 1, "dlymetal6s2s_1": 1,
         "buf_1": 1, "dfxtp_1": 1, "dfrtp_1": 1, "sdfxtp_1": 1}

RING_DELETED = "\n".join(ln for ln in GOOD.splitlines() if "nand2_4" not in ln)
# Gercek upsize: dfxtp_1 -> dfxtp_4. (dfxtp_2 KULLANILMAZ: o kasitli bir DUT cesidi.)
FF_UPSIZED = GOOD.replace("sky130_fd_sc_hd__dfxtp_1", "sky130_fd_sc_hd__dfxtp_4")
DFRTP_UPSIZED = GOOD.replace("sky130_fd_sc_hd__dfrtp_1", "sky130_fd_sc_hd__dfrtp_2")


def test_counts_named_cells():
    counts = count_cells(GOOD)
    assert counts["nand2_4"] == 1
    assert counts["inv_4"] == 2
    assert counts["dlymetal6s2s_1"] == 1


def test_passes_when_apparatus_intact():
    counts = verify_netlist(GOOD, minimums=SMALL)
    assert counts["buf_1"] == 1


def test_raises_when_ring_optimized_away():
    with pytest.raises(AssertionError) as excinfo:
        verify_netlist(RING_DELETED, minimums=SMALL)
    assert "nand2_4" in str(excinfo.value)


def test_raises_when_measurement_ff_upsized():
    """dfxtp_1 -> dfxtp_4 upsize = gecikme karakteristigi degisti = FAIL."""
    with pytest.raises(AssertionError) as excinfo:
        verify_netlist(FF_UPSIZED, minimums=SMALL)
    assert "dfxtp_1" in str(excinfo.value)


def test_upsize_report_flags_dont_touch_leak():
    hits = upsize_report(count_cells(FF_UPSIZED), minimums=SMALL)
    assert ("dfxtp_1", "dfxtp_4", 1) in hits


def test_upsize_report_flags_dfrtp_variant():
    """ff_dfrtp1 dont_touch DISINDA (rst_n buffer'lama) -> upsize'i izlenmeli."""
    hits = upsize_report(count_cells(DFRTP_UPSIZED), minimums=SMALL)
    assert ("dfrtp_1", "dfrtp_2", 1) in hits


def test_intended_dut_flavor_dfxtp_2_not_flagged_as_upsize():
    """dut_ff_bank.ff_dfxtp2 kasitli DUT cesidi -- upsize sanilmamali."""
    netlist = GOOD + "\n sky130_fd_sc_hd__dfxtp_2 \\u_ffbank.ff_dfxtp2 (.CLK(clk));\n"
    hits = upsize_report(count_cells(netlist), minimums=SMALL)
    assert not [h for h in hits if h[1] == "dfxtp_2"]


def test_default_minimums_match_silicon_config():
    # NCOARSE=8, NFINE=4, NDUT=4 -> src/ okunarak turetildi
    assert MIN_CELLS["dlymetal6s2s_1"] == 8
    assert MIN_CELLS["buf_1"] == 33          # 8*4 fine + witness u_clkdly
    assert MIN_CELLS["dfxtp_1"] == 10        # dut_ff_bank ff_dfxtp1+ff_ref + witness 8
    assert MIN_CELLS["dfxtp_2"] == 1         # dut_ff_bank.ff_dfxtp2 (DUT cesidi)
    assert MIN_CELLS["nand2_4"] == 1 and MIN_CELLS["inv_4"] == 2


# ---- isim-farkinda upsize kontrolu (global sayim false-positive uretiyordu) ----

def test_instance_report_clean_on_good_netlist():
    from verify_netlist import upsize_report_by_instance
    assert upsize_report_by_instance(GOOD) == []


def test_instance_report_ignores_unrelated_design_cells():
    """Tasarimin kendi register'lari (dfrtp_2 x200) upsize sanilmamali."""
    from verify_netlist import upsize_report_by_instance
    noise = "\n".join(f" sky130_fd_sc_hd__dfrtp_2 _{i:04d}_ (.CLK(clk));" for i in range(200))
    assert upsize_report_by_instance(GOOD + "\n" + noise) == []


def test_instance_report_catches_resized_measurement_cell():
    from verify_netlist import upsize_report_by_instance
    bad = GOOD.replace(r"sky130_fd_sc_hd__dfrtp_1 \u_ffbank.ff_dfrtp1",
                       r"sky130_fd_sc_hd__dfrtp_2 \u_ffbank.ff_dfrtp1")
    dev = upsize_report_by_instance(bad)
    assert dev == [("u_ffbank.ff_dfrtp1", "dfrtp_1", "dfrtp_2")], dev


def test_instances_parses_escaped_hierarchical_names():
    from verify_netlist import instances
    got = dict((name, cell) for cell, name in instances(GOOD))
    assert got["u_delay.dly_coarse[0]"] == "dlymetal6s2s_1"
    assert got["u_ro.u_ro_nand"] == "nand2_4"
