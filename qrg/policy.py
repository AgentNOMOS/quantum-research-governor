"""Deterministic policy contract (demo values; documented in docs/GOVERNANCE_POLICY.md)."""
from __future__ import annotations

import copy

from .ir import sha256

# Admissible claim vocabulary. Each claim is a statement about the RATE of a
# fault class, tied to one governor-visible syndrome event.
CLAIMS = {
    # "No detectable (weight-1) fault occurred in more than eps of shots."
    "CODE_SPACE_PRESERVED": {
        "event": "ANY", "direction": "at_most", "param": "eps",
        "claim_hyps": ["clean"], "competitor": "all_weight1",
    },
    # "Phase-type (Z or Y) weight-1 faults occur in at least rho of shots."
    "PHASE_ERROR_PRESENT": {
        "event": "SX", "direction": "at_least", "param": "rho",
        "claim_paulis": "ZY", "competitor_paulis": "IX",
    },
    # "Bit-flip-type (X or Y) weight-1 faults occur in at least rho of shots."
    "BIT_FLIP_PRESENT": {
        "event": "SZ", "direction": "at_least", "param": "rho",
        "claim_paulis": "XY", "competitor_paulis": "IZ",
    },
}

# ---- R1 vocabulary: claims phrased about OBSERVABLE syndrome events -------------
# Each claim has an observable statement (model-free apart from i.i.d. shots) and a
# model-conditional reading that holds only under the declared weight-1 Pauli model.
CLAIMS.update({
    "DETECTED_SYNDROME_RATE_AT_MOST": {
        "event": "ANY", "direction": "at_most", "param": "eps",
        "claim_hyps": ["clean"], "competitor": "all_weight1",
        "observable": "P(nontrivial syndrome: sZ=1 or sX=1 per shot) <= {eps}",
        "model_conditional": "under the weight-1 Pauli model: rate of detectable faults <= {eps}",
    },
    "PHASE_SYNDROME_RATE_AT_LEAST": {
        "event": "SX", "direction": "at_least", "param": "rho",
        "claim_paulis": "ZY", "competitor_paulis": "IX",
        "observable": "P(sX=1 per shot) >= {rho}",
        "model_conditional": "under the weight-1 Pauli model: rate of Z/Y faults >= {rho}",
    },
    # Equivalence (TOST) claim: both one-sided level-alpha bounds inside [lo, hi].
    "PHASE_SYNDROME_RATE_WITHIN": {
        "event": "SX", "direction": "within", "params": ["lo", "hi"],
        "claim_paulis": "ZY", "competitor_paulis": "IX",
        "observable": "{lo} <= P(sX=1 per shot) <= {hi}",
        "model_conditional": "under the weight-1 Pauli model: Z/Y fault rate in [{lo}, {hi}]",
    },
})

# Claims that exceed what a distance-2 detection experiment on an ideal
# simulator can ever support, regardless of shot count.
CEILING = {
    "ERROR_LOCATED": "distance-2 code: weight-1 faults are detectable but not locatable",
    "ERROR_CORRECTED": "[[4,2,2]] detects, it cannot correct; no recovery was performed",
    "NO_ERROR_OCCURRED": "weight-2 Paulis (e.g. logical XXII) leave both syndromes at +1",
    "LOGICAL_STATE_INTACT": "phase-type logical operators on |00>_L are invisible here",
    "HARDWARE_FIDELITY": "an ideal simulator is not evidence about physical hardware",
    "FAULT_TOLERANT": "single-ancilla extraction is not a fault-tolerant protocol",
    "QUANTUM_ADVANTAGE": "nothing in this experiment measures computational advantage",
    # R1 additions
    "PHYSICAL_ERROR_RATE_AT_MOST": "only syndromes are observed; syndrome-silent faults (e.g. XXII) exist",
    "NO_PHYSICAL_ERROR": "a zero syndrome rate does not exclude syndrome-silent physical faults",
    "LOGICAL_ERROR_RATE_AT_MOST": "logical operators commute with both stabilizers and are undetectable",
    "FAULT_PROBABILITY_EQUALS": "a finite sample can never establish exact equality; use an interval claim",
}

DEFAULT_POLICY = {
    "policy_id": "QRG-R0-POLICY",
    "version": "0.1.0",
    "alpha": 0.05,                       # one-sided Clopper-Pearson level
    "permitted_backends": ["basic_simulator"],
    "ideal_backends": ["basic_simulator"],
    "max_shots_per_run": 20000,
    "budget_units": 50000,               # 1 unit per shot (demo accounting)
    "auto_approve_shots": 4096,          # above this, owner authorization needed
    "max_evidence_age_s": 3600,
    "min_event_separation": 1.0,         # exact identification of fault-class rate
    "max_out_of_model_fraction": {"basic_simulator": 0.0},
    "require_replay_backends": ["basic_simulator"],
    "permitted_variants": ["full", "z_only"],
}


def make_policy(**overrides):
    p = copy.deepcopy(DEFAULT_POLICY)
    p.update(overrides)
    return p


def policy_sha256(policy):
    return sha256({"policy": policy, "claims": CLAIMS, "ceiling": CEILING})


R1_OVERRIDES = {
    "policy_id": "QRG-R1-POLICY",
    "version": "0.2.0",
    "permitted_backends": ["basic_simulator"],
    "permitted_backend_classes": ["qiskit.providers.basic_provider.basic_simulator.BasicSimulator"],
    "denied_backend_substrings": ["ionq", "qpu", "forte", "aria", "harmony", "tempo"],
    "max_shots_per_run": 4096,
    "budget_units": 10000,
    "auto_approve_shots": 2000,
    "max_evidence_age_s": 600,
    # Seeded replay is optional in R1 (Qollab support unverified). Without replay or
    # in-process custody an ACCEPT is never granted (PROVENANCE_UNVERIFIED).
    "require_replay_backends": [],
    "accept_requires_custody_or_replay": True,
}


def make_policy_r1(**overrides):
    return make_policy(**{**R1_OVERRIDES, **overrides})
