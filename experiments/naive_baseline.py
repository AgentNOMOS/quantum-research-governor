"""STRAWMAN comparator: a classical threshold rule with no integrity checks, no
quantum-derived discriminability and no claim ceiling. Used only to show which
red-team cases a 'rule engine with a quantum logo' would get wrong."""


def naive_decide(claim, counts, shots):
    if not counts:
        return "ACCEPT"  # nothing bad observed
    # visible key layout: sX sZ d3 d2 d1 d0  (coin already removed)
    k_sx = sum(v for key, v in counts.items() if key[0] == "1")
    k_sz = sum(v for key, v in counts.items() if len(key) > 1 and key[1] == "1")
    k_any = sum(v for key, v in counts.items() if key[0] == "1" or (len(key) > 1 and key[1] == "1"))
    n = max(shots, 1)
    prm = claim.get("params", {})
    t = claim["type"]
    if t == "CODE_SPACE_PRESERVED":
        return "ACCEPT" if k_any / n <= prm["eps"] else "REJECT"
    if t == "PHASE_ERROR_PRESENT":
        return "ACCEPT" if k_sx / n >= prm["rho"] else "REJECT"
    if t == "BIT_FLIP_PRESENT":
        return "ACCEPT" if k_sz / n >= prm["rho"] else "REJECT"
    return "ACCEPT" if k_any == 0 else "REJECT"
