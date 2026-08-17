# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# uart_tx blok unit testi (TDD). 8N1: idle-high, start(0), 8 data LSB-first, stop(1).
# CLKS_PER_BIT modul parametresi; test kisa bolucuyle kosar (mantik degismez).

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


async def _reset(dut):
    dut.data.value = 0
    dut.send.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


@cocotb.test()
async def test_idle_high(dut):
    """Reset sonrasi, send gelmeden hat idle-high ve busy=0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    await ClockCycles(dut.clk, 5)
    assert dut.tx.value == 1, f"idle tx=1 olmali, gordum {dut.tx.value}"
    assert dut.busy.value == 0, f"idle busy=0 olmali, gordum {dut.busy.value}"


def _cpb(dut):
    return int(dut.CLKS_PER_BIT.value)


async def _capture_byte(dut, cpb):
    """Seri hattan 8N1 byte yakala; (deger, stop_biti) dondur."""
    # start bitini bekle (idle-high -> 0)
    started = False
    for _ in range(cpb * 4):
        await RisingEdge(dut.clk)
        if dut.tx.value == 0:
            started = True
            break
    assert started, "start biti gelmedi (tx hic dusmedi)"
    # start bitinin ~basindayiz -> ilk data bitinin ortasina hizala
    for _ in range(cpb + cpb // 2):
        await RisingEdge(dut.clk)
    val = 0
    for i in range(8):
        val |= (int(dut.tx.value) & 1) << i      # LSB-first
        for _ in range(cpb):
            await RisingEdge(dut.clk)
    stop = int(dut.tx.value)                       # stop biti ortasi
    return val, stop


@cocotb.test()
async def test_transmits_byte_8n1(dut):
    """send darbesi sonrasi 0xA5, 8N1 (start=0, 8 data LSB-first, stop=1) olarak cikar."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    cpb = _cpb(dut)

    dut.data.value = 0xA5
    dut.send.value = 1
    await ClockCycles(dut.clk, 1)
    dut.send.value = 0

    val, stop = await _capture_byte(dut, cpb)
    assert val == 0xA5, f"iletilen byte 0xA5 olmali, gordum {val:#04x}"
    assert stop == 1, f"stop biti 1 olmali, gordum {stop}"


@cocotb.test()
async def test_busy_asserts_then_clears(dut):
    """send'den sonra busy=1; iletim bitince busy=0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    cpb = _cpb(dut)

    dut.data.value = 0x3C
    dut.send.value = 1
    await ClockCycles(dut.clk, 1)
    dut.send.value = 0
    await ClockCycles(dut.clk, 2)
    assert dut.busy.value == 1, "iletim sirasinda busy=1 olmali"

    # 10 bit (start+8+stop) + pay
    await ClockCycles(dut.clk, cpb * 11)
    assert dut.busy.value == 0, "iletim bitince busy=0 olmali"
