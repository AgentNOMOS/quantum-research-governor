"""Circuit intermediate representation for the [[4,2,2]] syndrome experiment.

The IR is a plain list of tuples so that two independent back ends can consume it:
  * qrg.runner      -> Qiskit QuantumCircuit (executed on a backend)
  * qrg.witness_sim -> pure-Python statevector (exact theoretical prediction)

Qubit / classical-bit layout (clbit i measures qubit i; Qiskit key = c6..c0):
  q0..q3  data qubits of the [[4,2,2]] code
  q4      ancilla for stabilizer Z0Z1Z2Z3  -> bit "sZ" (detects X/Y faults)
  q5      ancilla for stabilizer X0X1X2X3  -> bit "sX" (detects Z/Y faults)
  q6      fault coin (only used by stochastic synthetic faults; AUDIT CHANNEL,
          never admissible evidence for the governor)
"""
from __future__ import annotations

import hashlib
import json
import math

N_QUBITS = 7
DATA = (0, 1, 2, 3)
SZ = 4
SX = 5
COIN = 6
VARIANTS = ("full", "z_only")
PAULIS = "IXYZ"
LAYOUT = {"data": list(DATA), "sZ": SZ, "sX": SX, "coin_audit_only": COIN}


def encode_ops():
    """Logical |00>_L = (|0000> + |1111>)/sqrt2, a +1 eigenstate of XXXX and ZZZZ."""
    return [("h", 0), ("cx", 0, 1), ("cx", 0, 2), ("cx", 0, 3)]


def extract_ops(variant: str):
    """Ancilla-based stabilizer extraction; everything is measured once at the end."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    ops = [("cx", d, SZ) for d in DATA]  # ZZZZ parity onto q4
    if variant == "full":
        ops += [("h", SX)] + [("cx", SX, d) for d in DATA] + [("h", SX)]  # XXXX onto q5
    return ops


def validate_fault(fault: dict) -> dict:
    pattern = fault.get("pattern", "IIII")
    mode = fault.get("mode", "deterministic")
    if len(pattern) != 4 or any(c not in PAULIS for c in pattern):
        raise ValueError(f"bad pattern {pattern!r}")
    if mode not in ("deterministic", "stochastic"):
        raise ValueError(f"bad mode {mode!r}")
    p = float(fault.get("p", 1.0 if mode == "deterministic" else 0.0))
    if not 0.0 <= p <= 1.0:
        raise ValueError("p out of range")
    if pattern == "IIII":
        p = 0.0  # "no fault" is labelled with probability 0, never "identity with p=1"
    return {"pattern": pattern, "mode": mode, "p": p}


def fault_ops(fault: dict):
    """LABELLED SYNTHETIC fault layer, inserted between encoding and extraction.

    pattern[k] is the Pauli applied to data qubit k (string index k == qubit k).
    deterministic: apply the Pauli string.
    stochastic:    RY(theta) on the coin with sin^2(theta/2) = p, then a
                   coin-controlled Pauli string. Measuring the coin at the end
                   makes this the Pauli channel  rho -> (1-p) rho + p P rho P.
    """
    f = validate_fault(fault)
    ops = []
    if f["mode"] == "deterministic":
        for k, c in enumerate(f["pattern"]):
            if c != "I":
                ops.append((c.lower(), k))
    elif f["p"] > 0 and f["pattern"] != "IIII":
        ops.append(("ry", 2 * math.asin(math.sqrt(f["p"])), COIN))
        for k, c in enumerate(f["pattern"]):
            if c != "I":
                ops.append(("c" + c.lower(), COIN, k))
    return ops


def circuit_ops(variant: str, fault: dict | None = None):
    return encode_ops() + fault_ops(fault or {}) + extract_ops(variant) + [("measure_all",)]


def skeleton(variant: str) -> dict:
    """The authorised measurement skeleton. The fault layer is NOT part of it:
    it plays the role of the unknown environment / device under test."""
    return {
        "code": "[[4,2,2]]",
        "logical_input": "|00>_L",
        "variant": variant,
        "encode": [list(o) for o in encode_ops()],
        "fault_slot": "between_encode_and_extract",
        "extract": [list(o) for o in extract_ops(variant)],
        "layout": LAYOUT,
        "n_qubits": N_QUBITS,
    }


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def skeleton_sha256(variant: str) -> str:
    return sha256(skeleton(variant))


def bit(key: str, q: int) -> int:
    """Value of clbit q in a Qiskit-ordered key (rightmost char = clbit 0)."""
    return int(key[N_QUBITS - 1 - q])


def visible(key: str) -> str:
    """Drop the audit-only coin bit: governor-visible 6-bit key (sX sZ d3 d2 d1 d0)."""
    return key[1:]
