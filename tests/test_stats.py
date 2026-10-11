import math

import pytest

from qrg import stats


def test_zero_event_upper_bound_closed_form():
    for n in (10, 100, 2000):
        assert stats.cp_upper(0, n, 0.05) == pytest.approx(1 - 0.05 ** (1 / n), abs=1e-9)


def test_all_event_lower_bound_closed_form():
    for n in (10, 100, 500):
        assert stats.cp_lower(n, n, 0.05) == pytest.approx(0.05 ** (1 / n), abs=1e-9)


def test_bounds_bracket_estimate_and_shrink():
    prev = 1.0
    for n in (100, 1000, 10000):
        k = n // 5
        lo, hi = stats.cp_lower(k, n, 0.05), stats.cp_upper(k, n, 0.05)
        assert lo < 0.2 < hi
        assert hi - lo < prev
        prev = hi - lo


def test_symmetry():
    assert stats.cp_lower(30, 200, 0.05) == pytest.approx(1 - stats.cp_upper(170, 200, 0.05), abs=1e-9)


def test_min_shots():
    n = stats.min_shots("at_most", 0.01, 0.05)
    assert n == math.ceil(math.log(0.05) / math.log(0.99)) == 299
    assert stats.cp_upper(0, n, 0.05) <= 0.01 < stats.cp_upper(0, n - 1, 0.05)
    assert stats.min_shots("at_least", 0.5, 0.05) == 5
