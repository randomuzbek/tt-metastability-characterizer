# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# detector blok unit testi (TDD). Kombinasyonel: her DUT FF ciktisi (dut_q[i])
# ile Ref FF ciktisi (ref_q) XOR'lanir -> mismatch[i]. dut_sel ile secilen
# DUT'in mismatch'i sample_fail olarak sweep_ctrl'e gider.
# NOT: gercek FF gecikmesi/setup-hold GL-sim+silikon; burada SADECE XOR mantigi.

import cocotb
from cocotb.triggers import Timer


async def _settle(dut):
    await Timer(1, unit="ns")  # kombinasyonel delta yerlessin


@cocotb.test()
async def test_no_mismatch_no_fail(dut):
    """Tum DUT'lar Ref ile ayni -> mismatch=0, hangi sel olursa olsun fail=0."""
    ndut = int(dut.NDUT.value)
    dut.ref_q.value = 1
    dut.dut_q.value = (1 << ndut) - 1  # hepsi 1, ref=1 -> mismatch yok
    for sel in range(ndut):
        dut.dut_sel.value = sel
        await _settle(dut)
        assert dut.mismatch.value == 0, f"sel={sel}: mismatch=0 olmali"
        assert dut.sample_fail.value == 0, f"sel={sel}: fail=0 olmali"


@cocotb.test()
async def test_selected_dut_drives_fail(dut):
    """Sadece secili DUT Ref'ten farkliysa sample_fail=1, aksi 0."""
    ndut = int(dut.NDUT.value)
    dut.ref_q.value = 0
    # yalniz DUT#2 farkli (bit2=1), digerleri Ref ile ayni (0)
    dut.dut_q.value = (1 << 2)
    await _settle(dut)
    assert dut.mismatch.value == (1 << 2), "sadece bit2 mismatch olmali"

    dut.dut_sel.value = 2
    await _settle(dut)
    assert dut.sample_fail.value == 1, "sel=2 farkli -> fail=1"

    dut.dut_sel.value = 0
    await _settle(dut)
    assert dut.sample_fail.value == 0, "sel=0 ayni -> fail=0"


@cocotb.test()
async def test_mismatch_vector_per_dut(dut):
    """mismatch[i] = dut_q[i] ^ ref_q; sample_fail secili biti izler."""
    ndut = int(dut.NDUT.value)
    dut.ref_q.value = 1
    # bit0=1(ayni),1=0(farkli),2=1(ayni),3=0(farkli) ref=1 icin
    pattern = 0b0101 & ((1 << ndut) - 1)
    dut.dut_q.value = pattern
    expected_mm = (pattern ^ ((1 << ndut) - 1)) & ((1 << ndut) - 1)
    await _settle(dut)
    assert dut.mismatch.value == expected_mm, \
        f"mismatch={int(dut.mismatch.value):b} olmali {expected_mm:b}"

    for sel in range(ndut):
        dut.dut_sel.value = sel
        await _settle(dut)
        exp = (expected_mm >> sel) & 1
        assert dut.sample_fail.value == exp, \
            f"sel={sel}: fail={int(dut.sample_fail.value)} olmali {exp}"
