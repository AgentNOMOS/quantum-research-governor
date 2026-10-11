"""Owner-executed REAL Qollab R2 results (2026-10-10): every stated number must be
re-derivable from the raw counts (governor stack and independent verifier)."""
import pytest

from qrg import blinding, stats
from verifier import verify_qrg

A = {"0000000": 1008, "0001111": 992}
B = {"0000000": 812, "0001111": 775, "1100000": 205, "1101111": 208}


def _parity_ok(c):
    return all(int(k[2]) == sum(map(int, k[3:])) % 2 for k in c)


def test_r2_package_a_live():
    v = blinding.marginalize_visible(A)
    assert sum(A.values()) == 2000 and _parity_ok(A)
    assert sum(c for k, c in v.items() if "1" in k[:2]) == 0
    assert stats.cp_upper(0, 2000, 0.05) == pytest.approx(0.0014967448951882841, abs=1e-15)
    assert stats.cp_upper(0, 2000, 0.05) <= 0.01


def test_r2_package_b_live():
    v = blinding.marginalize_visible(B)
    assert sum(B.values()) == 2000 and _parity_ok(B)
    sx = sum(c for k, c in v.items() if k[0] == "1")
    sz = sum(c for k, c in v.items() if k[1] == "1")
    assert (sx, sz) == (413, 0) and sx / 2000 == 0.2065
    lo, hi = stats.cp_lower(413, 2000, 0.05), stats.cp_upper(413, 2000, 0.05)
    assert lo == pytest.approx(0.19168686065152074, abs=1e-12)
    assert hi == pytest.approx(0.22195326711385566, abs=1e-12)
    assert abs(verify_qrg.cp_lower(413, 2000, 0.05) - lo) < 1e-9
    assert abs(verify_qrg.cp_upper(413, 2000, 0.05) - hi) < 1e-9
    assert 0.15 <= lo and hi <= 0.25  # TOST ACCEPT
