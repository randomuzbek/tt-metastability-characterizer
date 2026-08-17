# host/ — post-silicon decode + τ/W extraction

Çip **~2027-05**'te gelecek. Bu araçlar tapeout'tan ÖNCE yazıldı ve sentetik veriyle
doğrulandı (ders: "çip üretildi, sonuç çıkmadı" olmasın).

```
python -m pytest -q          # 12/12 (sentetik veri, silikon gerekmez)
```

## Ölçüm zinciri (hatırlatma)

`ring_osc(÷N)` → asenkron veri (Fd) → `delay_line(tap)` → DUT FF (25 MHz `clk` ile
örnekler) → `witness_bank` (dual-sample) → `metastable_witness` → `sweep_ctrl` her
tap için `fail_count`/`trial_count` sayar → `uart_packet` → `uo_out[0]`.

## Wire-format (KAYNAK: `src/uart_packet.v`, 14 byte, little-endian)

| Byte | Alan | Not |
|---|---|---|
| 0 | `0xA5` | sync |
| 1 | `{7'b0, mode}` | 0=shmoo, 1=mtbf (`ui[1]`) |
| 2..3 | `tap` | LE16 |
| 4..7 | `fail_count` | LE32 — metastable event sayısı |
| 8..11 | `trial_count` | LE32 — o tap'teki deneme (dwell) |
| 12 | `die_id` | v1'de sabit `0x5A` |
| 13 | `checksum` | `XOR(byte[0..12])` → host: `XOR(14 byte) == 0` |

UART: **8N1, 115200 baud** (`CLKS_PER_BIT=217` @ 25 MHz).

## Pin haritası (bring-up için)

| Pin | Yön | İşlev |
|---|---|---|
| `ui[0]` | in | `start` |
| `ui[1]` | in | `mode` (paket alanı) |
| `ui[4:2]` | in | `ro_div` — Fd seçimi (0=en hızlı … 7=÷256) |
| `ui[6:5]` | in | `dut_sel` — ölçülen DUT çeşidi (0=dfxtp_1, 1=dfxtp_2, 2=dfrtp_1, 3=sdfxtp_1) |
| `ui[7]` | in | `ext_data` (1 → veri `uio[0]`'dan) |
| `uo[0]` | out | **UART TX** |
| `uo[1]` / `uo[2]` | out | `busy` / `done` |
| `uo[3]` | out | heartbeat (`clk`/2²⁴ ≈ 1.5 Hz) |
| `uo[7:4]` | out | canlı `tap[3:0]` (debug) |
| `uio[0]` | in | `ext_data` girişi (`ui[7]=1` iken) |

## Kullanım

```bash
# 1) Yakala (ornek: 60 s, 115200 8N1)
python -c "import serial,sys;s=serial.Serial('COM5',115200,timeout=1);open('capture.bin','wb').write(s.read(2_000_000))"

# 2) Coz -> CSV
python decode.py capture.bin --csv sweep.csv

# 3) tau / W / MTBF
python extract.py sweep.csv --fd-hz <OLCULEN_Fd> --fc-hz 25e6 --tw-s <OLCULEN_ADIM>
```

## ⚠️ Silikonda TEYİT EDİLMESİ GEREKEN iki sayı

`extract.py` iki dış girdiye bağlı; ikisi de RTL'den bilinemez:

1. **`--fd-hz` (Fd, asenkron veri frekansı).** `MTBF = e^(Ts/τ)/(Tw·Fc·Fd)` içinde
   doğrudan var. Ring-osc frekansı PVT'ye bağlı → **ölçülmeli.** v1'de ring hiçbir
   pine çıkmıyor; Fd'yi ancak dolaylı (fail-rate'in `ro_div` ile ölçeklenmesinden)
   tahmin edebilirsin. → Plan Task 3 (`uio[1]` Fd monitörü) bu boşluğu kapatmak için.
2. **`--tw-s` (delay-line adım süresi).** `Ts = tap · tw_s` dönüşümü buna dayanır.
   Hedef ~10–15 ps (`docs/method.md`);
   gerçek değer GL-sim(SDF)/STA veya silikon-üstü kalibrasyon ister.

`tw_s` yanlışsa τ **ölçek hatası** alır (bağıl profil doğru kalır); Fd yanlışsa W
absolute yanlış olur (τ etkilenmez, çünkü τ yalnız eğimden gelir).

**Model notu:** `extract_tau_w` birinci-mertebe modeli kullanır
(`P(fail) = W·Fd·e^(−Ts/τ)`, log-lineer fit). `r2 < 0.9` uyarısı görürsen τ/W
güvenilir DEĞİL — dwell yetersiz, gürültü, ya da tap aralığı aperture'ı tam
taramıyor demektir.
