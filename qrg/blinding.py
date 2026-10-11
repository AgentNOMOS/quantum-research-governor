"""Explicit split of raw evidence into a GOVERNOR VIEW and an AUDIT-ONLY section.

governor view : syndrome + data bits only (6-bit keys "sX sZ d3 d2 d1 d0"),
                no fault label, no commitment, no coin outcome.
audit-only    : coin marginal, fault label, commitment and salt — used only for
                retrospective referee audit, never as input to a verdict.
"""
from __future__ import annotations

from . import ir

VIEW_SCHEMA = "qrg.governor_view.v1"
VISIBLE_LAYOUT = "sX sZ d3 d2 d1 d0"
VIEW_FIELDS = ("schema", "experiment_id", "nonce", "backend", "backend_class", "shots",
               "variant", "skeleton_sha256", "created_at", "raw_record_sha256",
               "visible_layout", "visible_counts", "visible_counts_sha256", "view_sha256")
FORBIDDEN_IN_VIEW = ("fault", "pattern", "coin", "salt", "fault_commitment", "audit", "counts")


def marginalize_visible(counts7):
    out = {}
    for k, v in counts7.items():
        vk = ir.visible(k)
        out[vk] = out.get(vk, 0) + v
    return dict(sorted(out.items()))


def seal_view(view):
    v = dict(view)
    v["visible_counts_sha256"] = ir.sha256(v["visible_counts"])
    v.pop("view_sha256", None)
    v["view_sha256"] = ir.sha256(v)
    return v


def governor_view(raw_record, backend_class=None):
    return seal_view({
        "schema": VIEW_SCHEMA,
        "experiment_id": raw_record["experiment_id"],
        "nonce": raw_record["nonce"],
        "backend": raw_record["backend"],
        "backend_class": backend_class or raw_record.get("backend_class"),
        "shots": raw_record["shots"],
        "variant": raw_record["variant"],
        "skeleton_sha256": raw_record["skeleton_sha256"],
        "created_at": raw_record["created_at"],
        "raw_record_sha256": raw_record["record_sha256"],
        "visible_layout": VISIBLE_LAYOUT,
        "visible_counts": marginalize_visible(raw_record["counts"]),
    })


def audit_section(raw_record, fault, salt):
    coin = {"0": 0, "1": 0}
    for k, v in raw_record["counts"].items():
        coin[k[0]] += v
    return {"AUDIT_ONLY": True, "coin_marginal": coin, "fault": ir.validate_fault(fault),
            "fault_commitment": raw_record["fault_commitment"], "salt": salt}


def verify_view(view):
    body = {k: v for k, v in view.items() if k != "view_sha256"}
    return {"visible_counts_sha256": ir.sha256(view["visible_counts"]) == view["visible_counts_sha256"],
            "view_sha256": ir.sha256(body) == view["view_sha256"]}
