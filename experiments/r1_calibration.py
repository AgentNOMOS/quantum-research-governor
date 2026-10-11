"""Exact operating characteristics of the deployed R1 decision rules.

P(verdict | true syndrome probability p) is computed by exact binomial summation
over the ACCEPT / REJECT sets of k (no simulation). Run:
  .venv/bin/python -m experiments.r1_calibration
"""
import json
import math
from pathlib import Path

from qrg import stats

ALPHA = 0.05
N = 2000


def pmf(k, n, p):
    if p == 0:
        return 1.0 if k == 0 else 0.0
    if p == 1:
        return 1.0 if k == n else 0.0
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(p) + (n - k) * math.log1p(-p))


def verdict_sets(rule, n, alpha):
    acc, rej = [], []
    for k in range(n + 1):
        lo, hi = stats.cp_lower(k, n, alpha), stats.cp_upper(k, n, alpha)
        a, r = rule(lo, hi)
        if a:
            acc.append(k)
        if r:
            rej.append(k)
    return acc, rej


def oc(acc, rej, n, ps):
    rows = []
    for p in ps:
        pa = sum(pmf(k, n, p) for k in acc)
        pr = sum(pmf(k, n, p) for k in rej)
        rows.append({"p": p, "P_ACCEPT": pa, "P_REJECT": pr, "P_ESCALATE": max(0.0, 1 - pa - pr)})
    return rows


def main():
    out = {"alpha": ALPHA, "n": N, "method": "exact binomial summation over verdict sets"}
    # Package A: DETECTED_SYNDROME_RATE_AT_MOST eps=0.01
    eps = 0.01
    acc, rej = verdict_sets(lambda lo, hi: (hi <= eps, lo > eps), N, ALPHA)
    out["A_at_most_0.01"] = {
        "accept_if_k_le": max(acc), "reject_if_k_ge": min(rej),
        "oc": oc(acc, rej, N, [0.0, 0.002, 0.004, 0.006, 0.008, 0.01, 0.012, 0.015, 0.02]),
        "false_accept_sup": "attained as p -> 0.01 from above (P_ACCEPT decreasing in p)",
        "false_accept_at_boundary": oc(acc, rej, N, [eps])[0]["P_ACCEPT"],
        "false_reject_at_boundary": oc(acc, rej, N, [eps])[0]["P_REJECT"]}
    # Package B: PHASE_SYNDROME_RATE_WITHIN [0.15, 0.25] (TOST)
    a, b = 0.15, 0.25
    acc, rej = verdict_sets(lambda lo, hi: (lo >= a and hi <= b, hi < a or lo > b), N, ALPHA)
    bound = oc(acc, rej, N, [a, b])
    out["B_within_0.15_0.25"] = {
        "accept_if_k_in": [min(acc), max(acc)],
        "oc": oc(acc, rej, N, [0.12, 0.14, 0.15, 0.16, 0.18, 0.2, 0.22, 0.24, 0.25, 0.26, 0.28]),
        "false_accept_at_boundaries": {str(r["p"]): r["P_ACCEPT"] for r in bound},
        "false_reject_at_boundaries": {str(r["p"]): r["P_REJECT"] for r in bound},
        "power_at_nominal_0.2": oc(acc, rej, N, [0.2])[0]["P_ACCEPT"]}
    # Exact counterpart of the R0 Monte Carlo (n=400, rho=0.10, PHASE >= rho)
    acc, rej = verdict_sets(lambda lo, hi: (lo >= 0.10, hi < 0.10), 400, ALPHA)
    out["R0_monte_carlo_exact_counterpart"] = {
        "oc": oc(acc, rej, 400, [0.08, 0.10, 0.13]),
        "monte_carlo_observed": {"0.08": {"ACCEPT": 0, "REJECT": 77, "ESCALATE": 123},
                                 "0.13": {"ACCEPT": 121, "REJECT": 1, "ESCALATE": 78}}}
    Path("results").mkdir(exist_ok=True)
    Path("results/r1_calibration.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
