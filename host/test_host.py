"""host/ decode + extract testleri (sentetik veri; silikon gerekmez).

Kosum:  cd host && python -m pytest -q
"""
import math

import pytest

from decode import PKT_LEN, Record, decode_stream, pack, parse_packet, to_csv
from extract import extract_tau_w, mtbf_s


# ---------------- decode ----------------

def test_pack_matches_rtl_frame_layout():
    """src/uart_packet.v: A5 | mode | tap LE16 | fail LE32 | trial LE32 | die | chk"""
    raw = pack(die_id=0x5A, mode=1, tap=0x0107, fail=0x00000102, trial=0x00000100)
    assert len(raw) == PKT_LEN
    assert raw[0] == 0xA5
    assert raw[1] == 1
    assert raw[2:4] == bytes([0x07, 0x01])                    # tap LE
    assert raw[4:8] == bytes([0x02, 0x01, 0x00, 0x00])        # fail LE
    assert raw[8:12] == bytes([0x00, 0x01, 0x00, 0x00])       # trial LE
    assert raw[12] == 0x5A
    xor = 0
    for b in raw:
        xor ^= b
    assert xor == 0, "tum cercevenin XOR'u 0 olmali (RTL semantigi)"


def test_decodes_single_packet():
    recs = decode_stream(pack(0x5A, 0, 7, 123, 256))
    assert recs == [Record(die_id=0x5A, mode=0, tap=7, fail_count=123, trial_count=256)]


def test_resyncs_after_garbage_prefix():
    recs = decode_stream(b"\xde\xad\xbe" + pack(0x5A, 0, 3, 1, 256))
    assert len(recs) == 1 and recs[0].tap == 3


def test_decodes_consecutive_sweep_stream():
    raw = b"".join(pack(0x5A, 0, tap, tap * 2, 256) for tap in range(41))
    recs = decode_stream(raw)
    assert [r.tap for r in recs] == list(range(41))
    assert all(r.trial_count == 256 for r in recs)


def test_rejects_bad_checksum():
    raw = bytearray(pack(0x5A, 0, 3, 1, 256))
    raw[-1] ^= 0xFF
    assert decode_stream(bytes(raw)) == []


def test_survives_false_sync_byte_inside_payload():
    """Payload'da 0xA5 gecerse resync yanlis hizalanmamali."""
    good = pack(0x5A, 0, 0x00A5, 0xA5, 256)
    recs = decode_stream(b"\xa5\xa5" + good)
    assert any(r.tap == 0x00A5 and r.fail_count == 0xA5 for r in recs)


def test_parse_rejects_short_frame():
    assert parse_packet(pack(0x5A, 0, 1, 1, 1)[:-1]) is None


def test_fail_rate_and_csv():
    r = Record(0x5A, 0, 4, 128, 256)
    assert r.fail_rate == 0.5
    csv_text = to_csv([r])
    assert csv_text.splitlines()[0].startswith("die_id,mode,tap")
    assert ",4,128,256,0.5" in csv_text


# ---------------- extract ----------------

def _synthetic_sweep(tau=40e-12, w=0.5e-12, fd=3.125e6, fc=25e6, step=15e-12,
                     trials=100_000_000, ntap=41):
    """fail_rate = W*Fd*exp(-Ts/tau) modelinden sentetik sweep uretir."""
    recs = []
    for tap in range(ntap):
        ts = tap * step
        p_fail = w * fd * math.exp(-ts / tau)      # kenar basina olasilik
        recs.append(Record(0x5A, 0, tap, int(round(p_fail * trials)), trials))
    return recs


def test_extracts_tau_from_exponential_tail():
    tau, w, fd, fc, step = 40e-12, 0.5e-12, 3.125e6, 25e6, 15e-12
    recs = [r for r in _synthetic_sweep(tau, w, fd, fc, step) if r.fail_count > 0]
    out = extract_tau_w(recs, fd_hz=fd, fc_hz=fc, tw_s=step)
    assert out["tau_s"] == pytest.approx(tau, rel=0.15)
    assert out["r2"] > 0.98
    assert out["n"] >= 3


def test_raises_when_too_few_nonzero_points():
    recs = [Record(0x5A, 0, t, 0, 1000) for t in range(10)]
    with pytest.raises(ValueError, match="en az 3"):
        extract_tau_w(recs, fd_hz=1e6, fc_hz=25e6, tw_s=15e-12)


def test_raises_when_rate_increases_with_ts():
    """Fail-rate Ts ile ARTIYORSA bu metastability degil -> sessizce tau uretme."""
    recs = [Record(0x5A, 0, t, 10 * (t + 1), 100_000) for t in range(10)]
    with pytest.raises(ValueError, match="egim"):
        extract_tau_w(recs, fd_hz=1e6, fc_hz=25e6, tw_s=15e-12)


def test_mtbf_grows_exponentially_with_settling_time():
    tau, w, fc, fd = 40e-12, 0.5e-12, 25e6, 3.125e6
    m1 = mtbf_s(100e-12, tau, w, fc, fd)
    m2 = mtbf_s(200e-12, tau, w, fc, fd)
    assert m2 / m1 == pytest.approx(math.exp(100e-12 / tau), rel=1e-9)
