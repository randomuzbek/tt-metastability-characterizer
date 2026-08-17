# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# sweep_ctrl blok unit testi (TDD). Her tap icin TRIALS deneme kosar;
# sample_fail=1 olan denemeleri sayar; tap bitince emit darbesi + fail/trial
# sunar; son tap'te done. Parametreler kucuk default (TAP_COUNT/TRIALS) ile
# hizli test; gercek degerleri top instantiate ederken verir.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


async def _reset(dut):
    dut.start.value = 0
    dut.sample_fail.value = 0
    dut.stall.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


def _params(dut):
    return int(dut.TAP_COUNT.value), int(dut.TRIALS.value)


async def _run_and_collect(dut):
    """start ver, emit darbelerini (tap, fail, trial) topla, done'a kadar."""
    tap_count, trials = _params(dut)
    dut.start.value = 1
    await ClockCycles(dut.clk, 1)
    dut.start.value = 0
    records = []
    guard = tap_count * (trials + 8) + 100
    for _ in range(guard):
        await RisingEdge(dut.clk)
        if dut.emit.value == 1:
            records.append((int(dut.tap.value),
                            int(dut.fail_count.value),
                            int(dut.trial_count.value)))
        if dut.done.value == 1:
            break
    return records


@cocotb.test()
async def test_reset_idle(dut):
    """Reset sonrasi busy=0, done=0, tap=0, emit=0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    assert dut.busy.value == 0
    assert dut.done.value == 0
    assert dut.tap.value == 0
    assert dut.emit.value == 0


@cocotb.test()
async def test_sweep_no_fails(dut):
    """sample_fail=0: her tap TRIALS deneme, fail=0; TAP_COUNT kayit; done."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    tap_count, trials = _params(dut)

    dut.sample_fail.value = 0
    records = await _run_and_collect(dut)

    assert len(records) == tap_count, f"{tap_count} emit bekleniyor, {len(records)} geldi"
    for i, (tap, fail, trial) in enumerate(records):
        assert tap == i, f"emit {i}: tap={tap} olmali {i}"
        assert trial == trials, f"emit {i}: trial={trial} olmali {trials}"
        assert fail == 0, f"emit {i}: fail=0 olmali, {fail} geldi"
    assert dut.done.value == 1, "sweep sonunda done=1"


@cocotb.test()
async def test_all_fail_counts_every_trial(dut):
    """sample_fail=1 sabit: her tap'te fail_count == trial_count == TRIALS."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    tap_count, trials = _params(dut)

    dut.sample_fail.value = 1
    records = await _run_and_collect(dut)

    assert len(records) == tap_count
    for i, (tap, fail, trial) in enumerate(records):
        assert trial == trials, f"emit {i}: trial={trial} olmali {trials}"
        assert fail == trials, f"emit {i}: fail={fail} olmali {trials} (hepsi fail)"


@cocotb.test()
async def test_stall_freezes_counters(dut):
    """stall=1: trial/fail sayaclari donar (back-pressure); stall=0 devam eder.
    TOP'ta stall = uart_packet.busy -> paket iletilirken sweep beklemeli
    (yoksa emit'ler duser). sweep imzasina 'stall' girisi eklendi."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    dut.sample_fail.value = 1
    dut.start.value = 1
    await ClockCycles(dut.clk, 1)
    dut.start.value = 0
    await ClockCycles(dut.clk, 3)             # birkac trial biriksin (TRIALS'in altinda)

    dut.stall.value = 1
    await Timer(1, unit="ns")
    t1 = int(dut.trial_count.value)
    f1 = int(dut.fail_count.value)

    await ClockCycles(dut.clk, 12)            # stall boyunca donmali
    await Timer(1, unit="ns")
    assert int(dut.trial_count.value) == t1, \
        f"stall trial_count'u dondurmali: {t1} -> {int(dut.trial_count.value)}"
    assert int(dut.fail_count.value) == f1, \
        f"stall fail_count'u dondurmali: {f1} -> {int(dut.fail_count.value)}"

    dut.stall.value = 0
    await ClockCycles(dut.clk, 2)
    await Timer(1, unit="ns")
    assert int(dut.trial_count.value) > t1, "stall kalkinca sayac devam etmeli"
