"""Exact one-sided Clopper-Pearson bounds (pure Python, no SciPy)."""
from __future__ import annotations

import math


def _log_pmf(i, n, p):
    if p <= 0:
        return 0.0 if i == 0 else -math.inf
    if p >= 1:
        return 0.0 if i == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p))


def binom_cdf(k, n, p):
    """P(X <= k), X ~ Bin(n, p)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return min(1.0, sum(math.exp(_log_pmf(i, n, p)) for i in range(k + 1)))


def _bisect(f, lo=0.0, hi=1.0, iters=80):
    # f is monotone increasing in p on [lo, hi]; find root of f(p) = 0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp_lower(k, n, alpha):
    """One-sided (1-alpha) lower confidence bound for p given k successes in n."""
    if k <= 0:
        return 0.0
    # P(X >= k | p) increases in p; solve = alpha
    return _bisect(lambda p: (1 - binom_cdf(k - 1, n, p)) - alpha)


def cp_upper(k, n, alpha):
    """One-sided (1-alpha) upper confidence bound for p given k successes in n."""
    if k >= n:
        return 1.0
    # P(X <= k | p) decreases in p; solve = alpha
    return _bisect(lambda p: alpha - binom_cdf(k, n, p))


def min_shots(direction, threshold, alpha, n_max=10_000_000):
    """Fewest shots for which the BEST-CASE outcome could yield ACCEPT.

    at_most  (claim rate <= thr): best case k=0 -> 1-alpha^(1/n) <= thr
    at_least (claim rate >= thr): best case k=n -> alpha^(1/n) >= thr
    """
    if direction == "at_most":
        if threshold <= 0:
            return None
        n = math.log(alpha) / math.log1p(-threshold)
    else:
        if threshold >= 1:
            return None
        if threshold <= 0:
            return 1
        n = math.log(alpha) / math.log(threshold)
    n = max(1, math.ceil(n - 1e-9))
    return n if n <= n_max else None


def projected_shots(direction, threshold, rate, alpha, n_now, n_max):
    """HEURISTIC: smallest n (doubling search) at which the CURRENT observed
    rate, if it persisted, would resolve to ACCEPT or REJECT. Not a guarantee."""
    n = max(n_now, 1)
    while n <= n_max:
        n *= 2
        k = round(rate * n)
        lo, hi = cp_lower(k, n, alpha), cp_upper(k, n, alpha)
        if direction == "at_most" and (hi <= threshold or lo > threshold):
            return min(n, n_max)
        if direction == "at_least" and (lo >= threshold or hi < threshold):
            return min(n, n_max)
    return None


def min_shots_within(lo, hi, alpha, n_max=10_000_000):
    """Fewest shots for which an outcome at the interval midpoint could yield an
    equivalence ACCEPT (both one-sided bounds inside [lo, hi])."""
    mid = (lo + hi) / 2

    def ok(n):
        k = round(mid * n)
        return cp_lower(k, n, alpha) >= lo and cp_upper(k, n, alpha) <= hi

    n = 1
    while not ok(n):
        n *= 2
        if n > n_max:
            return None
    lo_n, hi_n = n // 2, n
    while hi_n - lo_n > 1:
        m = (lo_n + hi_n) // 2
        lo_n, hi_n = (lo_n, m) if ok(m) else (m, hi_n)
    return hi_n
