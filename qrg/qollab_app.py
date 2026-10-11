"""QRG-R1 Qollab application flow (shared by every package; only the config differs).

One Run = at most ONE backend.run with ONE bare QuantumCircuit, using only the
backend object handed in by the runtime. No fallback simulator, no retries.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from . import blinding, governor, ir, runner, stats
from . import evidence as ev
from .policy import CEILING, CLAIMS, make_policy_r1, policy_sha256

BUNDLE_SCHEMA = "qrg.r1.bundle.v1"
JSON_PREFIX = "QRG_BUNDLE_JSON "

EXPERIMENTS = {
    "A_NO_FAULT": {
        "title": "Package A - clean encoded state |00>_L, no fault",
        "variant": "full", "shots": 2000, "seed": None,
        "fault": {"pattern": "IIII", "mode": "deterministic"},
        "claim": {"type": "DETECTED_SYNDROME_RATE_AT_MOST", "params": {"eps": 0.01}},
        "hypothesis": "With no injected fault, the per-shot nontrivial-syndrome probability is <= 1%.",
    },
    "B_Z_FAULT": {
        "title": "Package B - SYNTHETIC stochastic Z fault on q2, nominal p = 0.2",
        "variant": "full", "shots": 2000, "seed": None,
        "fault": {"pattern": "IIZI", "mode": "stochastic", "p": 0.2},
        "claim": {"type": "PHASE_SYNDROME_RATE_WITHIN", "params": {"lo": 0.15, "hi": 0.25}},
        "hypothesis": ("The XXXX (phase) syndrome rate lies within the predeclared equivalence "
                       "margin [0.15, 0.25] around the nominal synthetic fault probability 0.2."),
        "nominal_p": 0.2,
    },
    "C_SEED_REPLAY_PROBE": {
        "title": "Package C (optional) - seeded replay probe, clean state",
        "variant": "full", "shots": 2000, "seed": 20261010,
        "fault": {"pattern": "IIII", "mode": "deterministic"},
        "claim": {"type": "DETECTED_SYNDROME_RATE_AT_MOST", "params": {"eps": 0.01}},
        "hypothesis": "Seeded replay probe: run twice in two separate Runs and compare digests.",
    },
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _syndrome_table(visible_counts):
    n = sum(visible_counts.values())
    out = {}
    for name, pos in (("sX_XXXX", 0), ("sZ_ZZZZ", 1)):
        k = sum(v for key, v in visible_counts.items() if key[pos] == "1")
        out[name] = {"k": k, "n": n, "rate": k / n,
                     "two_sided_95": [stats.cp_lower(k, n, 0.025), stats.cp_upper(k, n, 0.025)]}
    k = sum(v for key, v in visible_counts.items() if "1" in key[:2])
    out["any_nontrivial"] = {"k": k, "n": n, "rate": k / n}
    par = sum(v for key, v in visible_counts.items() if int(key[1]) != sum(map(int, key[2:])) % 2)
    out["sZ_vs_data_parity_violations"] = par
    return out


def run(experiment, backend, *, cfg=None, now_fn=_now, nonce=None, emit=print):
    cfg = cfg or EXPERIMENTS[experiment]
    policy = make_policy_r1()
    calls_before = runner.BACKEND_RUN_CALLS
    bundle = {"bundle_schema": BUNDLE_SCHEMA, "experiment": experiment, "title": cfg["title"],
              "status": None, "policy_contract": {"policy": policy, "claims": CLAIMS, "ceiling": CEILING},
              "policy_sha256": policy_sha256(policy)}

    def finish(status, message):
        bundle["status"] = status
        bundle["status_message"] = message
        bundle["backend_run_calls_this_run"] = runner.BACKEND_RUN_CALLS - calls_before
        emit(f"QRG STATUS: {status} - {message}")
        emit(f"QRG backend.run calls in this Run: {bundle['backend_run_calls_this_run']}")
        line = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
        emit("QRG: copy the next line in full for offline verification (python verifier/verify_qrg.py)")
        emit(JSON_PREFIX + line)
        return bundle

    emit("=" * 72)
    emit(f"QRG-R1 Quantum Research Governor :: {cfg['title']}")
    emit("Ideal simulator only. Synthetic faults are labelled. Not hardware evidence.")
    emit("=" * 72)
    if backend is None:
        return finish("ERROR_NO_INJECTED_BACKEND",
                      "no Qollab-injected `backend` found; this package never creates a fallback simulator")

    ident = runner.backend_identity(backend)
    seed_probe = runner.probe_seed_option(backend)
    bundle["backend_identity"] = ident
    bundle["seed_probe"] = seed_probe
    emit(f"Backend: name={ident['name']} class={ident['class']}")
    emit(f"seed_simulator advertised: {seed_probe['seed_simulator_advertised']} (static check, no job)")

    proposal = {"experiment_id": f"QRG-R1-{experiment}", "nonce": nonce or secrets.token_hex(8),
                "variant": cfg["variant"], "backend": ident["name"], "backend_class": ident["class"],
                "shots": cfg["shots"], "seed": cfg["seed"], "claim": cfg["claim"],
                "hypothesis": cfg["hypothesis"]}
    bundle["proposal"] = proposal
    bundle["skeleton"] = ir.skeleton(cfg["variant"])
    pre = governor.preflight(proposal, policy)
    bundle["preflight"] = pre
    emit(f"Preflight: {pre['decision']} {pre['reason_code'] or ''}")
    if pre["decision"] != "CLEARED_TO_EXECUTE":
        return finish(f"PREFLIGHT_{pre['decision']}",
                      f"{pre['reason_code']}: no job submitted "
                      + "; ".join(c["detail"] for c in pre["checks"] if c["status"] != "PASS"))
    if cfg["seed"] is not None and not seed_probe["seed_simulator_advertised"]:
        bundle["replay"] = {"status": "UNAVAILABLE", "reason": "backend does not advertise seed_simulator"}
        return finish("SEED_REPLAY_UNAVAILABLE",
                      "deterministic replay UNAVAILABLE on this backend; no job submitted")

    qc = runner.to_qiskit(ir.circuit_ops(cfg["variant"], cfg["fault"]))
    bundle["circuit_metrics"] = runner.circuit_metrics(qc)
    try:
        emit(str(qc.draw(output="text", fold=-1)))
    except Exception as exc:  # drawing is cosmetic
        emit(f"(circuit drawing unavailable: {exc})")
    emit(f"Submitting exactly one bare QuantumCircuit, shots={cfg['shots']}"
         + (f", seed_simulator={cfg['seed']}" if cfg["seed"] is not None else ", no seed"))
    try:
        _, counts = runner.execute(qc, cfg["shots"], cfg["seed"], backend)
    except Exception as exc:
        bundle["job_error"] = f"{type(exc).__name__}: {exc}"
        return finish("JOB_FAILED", f"{bundle['job_error']} (not retried)")
    created_at = now_fn()

    commitment, salt = ev.fault_commitment(cfg["fault"])
    raw = ev.build(proposal, ident["name"], counts, commitment, created_at)
    raw = ev.seal(dict(raw, backend_class=ident["class"]))
    view = blinding.governor_view(raw, ident["class"])
    if cfg["seed"] is not None:
        replay = {"status": "UNAVAILABLE",
                  "reason": "this Run IS a seeded probe; compare visible_counts_sha256 with a second Run"}
    else:
        replay = {"status": "UNAVAILABLE",
                  "reason": "single-job Run without seed; seeded replay is a separately authorized Run (package C)"}
    decided_at = now_fn()
    decision = governor.evaluate_view(proposal, view, policy, decided_at, custody="in_process", replay=replay)
    bundle.update(raw_record=raw, governor_view=view, replay=replay, governor_decision=decision,
                  audit_only=blinding.audit_section(raw, cfg["fault"], salt))

    desc = {"NOT_GOVERNING": True, "syndromes": _syndrome_table(view["visible_counts"])}
    if "nominal_p" in cfg:
        lo, hi = desc["syndromes"]["sX_XXXX"]["two_sided_95"]
        desc["nominal_comparison"] = {
            "nominal_p": cfg["nominal_p"], "observed_sX_rate": desc["syndromes"]["sX_XXXX"]["rate"],
            "two_sided_95": [lo, hi], "nominal_inside_interval": lo <= cfg["nominal_p"] <= hi,
            "note": "consistency with 0.2 is NOT confirmation of p = 0.2; the governed claim is the "
                    "equivalence interval [0.15, 0.25]"}
        zspec, *_ = governor.claim_spec(cfg["claim"])
        desc["zzzz_only_alternative"] = {
            "observed_sZ_rate": desc["syndromes"]["sZ_ZZZZ"]["rate"],
            "z_only_circuit_separation_for_claim": governor.discriminability(zspec, "z_only")["separation"],
            "note": "ZZZZ commutes with Z faults: a ZZZZ-only experiment cannot see this channel "
                    "(computed from the circuit, no extra job)"}
    bundle["descriptive_not_governing"] = desc

    st = decision.get("statistics") or {}
    emit(f"Visible counts (sX sZ d3 d2 d1 d0): {view['visible_counts']}")
    for nm in ("sX_XXXX", "sZ_ZZZZ"):
        s = desc["syndromes"][nm]
        emit(f"  {nm}: {s['k']}/{s['n']} = {s['rate']:.4f}  two-sided 95% [{s['two_sided_95'][0]:.4f}, "
             f"{s['two_sided_95'][1]:.4f}]")
    if st:
        emit(f"Governed claim {proposal['claim']}: k={st['k']} n={st['n']} one-sided 95% bounds "
             f"[{st['cp_lower']:.4f}, {st['cp_upper']:.4f}]  rule: {st['rule']}")
    emit(f"GOVERNOR VERDICT: {decision['verdict']} ({decision['reason_code']})")
    for k, v in decision["assurance"].items():
        emit(f"  assurance.{k}: {v}")
    if "nominal_comparison" in desc:
        nc = desc["nominal_comparison"]
        emit(f"Nominal p=0.2 inside two-sided 95% interval: {nc['nominal_inside_interval']} (descriptive only)")

    try:
        from verifier.verify_qrg import verify_bundle
        vr = verify_bundle(json.loads(json.dumps(bundle)))
        bundle["in_run_independent_verification"] = {
            "status": vr["status"], "mismatches": vr["mismatches"],
            "recomputed_verdict": vr["recomputed"].get("verdict"),
            "offline_assessment": vr.get("offline_assessment")}
        emit(f"INDEPENDENT VERIFIER (in-run): {vr['status']} {vr['mismatches'] or ''}")
    except Exception as exc:
        bundle["in_run_independent_verification"] = {"status": "VERIFIER_ERROR", "error": repr(exc)}
        emit(f"INDEPENDENT VERIFIER (in-run): VERIFIER_ERROR {exc!r}")
    return finish("COMPLETED", f"verdict {decision['verdict']} ({decision['reason_code']})")
