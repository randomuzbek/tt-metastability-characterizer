# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# lfsr blok unit testi (TDD). 16-bit Galois LFSR (poly 0xB400, maximal-length).
# Her trial yeni bir test-data biti (bit_out) uretir; DUT/Ref FF'ler bunu
# skewed-D olarak ornekler. en=0 iken deger dondurulur (freeze).
# Referans model Python'da ayni tekrarlamayi hesaplar -> RTL ile karsilastirilir.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

POLY = 0xB400
MASK = 0xFFFF


def _next(state):
    """Galois 16-bit: LSB disari -> tum state'i poly ile XOR'la, sonra kaydir."""
    lsb = state & 1
    state >>= 1
    if lsb:
        state ^= POLY
    return state & MASK


async def _load(dut, seed):
    dut.en.value = 0
    dut.seed.value = seed
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


async def _tick(dut):
    """Bir clock kenari + registered NBA guncellemesi gorunur olsun diye
    kucuk settle. RisingEdge'den HEMEN sonra registered ciktilar pre-edge
    degeri okunur (icarus/cocotb); Timer ile post-edge deger okunur."""
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


@cocotb.test()
async def test_reset_loads_seed_nonzero(dut):
    """Reset sonrasi state = seed; seed 0 verilse bile state 0 olmamali (lock-up yok)."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _load(dut, 0xACE1)
    assert dut.value.value == 0xACE1, "reset seed'i yuklemeli"

    await _load(dut, 0x0000)
    assert dut.value.value != 0, "all-zero lock-up olmamali (seed 0 -> nonzero)"


@cocotb.test()
async def test_freeze_when_disabled(dut):
    """en=0: deger degismez (her trial degil, sadece en=1'de ilerler)."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _load(dut, 0xACE1)
    dut.en.value = 0
    before = int(dut.value.value)
    await ClockCycles(dut.clk, 5)
    assert int(dut.value.value) == before, "en=0 iken deger dondurulmali"


@cocotb.test()
async def test_matches_golden_sequence(dut):
    """en=1: RTL dizisi Python referans modeliyle birebir esler; bit_out=state LSB."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    seed = 0xACE1
    await _load(dut, seed)

    model = seed
    dut.en.value = 1
    await Timer(1, unit="ns")  # en=1 kenardan once yerlessin
    for step in range(64):
        # bit_out mevcut state'in LSB'si (ilerlemeden once)
        assert int(dut.bit_out.value) == (model & 1), \
            f"step {step}: bit_out={int(dut.bit_out.value)} olmali {model & 1}"
        await _tick(dut)
        model = _next(model)
        assert int(dut.value.value) == model, \
            f"step {step}: value={int(dut.value.value):#06x} olmali {model:#06x}"


@cocotb.test()
async def test_no_immediate_repeat(dut):
    """Maximal-length: kisa pencerede ayni deger tekrar etmez (stuck degil)."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _load(dut, 0x0001)
    dut.en.value = 1
    await Timer(1, unit="ns")
    seen = set()
    for _ in range(200):
        v = int(dut.value.value)
        assert v not in seen, f"deger {v:#06x} 200 adimda tekrarladi (stuck/kisa period)"
        seen.add(v)
        await _tick(dut)
