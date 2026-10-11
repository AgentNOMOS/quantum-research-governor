"""QRG-R2 JS bridge API. Called once per Qollab Run from main.js:

    import * as qrgApi from 'qrg.js_api';
    const text = await qrgApi.run_experiment.callPromising(backend);

Exactly ONE backend job happens inside (via qrg.qollab_app.run, the R1 flow,
unchanged). Everything else in the envelope — circuit layout, detection table,
counterfactual preflights and labelled local evidence mutations — is computed
deterministically WITHOUT any backend call. The canonical evidence text is
produced here once and must be displayed/exported verbatim by the UI.
"""
from __future__ import annotations

import copy
import hashlib
import json
import traceback

from . import blinding, governor, ir, qollab_app, runner, witness_sim
from .policy import make_policy_r1

ENVELOPE_SCHEMA = "qrg.r2.envelope.v1"


def _canon_text(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------ circuit layout
def _segments(variant, fault):
    seg = [("encode", o) for o in ir.encode_ops()]
    seg += [("fault", o) for o in ir.fault_ops(fault)]
    ex = ir.extract_ops(variant)
    seg += [("check_zzzz", o) for o in ex[:4]] + [("check_xxxx", o) for o in ex[4:]]
    seg += [("measure", ("measure", q)) for q in range(ir.N_QUBITS)]
    return seg


def circuit_layout(variant, fault):
    """ASAP layering of the executed circuit for the UI (same ops as the job)."""
    busy = [0] * ir.N_QUBITS
    out = []
    measure_layer = None
    for segment, op in _segments(variant, fault):
        name = op[0]
        if name == "ry":
            qs, label = [op[2]], f"RY({op[1]:.4f})"
        elif name in ("cx", "cy", "cz"):
            qs, label = [op[1], op[2]], name.upper()
        else:
            qs, label = [op[1]], name.upper() if name != "measure" else "M"
        lo, hi = min(qs), max(qs)
        span = range(lo, hi + 1) if len(qs) == 2 else qs
        layer = max(busy[q] for q in span)
        if name == "measure":
            if measure_layer is None:
                measure_layer = max(busy)  # all measurements share one final column
            layer = measure_layer
        for q in span:
            busy[q] = layer + 1
        out.append({"gate": name, "qubits": qs, "label": label, "layer": layer, "segment": segment})
    return out


def detection_table():
    """Exact syndrome predictions from the independent simulator (no backend)."""
    rows = []
    for pat, note in [("XIII", "bit flip on one data qubit"), ("ZIII", "phase flip on one data qubit"),
                      ("YIII", "bit + phase flip"), ("XXII", "logical X on logical qubit 1"),
                      ("ZIZI", "logical Z on logical qubit 1 (acts trivially on |00>_L)")]:
        f = {"pattern": pat}
        sz = witness_sim.event_probability("full", f, "SZ")
        sx = witness_sim.event_probability("full", f, "SX")
        sx_z = witness_sim.event_probability("z_only", f, "SX")
        sz_z = witness_sim.event_probability("z_only", f, "SZ")
        rows.append({"pauli": pat, "note": note, "sZ": round(sz, 12), "sX": round(sx, 12),
                     "detected_full": bool(round(sz) or round(sx)),
                     "detected_zzzz_only": bool(round(sz_z) or round(sx_z)),
                     "same_syndrome_on_every_qubit": pat.count("I") == 3})
    return rows


# ------------------------------------------------------------------ demonstrations
def _verifier_decide(bundle_copy, custody, replay):
    from verifier.verify_qrg import decide
    try:
        r = decide(bundle_copy, custody, replay)
        return {"verdict": r["verdict"], "reason_code": r["reason_code"]}
    except Exception as exc:  # malformed mutation the replica cannot parse
        return {"verdict": "FREEZE", "reason_code": f"VERIFIER_REFUSED_INPUT:{type(exc).__name__}"}


def _blinding_scan(view):
    return [k for k in view if any(f in k.lower() for f in ("fault", "coin", "salt", "audit", "pattern"))]


def build_demonstrations(bundle):
    """Deterministic, zero-job demonstrations. NEVER mutates `bundle`."""
    policy = make_policy_r1()
    prop, view, dec = bundle["proposal"], bundle["governor_view"], bundle["governor_decision"]
    now, replay = dec["decided_at"], bundle["replay"]
    demos = []

    def pre(did, label, why, **changes):
        p = copy.deepcopy(prop)
        p.update(changes)
        r = governor.preflight(p, policy)
        demos.append({"id": did, "kind": "LOCAL_PREFLIGHT", "label": label, "explanation": why,
                      "executed_on_backend": False, "changed": changes,
                      "governor": {"verdict": r["decision"], "reason_code": r["reason_code"]},
                      "verifier": None})

    def on_live(did, label, why, kind, *, claim=None, mutate_view=None, custody="in_process",
                decided_at=None, mutation=""):
        p = copy.deepcopy(prop)
        if claim:
            p["claim"] = claim
        v = copy.deepcopy(view)
        if mutate_view:
            v = mutate_view(v)
        t = decided_at or now
        g = governor.evaluate_view(p, v, policy, t, custody=custody, replay=replay)
        b = copy.deepcopy(bundle)
        b["proposal"], b["governor_view"] = p, v
        b["governor_decision"] = dict(b["governor_decision"], decided_at=t)
        ver = _verifier_decide(b, custody, replay)
        scan = _blinding_scan(v)
        if scan:
            ver = {"verdict": "FREEZE", "reason_code": "BLINDING_VIOLATION", "fields": scan}
        demos.append({"id": did, "kind": kind, "label": label, "explanation": why,
                      "executed_on_backend": False, "changed": {"claim": claim} if claim else {},
                      "mutation": mutation,
                      "governor": {"verdict": g["verdict"], "reason_code": g["reason_code"],
                                   "statistics": g.get("statistics")},
                      "verifier": ver, "agree": ver["verdict"] == g["verdict"]})

    # ---- REJECT: claim ceiling and policy (preflight, no job)
    pre("reject-no-physical-error", "Claim: no physical error occurred",
        "A clean syndrome cannot exclude syndrome-silent faults such as logical XXII.",
        claim={"type": "NO_PHYSICAL_ERROR", "params": {}})
    pre("reject-error-corrected", "Claim: the code corrected the error",
        "[[4,2,2]] has distance 2: it detects single-qubit faults but cannot correct them.",
        claim={"type": "ERROR_CORRECTED", "params": {}})
    pre("reject-quantum-advantage", "Claim: quantum advantage",
        "Nothing in this experiment measures computational advantage.",
        claim={"type": "QUANTUM_ADVANTAGE", "params": {}})
    pre("reject-ionq-backend", "Request: run on IonQ hardware",
        "Only the built-in ideal simulator is authorized; IonQ/QPU names are refused before any job.",
        backend="ionq_qpu.forte-1", backend_class="qiskit_ionq.ionq_backend.IonQBackend")
    pre("reject-shot-limit", "Request: 50,000 shots", "Exceeds the per-run shot limit (4096).",
        shots=50000)
    # ---- REJECT: a counterfactual claim contradicted by the LIVE evidence
    if bundle["experiment"] == "B_Z_FAULT":
        on_live("reject-contradicted-live", "Claim: detected-syndrome rate <= 1%",
                "The live XXXX syndrome rate is ~0.2; its lower bound exceeds 0.01.",
                "LIVE_EVIDENCE_COUNTERFACTUAL_CLAIM",
                claim={"type": "DETECTED_SYNDROME_RATE_AT_MOST", "params": {"eps": 0.01}})
    else:
        on_live("reject-contradicted-live", "Claim: phase syndromes in >= 5% of shots",
                "The live XXXX syndrome count is 0; its upper bound is far below 0.05.",
                "LIVE_EVIDENCE_COUNTERFACTUAL_CLAIM",
                claim={"type": "PHASE_SYNDROME_RATE_AT_LEAST", "params": {"rho": 0.05}})
    # ---- ESCALATE
    pre("escalate-underpowered", "Request: only 100 shots",
        "Even a perfect outcome could not reach the confidence bound with 100 shots.", shots=100)
    pre("escalate-authorization", "Request: 3000 shots without owner sign-off",
        "Above the 2000-shot auto-approval limit a human owner must authorize.", shots=3000)
    pre("escalate-non-discriminating", "Circuit: ZZZZ check only (no XXXX ancilla)",
        "Without the XXXX check a phase fault and a clean state give identical measurements.",
        variant="z_only")
    on_live("escalate-offline-record", "Same live evidence, submitted offline",
            "Pasted evidence can be checked for consistency, not for origin: never ACCEPTed offline.",
            "OFFLINE_CUSTODY", custody="offline")
    # ---- FREEZE: labelled local mutations of a COPY of the live evidence

    def edit_no_rehash(v):
        k = sorted(v["visible_counts"])[0]
        v["visible_counts"][k] -= 1
        v["visible_counts"]["100000"] = v["visible_counts"].get("100000", 0) + 1
        return v

    def impossible(v):
        k = max(v["visible_counts"], key=v["visible_counts"].get)
        v["visible_counts"][k] -= 3
        v["visible_counts"]["000001"] = 3
        return blinding.seal_view(v)

    def drop(v):
        v["visible_counts"] = {}
        return v

    def leak(v):
        return blinding.seal_view(dict(v, fault_label="hidden-fault-label"))

    on_live("freeze-edited-counts", "Edited counts, hashes not updated",
            "The content hash no longer matches the counts.", "LOCAL_EVIDENCE_MUTATION",
            mutate_view=edit_no_rehash, mutation="moved 1 shot to sX=1, kept old hashes")
    on_live("freeze-impossible-outcome", "Forged counts, hashes recomputed",
            "3 shots with odd data parity but sZ=0 are impossible for any Pauli fault on an ideal backend.",
            "LOCAL_EVIDENCE_MUTATION", mutate_view=impossible,
            mutation="moved 3 shots to outcome 000001 and recomputed hashes")
    on_live("freeze-missing-data", "Measurement data missing", "No counts: nothing can be concluded.",
            "LOCAL_EVIDENCE_MUTATION", mutate_view=drop, mutation="removed all counts")
    on_live("freeze-stale", "Evidence decided 2 hours late",
            "Evidence older than the 10-minute freshness window is frozen.", "LOCAL_EVIDENCE_MUTATION",
            decided_at=_shift(now, 7200), mutation="decision time moved +2 h")
    on_live("freeze-blinding", "Fault label leaked into the governor's view",
            "The governor must never see the injected-fault label or the control-qubit outcome.",
            "LOCAL_EVIDENCE_MUTATION", mutate_view=leak, mutation="added field fault_label and rehashed")
    return demos


def _shift(iso, seconds):
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(iso) + timedelta(seconds=seconds)).isoformat()


# ------------------------------------------------------------------ entry point
def build_envelope(experiment, backend, **run_kwargs):
    env = {"envelope_schema": ENVELOPE_SCHEMA, "experiment": experiment}
    log = []
    calls_before = runner.BACKEND_RUN_CALLS
    try:
        cfg = qollab_app.EXPERIMENTS[experiment]
        bundle = qollab_app.run(experiment, backend, emit=log.append, **run_kwargs)
        text = _canon_text(bundle)
        line = [x for x in log if x.startswith(qollab_app.JSON_PREFIX)]
        assert line and line[0][len(qollab_app.JSON_PREFIX):] == text, "evidence text drift"
        env.update(
            status=bundle["status"], status_message=bundle.get("status_message"),
            title=cfg["title"], hypothesis=cfg["hypothesis"],
            evidence_text=text, evidence_sha256=hashlib.sha256(text.encode("ascii")).hexdigest(),
            evidence_bytes=len(text),
            log=[x for x in log if not x.startswith(qollab_app.JSON_PREFIX)],
            backend_run_calls_this_run=bundle["backend_run_calls_this_run"],
            synthetic_fault=ir.validate_fault(cfg["fault"]),
            circuit={"layout": circuit_layout(cfg["variant"], cfg["fault"]),
                     "metrics": bundle.get("circuit_metrics"), "n_qubits": ir.N_QUBITS,
                     "qubit_roles": ["data q0", "data q1", "data q2", "data q3",
                                     "ZZZZ check (sZ)", "XXXX check (sX)", "fault control (audit)"]},
            detection_table=detection_table())
        if bundle["status"] == "COMPLETED":
            from verifier.verify_qrg import verify_bundle
            env["verifier_report"] = verify_bundle(json.loads(text))  # parses the exact exported text
            env["demonstrations"] = build_demonstrations(bundle)
            env["evidence_sha256_after_demonstrations"] = hashlib.sha256(
                _canon_text(bundle).encode("ascii")).hexdigest()
        else:
            # Preflight refusals etc.: show the local preflight of the configured proposal only.
            env["demonstrations"] = []
        env["backend_run_calls_total_including_demonstrations"] = runner.BACKEND_RUN_CALLS - calls_before
    except Exception as exc:  # never raise across the bridge
        env.update(status="INTERNAL_ERROR", status_message=f"{type(exc).__name__}: {exc}",
                   traceback=traceback.format_exc()[-2000:], log=log,
                   backend_run_calls_total_including_demonstrations=runner.BACKEND_RUN_CALLS - calls_before)
    return env


def run_experiment(backend=None):
    """Bridge entry: returns ONE JSON string (the envelope). Experiment fixed per package."""
    from experiment_config import EXPERIMENT
    return json.dumps(build_envelope(EXPERIMENT, backend), sort_keys=True, separators=(",", ":"))
