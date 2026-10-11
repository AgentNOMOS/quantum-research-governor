"""Independent exact predictor: a tiny pure-Python statevector simulator.

Deliberately does NOT import Qiskit, so theoretical predictions are derived
independently of the execution stack (tests assert the import boundary and
cross-check against qiskit.quantum_info.Statevector).
"""
from __future__ import annotations

import math
from functools import lru_cache
from itertools import product

from . import ir

_S = 1 / math.sqrt(2)
_M = {
    "h": ((_S, _S), (_S, -_S)),
    "x": ((0, 1), (1, 0)),
    "y": ((0, -1j), (1j, 0)),
    "z": ((1, 0), (0, -1)),
}


def _ry(t):
    c, s = math.cos(t / 2), math.sin(t / 2)
    return ((c, -s), (s, c))


def _apply(state, q, m, control=None):
    step = 1 << q
    for i in range(len(state)):
        if i & step or (control is not None and not (i >> control) & 1):
            continue
        a, b = state[i], state[i | step]
        state[i] = m[0][0] * a + m[0][1] * b
        state[i | step] = m[1][0] * a + m[1][1] * b


def statevector(ops, n=ir.N_QUBITS):
    state = [0j] * (1 << n)
    state[0] = 1 + 0j
    for op in ops:
        name = op[0]
        if name == "measure_all":
            continue
        if name in _M:
            _apply(state, op[1], _M[name])
        elif name == "ry":
            _apply(state, op[2], _ry(op[1]))
        elif name in ("cx", "cy", "cz"):
            _apply(state, op[2], _M[name[1]], control=op[1])
        else:
            raise ValueError(f"unsupported op {name}")
    return state


def distribution(ops, n=ir.N_QUBITS, eps=1e-12):
    """Exact outcome probabilities, keyed in Qiskit order (c_{n-1} ... c_0)."""
    out = {}
    for i, a in enumerate(statevector(ops, n)):
        p = (a * a.conjugate()).real
        if p > eps:
            out[format(i, f"0{n}b")] = p
    return out


def visible_distribution(variant, fault):
    out = {}
    for k, p in distribution(ir.circuit_ops(variant, fault)).items():
        v = ir.visible(k)
        out[v] = out.get(v, 0.0) + p
    return out


EVENTS = {
    "SZ": lambda v: v[-1 - ir.SZ] == "1",
    "SX": lambda v: v[-1 - ir.SX] == "1",
    "ANY": lambda v: v[-1 - ir.SZ] == "1" or v[-1 - ir.SX] == "1",
}


def event_probability(variant, fault, event):
    f = EVENTS[event]
    return sum(p for v, p in visible_distribution(variant, fault).items() if f(v))


def single_fault_hypotheses():
    """Declared fault model for claim discrimination: clean + all weight-1 Paulis."""
    hyps = {"clean": {"pattern": "IIII"}}
    for k in range(4):
        for P in "XYZ":
            pat = ["I"] * 4
            pat[k] = P
            hyps[f"{P}{k}"] = {"pattern": "".join(pat)}
    return hyps


@lru_cache(maxsize=None)
def pauli_model_support(variant):
    """Union of visible supports over ALL 4^4 data Pauli strings (and hence any
    Pauli mixture). An ideal backend can never emit a visible outcome outside it."""
    sup = set()
    for pat in product(ir.PAULIS, repeat=4):
        sup |= set(visible_distribution(variant, {"pattern": "".join(pat)}))
    return frozenset(sup)
