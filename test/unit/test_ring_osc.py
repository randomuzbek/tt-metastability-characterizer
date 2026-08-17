# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# ring_osc blok unit testi (TDD). Std-cell 3-stage inverting ring (nand2+2×inv,
# kombinasyonel feedback) + ripple divider -> ASENKRON veri/clock kaynagi
# (metastability olcumu icin, docs/method.md; MTBF=e^(Ts/tau)/(Tw·Fc·Fd),
# Fd=async veri frekansi -> senkron LFSR bunu uretemez, ring osc gerekir).
#
# ⚠️ SIM: ring hucreleri cells_sim.v'de #1 gecikmeli (osile olmak icin SART).
# Gercek frekans = silikon/GL (see docs/method.md); burada test edilen KONTROL: gate=1'de
# osile eder, gate=0'da durur, rst_n counter'i sifirlar, div bolme secer.
# Kullanim: make BLK=ring_osc SIMLIB=cells_sim

import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_oscillates_when_gated(dut):
    """gate=1: ring osile eder -> clk_out zamanla toggle eder (counter ilerler)."""
    dut.rst_n.value = 0
    dut.gate.value = 0
    dut.div.value = 0
    await Timer(5, unit="ns")
    dut.rst_n.value = 1
    dut.gate.value = 1

    seen = set()
    for _ in range(30):
        await Timer(2, unit="ns")
        seen.add(int(dut.clk_out.value))
    assert seen == {0, 1}, f"gate=1 -> clk_out toggle etmeli (oscillate), gordum {seen}"


@cocotb.test()
async def test_stops_when_ungated(dut):
    """gate=0: oscillasyon durur -> clk_out sabit kalir."""
    dut.rst_n.value = 0
    dut.gate.value = 0
    dut.div.value = 0
    await Timer(5, unit="ns")
    dut.rst_n.value = 1
    # gate=0 -> ring durur (nand ile sabitlenir), counter ilerlemez
    await Timer(20, unit="ns")
    v1 = int(dut.clk_out.value)
    await Timer(30, unit="ns")
    v2 = int(dut.clk_out.value)
    assert v1 == v2, f"gate=0 -> clk_out sabit olmali, {v1}->{v2}"


@cocotb.test()
async def test_div_selects_slower_tap(dut):
    """div daha yuksek -> daha yavas clk_out (daha az toggle ayni surede)."""
    async def _count_toggles(div_val, window_ns):
        dut.rst_n.value = 0
        dut.gate.value = 0
        dut.div.value = div_val
        await Timer(5, unit="ns")
        dut.rst_n.value = 1
        dut.gate.value = 1
        prev = int(dut.clk_out.value)
        toggles = 0
        steps = window_ns  # 1ns adim
        for _ in range(steps):
            await Timer(1, unit="ns")
            cur = int(dut.clk_out.value)
            if cur != prev:
                toggles += 1
                prev = cur
        return toggles

    fast = await _count_toggles(0, 60)   # div=0 en hizli tap
    slow = await _count_toggles(3, 60)   # div=3 daha yavas
    assert fast > slow, f"div=0 (fast) > div=3 (slow) toggle beklenir: {fast} vs {slow}"
