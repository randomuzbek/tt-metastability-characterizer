# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# witness_bank blok unit testi (TDD). DUT.Q'yu iki fazda ornekler (Beer 2011
# dual-sample): q_a = inverse-clk (negedge), q_b = GECIKMELI inverse-clk.
# Silikonda gecikme geç-cozulmeyi yakalar (metastable event). RTL-sim'de clock
# gecikmesi 0 ps (see docs/method.md) -> q_a ile q_b AYNI negedge'de ornekler -> q_a==q_b -> ASLA
# sahte event. Bu blok event'i sim'de URETMEZ (dogru); event = silikon/GL.
#
# Test edilen KONTROL/YAPISAL: (a) q_a==q_b her zaman (sim event-free -> async
# veri sahte-event vermez), (b) q_a dut_q'yu negedge'de takip eder, (c) named-cell
# yapisal varlik. make BLK=witness_bank SIMLIB=cells_sim

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer, FallingEdge


async def _reset(dut):
    dut.dut_q.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


@cocotb.test()
async def test_no_false_events_in_sim(dut):
    """RTL-sim'de q_a == q_b HER ZAMAN (0-delay clock -> ayni negedge ornek).
    Async veri her cycle degisse bile sahte metastable-event YOK."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    # dut_q'yu her cycle degistir (async-veri benzeri) -> yine de q_a==q_b olmali
    for pattern in [0b0001, 0b1110, 0b1010, 0b0101, 0b1111, 0b0000, 0b1001]:
        dut.dut_q.value = pattern
        await ClockCycles(dut.clk, 1)
        await Timer(1, unit="ns")
        assert int(dut.q_a.value) == int(dut.q_b.value), \
            f"q_a={int(dut.q_a.value):#x} q_b={int(dut.q_b.value):#x} esit olmali (sim event-free)"


@cocotb.test()
async def test_qa_tracks_dut_q_on_negedge(dut):
    """q_a, dut_q'yu inverse-clk (negedge) ile ornekler -> negedge sonrasi dut_q."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    dut.dut_q.value = 0b1011
    await FallingEdge(dut.clk)          # negedge -> witness ornekler
    await Timer(1, unit="ns")
    assert int(dut.q_a.value) == 0b1011, f"q_a negedge'de dut_q ornekli, {int(dut.q_a.value):#x}"


@cocotb.test()
async def test_named_cell_instances_present(dut):
    """Yapisal checker: clock-inverter + witness FF instance'lari hiyerarside var."""
    await Timer(1, unit="ns")
    try:
        _ = dut.u_clkinv
        _ = dut.wff[0].ff_a
        _ = dut.wff[0].ff_b
    except Exception as e:                           # noqa: BLE001
        assert False, f"witness named-cell instance yok: {e}"
