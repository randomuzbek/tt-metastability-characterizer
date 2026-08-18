# SPDX-FileCopyrightText: 2026 randomuzbek
# SPDX-License-Identifier: Apache-2.0
#
# TOP entegrasyon testi (tt_um_randomuzbek_charinst, v1 wiring).
# Zincir: lfsr -> delay_line -> dut_ff_bank -> detector -> sweep_ctrl ->
#         uart_packet -> uart_tx -> uo_out[0].
#
# NOT (see docs/method.md, evidence levels): RTL-sim'de named-cell delay/FF hucreleri 0 ps (cells_sim.v)
# -> DUT ile Ref AYNI veriyi ayni anda ornekler -> fail_count = 0 (dogru!).
# Bu test KONTROL MANTIGI + WIRING + BACK-PRESSURE dogrular: paket cercevesi
# (sync/checksum/alanlar), tap'in SIRALI ilerlemesi (kayit dusmedi = back-pressure
# calisiyor), trial=TRIALS. GERCEK timing/mismatch = GL-sim(SDF)+STA+silikon.
#
# Hiz: TB_PARAMS="-Ptb.TRIALS=4 -Ptb.CLKS_PER_BIT=8 -Ptb.NCOARSE=2 -Ptb.NFINE=1"
# (kucuk delay-line + kisa dwell/baud). Test gercek degerleri tb param'larindan okur.

import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer
from cocotb.utils import get_sim_time

SYNC = 0xA5

# GL (gate-level) kosusu: CI'in gl_test job'i `make -B GATES=yes` ile kosar.
GL = os.environ.get("GATES") == "yes"

# ⚠️ FONKSIYONEL GL SIM BU TASARIMDA KOSULAMAZ -- ring osilatoru yuzunden.
#
# TT'nin gl_test akisi PDK'nin FONKSIYONEL hucre modellerini kullaniyor
# (-DFUNCTIONAL -DUNIT_DELAY=#1). Bu modellerde ring'in kombinasyonel geri
# beslemesi pratikte SIFIR gecikmeli bir dongu oluyor: simulator ayni zaman
# damgasinda sonsuz olay uretiyor ve SIMULASYON ZAMANI HIC ILERLEMIYOR.
# Kanit: 2026-08-17 kosusu (job 95426082060) daha ILK testte (test_reset_sanity,
# RTL'de 240 ns) takildi ve GitHub'in 6 SAATLIK job limitine kadar ilerlemedi.
#
# Bu bir SILIKON sorunu DEGIL: gercek kapilarin gercek gecikmesi var, ring
# osile eder. Sadece gecikmesiz fonksiyonel model bunu temsil edemez.
# Dogru arac SDF-annotated GL sim (LibreLane .sdf uretiyor) ya da silikon.
#
# Bu yuzden GL modunda TUM testler atlanir: yoksa her push 6 saat CI yakar ve
# job "cancelled" olarak kirmizi gorunur -- yanlis alarm.
# SDF'li bir ortamda denemek icin: TT_GL_RING=1 ile kos.
GL_RING = os.environ.get("TT_GL_RING") == "1"
GL_SKIP = GL and not GL_RING          # GL'de calistirilamayan testler
GL_ONLY = not (GL and GL_RING)        # yalniz SDF'li GL'de anlamli testler


def _cfg(dut):
    trials = int(dut.TRIALS.value)
    cpb    = int(dut.CLKS_PER_BIT.value)
    ncoarse = int(dut.NCOARSE.value)
    nfine   = int(dut.NFINE.value)
    ntap    = ncoarse * (nfine + 1) + 1
    return trials, cpb, ntap


async def _reset(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


def _tx(dut):
    return int(dut.uo_out.value) & 1        # uo_out[0] = UART TX


async def _capture_byte(dut, cpb):
    """uo_out[0]'dan bir 8N1 byte yakala (LSB-first)."""
    started = False
    for _ in range(cpb * 60):               # paketler-arasi bosluk + start bekle
        await RisingEdge(dut.clk)
        if _tx(dut) == 0:
            started = True
            break
    assert started, "UART start biti gelmedi (uo_out[0] dusmedi)"
    for _ in range(cpb + cpb // 2):
        await RisingEdge(dut.clk)
    val = 0
    for i in range(8):
        val |= (_tx(dut) & 1) << i
        for _ in range(cpb):
            await RisingEdge(dut.clk)
    return val


async def _capture_packet(dut, cpb):
    return [await _capture_byte(dut, cpb) for _ in range(14)]


@cocotb.test(skip=GL_SKIP)
async def test_reset_sanity(dut):
    """Reset sonrasi: UART idle-high, busy/done=0, uio hepsi input, X yok."""
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await _reset(dut)
    uo = int(dut.uo_out.value)                       # resolvable (X olsa int() patlar)
    assert (uo & 0x1) == 1, "reset'te UART TX idle-high (uo_out[0]=1) olmali"
    assert (uo >> 1) & 1 == 0, "reset'te busy=0"
    assert (uo >> 2) & 1 == 0, "reset'te done=0"
    # uio[1] = Fd monitoru (ro_clk) -> tek output; digerleri input.
    assert int(dut.uio_oe.value) == 0x02, "yalniz uio[1] output olmali (Fd monitoru)"
    assert (int(dut.uio_out.value) & ~0x02) == 0, "uio_out'ta [1] disinda bit surulmemeli"


@cocotb.test(skip=GL_SKIP)
async def test_fd_monitor_pin(dut):
    """uio[1] = bolunmus ring clock (Fd monitoru): output-enable + toggle eder.

    Fd, MTBF = e^(Ts/tau)/(Tw*Fc*Fd) formulunun icinde -> silikonda OLCULEBILIR
    olmasi sart (yoksa W absolute cikarilamaz). Bkz. host/README.md.
    """
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = 0b000_00_100         # ro_div=1 (sim'de hizli toggle)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    assert int(dut.uio_oe.value) & 0x02, "uio[1] output olmali"

    seen = set()
    for _ in range(400):
        await ClockCycles(dut.clk, 1)
        seen.add((int(dut.uio_out.value) >> 1) & 1)
    assert seen == {0, 1}, f"uio[1] toggle etmeli (ring kosuyor), gorulen: {seen}"


@cocotb.test(skip=GL)
async def test_integration_sweep_stream(dut):
    """start -> sweep akar; ardisik UART paketleri dogru cerceve + SIRALI tap
    (back-pressure calisiyor: paket iletilirken sweep bekler, kayit dusmez).

    GL'de ATLANIR: (a) tb parametreleri netlist'te yok (gercek 256/217/41 kosar,
    saatlerce surerdi), (b) `fail == 0` iddiasi RTL'in 0-delay varsayimina dayanir
    -- GL'de gercek metastability event'i BEKLENIR (bkz. test_gl_* testleri)."""
    trials, cpb, ntap = _cfg(dut)
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    await _reset(dut)

    # start darbesi (ui_in[0]=1 bir cycle); dut_sel=0, mode=0, lfsr_ext=0
    dut.ui_in.value = 0x01
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0x00

    npkt = min(ntap, 4)                              # ilk birkac tap'i dogrula
    for k in range(npkt):
        b = await _capture_packet(dut, cpb)
        assert b[0] == SYNC, f"paket {k}: sync={b[0]:#04x} olmali 0xA5"
        x = 0
        for v in b:
            x ^= v
        assert x == 0, f"paket {k}: tum-frame XOR={x:#04x} olmali 0 (checksum)"
        tap   = b[2] | (b[3] << 8)
        fail  = b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24)
        trial = b[8] | (b[9] << 8) | (b[10] << 16) | (b[11] << 24)
        assert tap == k, f"paket {k}: tap={tap} olmali {k} (SIRALI sweep = back-pressure OK)"
        assert trial == trials, f"paket {k}: trial={trial} olmali {trials}"
        assert fail == 0, f"paket {k}: fail={fail} olmali 0 (RTL-sim 0-delay -> DUT==Ref)"
        assert b[1] == 0, f"paket {k}: mode byte={b[1]} olmali 0 (ui_in[1]=0)"


# ---------------------------------------------------------------------------
# GL-ONLY fizik dogrulamasi. RTL'de hucreler 0 ps oldugu icin bu sorularin
# cevabi RTL'den ALINAMAZ -- ama fonksiyonel GL'den de alinamaz (yukaridaki
# ring/zaman-ilerlemiyor notu). Bu testler SDF-annotated bir GL ortami icin
# hazir duruyor: TT_GL_RING=1 ile aktiflesirler. Aksi halde her zaman SKIP.
# ---------------------------------------------------------------------------

@cocotb.test(skip=GL_ONLY)
async def test_gl_ring_oscillates_and_fd_measurable(dut):
    """GL: gercek hucre gecikmeleriyle ring osile eder; Fd uio[1]'den OLCULUR.

    Bu, enstrumanin en riskli parcasi: ring durursa asenkron veri yok ->
    metastability olcumu imkansiz. Fd ayrica MTBF formulunde (Tw*Fc*Fd).
    """
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = 0b000_011_00      # ro_div=3 (÷8): pinde rahat olculur hiz
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1

    assert int(dut.uio_oe.value) & 0x02, "uio[1] output olmali (Fd monitoru)"

    t0 = get_sim_time("ns")
    prev = (int(dut.uio_out.value) >> 1) & 1
    edges = 0
    for _ in range(20000):
        await Timer(1, unit="ns")
        cur = (int(dut.uio_out.value) >> 1) & 1
        if cur != prev:
            edges += 1
            prev = cur
    span_ns = get_sim_time("ns") - t0

    assert edges > 0, ("GL'de ring OSILE ETMIYOR -> enstruman olcmez "
                      "(sentez/resizer ring'i bozdu mu? RSZ_DONT_TOUCH_RX kontrol)")
    fd_mhz = (edges / 2.0) / (span_ns * 1e-3)
    dut._log.info(f"MEASURED Fd(ro_div=3) = {fd_mhz:.3f} MHz "
                  f"({edges} kenar / {span_ns} ns)")


@cocotb.test(skip=GL_ONLY)
async def test_gl_sweep_runs_and_emits(dut):
    """GL: start sonrasi sweep gercekten calisir (busy=1) ve UART hat hareket eder.

    Gercek parametrelerle (TRIALS=256, CLKS_PER_BIT=217) tam sweep saatler surer;
    burada yalnizca CANLILIK dogrulanir: busy yukselir, TX hattinda start-bit gorulur.
    """
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    dut.ui_in.value = 0x01              # start darbesi
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0x00
    await ClockCycles(dut.clk, 5)
    assert int(dut.uo_out.value) & 0x02, "start sonrasi busy=1 olmali (sweep kosuyor)"

    # TRIALS=256 dwell + 41 tap -> ilk emit ~256 cycle sonra; TX start-bit'i yakala
    tx_low = False
    for _ in range(4000):
        await ClockCycles(dut.clk, 1)
        if (int(dut.uo_out.value) & 0x01) == 0:
            tx_low = True
            break
    assert tx_low, "ilk paketin start-bit'i (uo_out[0]=0) gorulmedi -> emit/UART akmiyor"
    dut._log.info("GL: sweep canli, ilk UART start-bit yakalandi")
