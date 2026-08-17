# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# dut_ff_bank blok unit testi (TDD). 4 cesit named-cell DUT FF (dfxtp_1,
# dfxtp_2, dfrtp_1, sdfxtp_1) + 1 referans FF; hepsi skewed-D'yi CLK'de ornekler.
#
# ⚠️ RTL-sim'de named hucreler cells_sim.v functional stub'lari ile derlenir
# (make BLK=dut_ff_bank SIMLIB=cells_sim). Gercek gecikme/setup-hold YOK
# (docs/method.md) -> burada test edilen SADECE: (a) registering (Q<=D, 1 clk),
# (b) DUT/Ref ayri veri yolu, (c) named-cell instance'larin yapisal varligi.
# Gercek within-die timing = GL-sim(SDF) + STA + silikon.

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

DUT_NAMES = ["ff_dfxtp1", "ff_dfxtp2", "ff_dfrtp1", "ff_sdfxtp1", "ff_ref"]


async def _reset(dut):
    dut.d_dut.value = 0
    dut.d_ref.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)      # reset + ilk clock'lar -> tum Q tanimli (0)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


async def _tick(dut):
    """RisingEdge sonrasi registered ciktilarin post-edge degeri gorunsun."""
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


@cocotb.test()
async def test_all_dut_register_d(dut):
    """4 DUT FF de d_dut'u 1-clk gecikmeyle ayni sekilde ornekler (hepsi ozdes)."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    for bit in [1, 0, 1, 1, 0, 0, 1, 0]:
        dut.d_dut.value = bit
        await _tick(dut)
        val = int(dut.dut_q.value)
        expect = 0xF if bit else 0x0
        assert val == expect, \
            f"d_dut={bit}: dut_q={val:#03x} olmali {expect:#03x} (4 DUT ozdes registermeli)"


@cocotb.test()
async def test_ref_separate_data_path(dut):
    """Ref FF d_ref'i ornekler; DUT'lardan bagimsiz veri yolu."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await _reset(dut)

    dut.d_dut.value = 1
    dut.d_ref.value = 0
    await _tick(dut)
    assert int(dut.dut_q.value) == 0xF, "DUT'lar d_dut=1 ornekler"
    assert int(dut.ref_q.value) == 0, "Ref d_ref=0 ornekler (DUT'tan bagimsiz)"

    dut.d_dut.value = 0
    dut.d_ref.value = 1
    await _tick(dut)
    assert int(dut.dut_q.value) == 0x0, "DUT'lar d_dut=0 ornekler"
    assert int(dut.ref_q.value) == 1, "Ref d_ref=1 ornekler"


@cocotb.test()
async def test_named_cell_instances_present(dut):
    """Yapisal (synth-defense) checker: 5 named-cell instance hiyerarside var.
    Davranissal 'reg' cikarimi yerine gercekten named-cell instantiate edildigini
    dogrular -- keep + named-cell sentez-savunmasinin RTL ayagi."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")
    for name in DUT_NAMES:
        try:
            h = getattr(dut, name)
        except Exception as e:                       # noqa: BLE001
            assert False, f"named-cell instance '{name}' hiyerarside yok: {e}"
        assert h is not None, f"instance '{name}' None"
