# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# metastable_witness blok unit testi (TDD). DUT.Q iki farkli fazda ornekleniyor
# (q_early = ana kenar, q_late = geciktirilmis/ters kenar); ikisi ANLASMAZSA
# DUT FF hala coyuluyordu = metastable event (Beer/Ginosar ISCAS 2011 dual-sample;
# docs/method.md). dut_sel secilen DUT cesidinin event'ini sweep_ctrl'e verir.
#
# NOT (see docs/method.md): RTL-sim'de DUT.Q her zaman 0/1 (metastability YOK) -> q_early==q_late
# -> event=0 (dogru). Burada test edilen KONTROL MANTIGI (XOR + secim); gercek
# metastable-cozulme = silikon/GL. Kombinasyonel -> saf enjekte vektor testi.

import cocotb
from cocotb.triggers import Timer

NDUT = 4


@cocotb.test()
async def test_no_event_when_samples_agree(dut):
    """q_early == q_late (temiz cozulme) -> hicbir DUT'ta event yok."""
    for val in (0x0, 0xF, 0xA, 0x5):
        dut.q_early.value = val
        dut.q_late.value = val
        dut.dut_sel.value = 0
        await Timer(1, unit="ns")
        assert int(dut.meta.value) == 0, f"q_early==q_late={val:#x} -> meta=0 olmali"
        assert int(dut.sample_fail.value) == 0, "anlasmada sample_fail=0"


@cocotb.test()
async def test_event_when_selected_disagrees(dut):
    """Secili DUT'ta q_early != q_late -> sample_fail=1; secilmeyen bitte etkilemez."""
    # bit 2'de anlasmazlik
    dut.q_early.value = 0b0000
    dut.q_late.value = 0b0100        # sadece bit2 farkli
    await Timer(1, unit="ns")
    assert int(dut.meta.value) == 0b0100, "meta = q_early ^ q_late"

    dut.dut_sel.value = 2
    await Timer(1, unit="ns")
    assert int(dut.sample_fail.value) == 1, "dut_sel=2 (farkli bit) -> event"

    dut.dut_sel.value = 1
    await Timer(1, unit="ns")
    assert int(dut.sample_fail.value) == 0, "dut_sel=1 (ayni bit) -> event yok"


@cocotb.test()
async def test_per_dut_selection(dut):
    """Her dut_sel kendi bitinin metastable event'ini secer."""
    dut.q_early.value = 0b1010
    dut.q_late.value = 0b0000        # bit1 ve bit3 farkli
    for sel, expect in [(0, 0), (1, 1), (2, 0), (3, 1)]:
        dut.dut_sel.value = sel
        await Timer(1, unit="ns")
        assert int(dut.sample_fail.value) == expect, \
            f"dut_sel={sel}: sample_fail={int(dut.sample_fail.value)} olmali {expect}"
