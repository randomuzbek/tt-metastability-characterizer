# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# delay_line blok unit testi (TDD). coarse (dlymetal6s2s_1) + fine (buf_1)
# non-inverting zincir; tap_sel bir tap secer -> d_out. named-cell + keep.
#
# ⚠️ RTL-sim'de TUM delay hucreleri 0 ps (cells_sim.v: assign X=A) -> d_out
# KOMBINASYONEL olarak d_in'e esittir, HANGI tap secilirse secilsin (spec
# docs/method.md: RTL sim timing gostermez). Bu yuzden test edilen:
#   (a) POLARITE: her tap non-inverting -> d_out==d_in (inv olsaydi bazi tap'ler
#       ters cevirir; kullanici karari buf+dlymetal = polarite-guvenli),
#   (b) MUX yonlendirme X-siz calisir (her tap_sel icin gecerli cikis),
#   (c) named-cell instance'larin yapisal varligi.
# GERCEK gecikme/adim (ps) = GL-sim(SDF) + STA + silikon; host kalibrasyonu.

import cocotb
from cocotb.triggers import Timer


def _params(dut):
    return int(dut.NTAP.value), int(dut.NCOARSE.value), int(dut.NFINE.value)


@cocotb.test()
async def test_output_follows_input_all_taps(dut):
    """Her tap_sel icin d_out == d_in (0-delay sim + NON-INVERTING zincir).
    Herhangi bir tap ters cevirseydi (inv hucre) burada yakalanir -> polarite
    correctness'in RTL kapisi."""
    ntap, _, _ = _params(dut)
    for tap in range(ntap):
        dut.tap_sel.value = tap
        for bit in (0, 1, 0, 1, 1, 0):
            dut.d_in.value = bit
            await Timer(1, unit="ns")
            got = int(dut.d_out.value)
            assert got == bit, \
                f"tap {tap}: d_out={got} olmali {bit} (non-inverting, 0-delay sim)"


@cocotb.test()
async def test_tap_zero_is_input(dut):
    """tap_sel=0 = minimum gecikme tap'i = dogrudan d_in."""
    dut.tap_sel.value = 0
    dut.d_in.value = 1
    await Timer(1, unit="ns")
    assert int(dut.d_out.value) == 1
    dut.d_in.value = 0
    await Timer(1, unit="ns")
    assert int(dut.d_out.value) == 0


@cocotb.test()
async def test_named_cell_instances_present(dut):
    """Yapisal (synth-defense) checker: coarse + fine named-cell instance'lari
    generate hiyerarsisinde var (behavioral cikarim degil gercek instantiation)."""
    await Timer(1, unit="ns")
    _, ncoarse, nfine = _params(dut)
    try:
        seg0 = dut.dly_seg[0]
        coarse0 = seg0.dly_coarse
        fine0 = seg0.dly_fine[0].dly_buf
    except Exception as e:                           # noqa: BLE001
        assert False, f"delay named-cell instance hiyerarside yok: {e}"
    assert coarse0 is not None, "dly_seg[0].dly_coarse yok"
    assert fine0 is not None, "dly_seg[0].dly_fine[0].dly_buf yok"
    assert ncoarse >= 1 and nfine >= 1, "en az 1 coarse + 1 fine bekleniyor"
