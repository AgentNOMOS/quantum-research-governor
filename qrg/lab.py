"""Glue: proposal -> (preflight) -> one job -> sealed evidence -> replay witness."""
from __future__ import annotations

from . import evidence as ev
from . import ir, runner


def run_experiment(proposal, fault, created_at, salt="r0-demo-salt", backend=None):
    ops = ir.circuit_ops(proposal["variant"], fault)
    qc = runner.to_qiskit(ops)
    name, counts = runner.execute(qc, proposal["shots"], proposal.get("seed"), backend)
    commitment, salt = ev.fault_commitment(fault, salt)
    record = ev.build(proposal, name, counts, commitment, created_at)
    return record, {"salt": salt, "fault": ir.validate_fault(fault), "qc": qc}


def replay(proposal, fault, backend=None):
    """Independent re-execution (seeded) -> digest only. In R0 this is the same
    harness re-run; it detects post-hoc alteration, not a dishonest executor."""
    qc = runner.to_qiskit(ir.circuit_ops(proposal["variant"], fault))
    name, counts = runner.execute(qc, proposal["shots"], proposal.get("seed"), backend)
    return {"backend": name, "seed": proposal.get("seed"), "counts_sha256": ir.sha256(dict(sorted(counts.items())))}
