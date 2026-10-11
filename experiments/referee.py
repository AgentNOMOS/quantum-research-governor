"""Ground-truth referee (red-team scoring only; the governor never sees this).

Uses symplectic Pauli commutation, a THIRD derivation independent of both the
Qiskit run and the pure-Python simulator.
"""


def anticommutes(pattern, stabilizer):
    # Paulis on one qubit anticommute iff both non-identity and different.
    n = sum(1 for a, b in zip(pattern, stabilizer) if a != "I" and b != "I" and a != b)
    return n % 2 == 1


def true_rates(fault):
    pat, p = fault["pattern"], (fault["p"] if fault["mode"] == "stochastic" else 1.0)
    sx = anticommutes(pat, "XXXX")   # phase-type component detected by XXXX
    sz = anticommutes(pat, "ZZZZ")   # bit-flip-type component detected by ZZZZ
    return {"SX": p * sx, "SZ": p * sz, "ANY": p * (sx or sz),
            "any_fault": p * (pat != "IIII")}


def claim_true(claim, fault):
    r = true_rates(fault)
    t, prm = claim["type"], claim.get("params", {})
    if t == "CODE_SPACE_PRESERVED":
        return r["ANY"] <= prm["eps"]
    if t == "PHASE_ERROR_PRESENT":
        return r["SX"] >= prm["rho"]
    if t == "BIT_FLIP_PRESENT":
        return r["SZ"] >= prm["rho"]
    if t == "NO_ERROR_OCCURRED":
        return r["any_fault"] == 0
    return None  # not a well-defined empirical claim (ERROR_CORRECTED, QUANTUM_ADVANTAGE, ...)
