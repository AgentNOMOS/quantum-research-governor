"""Raw-evidence record: counts plus commitments, hashed at creation time.

Tamper-EVIDENT (hash mismatch, physics-model violation, seeded replay), not
tamper-PROOF: there is no signing key in R0 by design (no secrets).
"""
from __future__ import annotations

import hashlib
import secrets

from . import ir

SCHEMA = "qrg.evidence.v1"
REQUIRED = ("schema", "experiment_id", "nonce", "backend", "shots", "seed",
            "skeleton_sha256", "fault_commitment", "created_at", "counts",
            "counts_sha256", "record_sha256")


def fault_commitment(fault: dict, salt: str | None = None):
    """Seal the synthetic fault so the governor cannot see it; referee opens later."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(salt.encode() + ir.canonical(ir.validate_fault(fault))).hexdigest()
    return digest, salt


def open_commitment(commitment: str, fault: dict, salt: str) -> bool:
    return fault_commitment(fault, salt)[0] == commitment


def seal(record: dict) -> dict:
    r = dict(record)
    r["counts_sha256"] = ir.sha256(r["counts"])
    r.pop("record_sha256", None)
    r["record_sha256"] = ir.sha256(r)
    return r


def build(proposal, backend_name, counts, commitment, created_at):
    return seal({
        "schema": SCHEMA,
        "experiment_id": proposal["experiment_id"],
        "nonce": proposal["nonce"],
        "backend": backend_name,
        "shots": proposal["shots"],
        "seed": proposal.get("seed"),
        "skeleton_sha256": ir.skeleton_sha256(proposal["variant"]),
        "variant": proposal["variant"],
        "fault_commitment": commitment,
        "created_at": created_at,
        "counts": dict(sorted(counts.items())),
    })


def verify_hashes(record):
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return {
        "counts_sha256": ir.sha256(record["counts"]) == record["counts_sha256"],
        "record_sha256": ir.sha256(body) == record["record_sha256"],
    }
