"""Owner-executed real Qollab R1 results: every stated number must be re-derivable
from the raw counts with both the governor stack and the independent verifier."""
import pytest

from qrg import blinding, stats
from verifier import verify_qrg

A = {"0000000": 1031, "0001111": 969}
B = {"0000000": 810, "0001111": 770, "1100000": 208, "1101111": 212}


def parity_ok(counts):
    return all(int(k[2]) == sum(map(int, k[3:])) % 2 for k in counts)


def test_package_a_live_numbers():
    v = blinding.marginalize_visible(A)
    assert sum(A.values()) == 2000 and parity_ok(A)
    k = sum(c for key, c in v.items() if "1" in key[:2])
    assert k == 0
    assert stats.cp_upper(0, 2000, 0.05) == pytest.approx(0.0014967448951882841, abs=1e-15)
    assert verify_qrg.cp_upper(0, 2000, 0.05) == pytest.approx(0.0014967448951882841, abs=1e-12)
    assert stats.cp_upper(0, 2000, 0.05) <= 0.01  # ACCEPT


def test_package_b_live_numbers():
    v = blinding.marginalize_visible(B)
    assert sum(B.values()) == 2000 and parity_ok(B)
    sx = sum(c for key, c in v.items() if key[0] == "1")
    sz = sum(c for key, c in v.items() if key[1] == "1")
    assert (sx, sz) == (420, 0)
    lo, hi = stats.cp_lower(420, 2000, 0.05), stats.cp_upper(420, 2000, 0.05)
    assert lo == pytest.approx(0.19509061378833903, abs=1e-12)
    assert hi == pytest.approx(0.22554179990774226, abs=1e-12)
    assert abs(verify_qrg.cp_lower(420, 2000, 0.05) - lo) < 1e-9
    assert 0.15 <= lo and hi <= 0.25  # TOST ACCEPT
    # audit (not governing): coin bit == sX bit on every shot
    assert all(k[0] == k[1] for k in B)
