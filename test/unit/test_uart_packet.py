# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# uart_packet blok unit testi (TDD). emit darbesinde alanlari latch'ler ve
# 14-byte cerceveyi 8N1 UART'tan (icteki uart_tx) seri gonderir.
#
# Cerceve (little-endian, checksum sync DAHIL tum onceki byte'lari kapsar):
#   [0]   = 0xA5 sync
#   [1]   = mode        (bit0; ust bitler 0)
#   [2..3]= tap         (LE, 16-bit)
#   [4..7]= fail_count  (LE, 32-bit)
#   [8..11]= trial_count(LE, 32-bit)
#   [12]  = die_id
#   [13]  = XOR(byte[0..12])
# Kabul dogrulamasi: XOR(tum 14 byte) == 0.
#
# Hiz: CLKS_PER_BIT Makefile'dan COMPILE_ARGS=-Puart_packet.CLKS_PER_BIT=<n> ile
# kucultulebilir (varsayilan 217). Test _cpb(dut) ile gercek degeri okur.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

SYNC = 0xA5


async def _reset(dut):
    dut.emit.value = 0
    dut.mode.value = 0
    dut.tap.value = 0
    dut.fail_count.value = 0
    dut.trial_count.value = 0
    dut.die_id.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


def _cpb(dut):
    return int(dut.CLKS_PER_BIT.value)


async def _capture_byte(dut, cpb):
    """Seri hattan bir 8N1 byte yakala (LSB-first); (deger, stop) dondur."""
    started = False
    for _ in range(cpb * 16):          # baytlar-arasi bosluk + start bekle
        await RisingEdge(dut.clk)
        if dut.tx.value == 0:
            started = True
            break
    assert started, "start biti gelmedi (tx dusmedi)"
    # start bitinin basindayiz -> ilk data bitinin ortasina hizala
    for _ in range(cpb + cpb // 2):
        await RisingEdge(dut.clk)
    val = 0
    for i in range(8):
        val |= (int(dut.tx.value) & 1) << i      # LSB-first
        for _ in range(cpb):
            await RisingEdge(dut.clk)
    stop = int(dut.tx.value)                       # stop biti ortasi
    return val, stop


async def _capture_frame(dut, cpb, n=14):
    out = []
    for _ in range(n):
        val, stop = await _capture_byte(dut, cpb)
        assert stop == 1, "her byte stop biti 1 olmali"
        out.append(val)
    return out


async def _pulse_emit(dut, mode, tap, fail, trial, die):
    dut.mode.value = mode
    dut.tap.value = tap
    dut.fail_count.value = fail
    dut.trial_count.value = trial
    dut.die_id.value = die
    dut.emit.value = 1
    await ClockCycles(dut.clk, 1)      # bu kenarda latch (emit=1 gorulur)
    dut.emit.value = 0


@cocotb.test()
async def test_idle_before_emit(dut):
    """emit gelmeden hat idle-high, busy=0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    await ClockCycles(dut.clk, 20)
    assert dut.tx.value == 1, f"idle tx=1 olmali, gordum {dut.tx.value}"
    assert dut.busy.value == 0, f"idle busy=0 olmali, gordum {dut.busy.value}"


@cocotb.test()
async def test_frame_fields_little_endian(dut):
    """emit sonrasi 14-byte cerceve: sync/mode/tap/fail/trial/die_id dogru ve LE."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    cpb = _cpb(dut)

    mode, tap, fail, trial, die = 1, 0x1234, 0xDEADBEEF, 0x00C0FFEE, 0x5A
    await _pulse_emit(dut, mode, tap, fail, trial, die)

    b = await _capture_frame(dut, cpb, 14)
    assert b[0] == SYNC, f"sync 0xA5 olmali, {b[0]:#04x}"
    assert b[1] == mode, f"mode byte {mode} olmali, {b[1]}"
    assert (b[2] | (b[3] << 8)) == tap, f"tap LE cozulmeli: {b[2]:#04x} {b[3]:#04x}"
    assert (b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24)) == fail, "fail_count LE"
    assert (b[8] | (b[9] << 8) | (b[10] << 16) | (b[11] << 24)) == trial, "trial_count LE"
    assert b[12] == die, f"die_id {die:#04x} olmali, {b[12]:#04x}"


@cocotb.test()
async def test_checksum_whole_frame_xor_zero(dut):
    """checksum = XOR(byte[0..12]) -> tum 14 byte'in XOR'u 0 (farkli deger seti)."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    cpb = _cpb(dut)

    await _pulse_emit(dut, 0, 0xBEEF, 0x01020304, 0x0A0B0C0D, 0x99)

    b = await _capture_frame(dut, cpb, 14)
    x = 0
    for v in b:
        x ^= v
    assert x == 0, f"tum cercevenin XOR'u 0 olmali, {x:#04x}"
    chk = 0
    for v in b[:13]:
        chk ^= v
    assert b[13] == chk, f"checksum byte XOR(byte[0..12]) olmali: {b[13]:#04x} vs {chk:#04x}"


@cocotb.test()
async def test_busy_during_then_clears(dut):
    """emit sonrasi busy=1; 14-byte cerceve bitince busy=0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)
    cpb = _cpb(dut)

    await _pulse_emit(dut, 0, 0, 0, 0, 0)
    await ClockCycles(dut.clk, 2)
    assert dut.busy.value == 1, "iletim sirasinda busy=1 olmali"

    # 14 byte * 10 bit * cpb + pay
    await ClockCycles(dut.clk, cpb * 10 * 14 + cpb * 20)
    assert dut.busy.value == 0, "cerceve bitince busy=0 olmali"
