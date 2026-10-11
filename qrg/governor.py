"""Deterministic research governor: proposal + evidence + policy -> verdict.

Verdicts: ACCEPT / REJECT / ESCALATE / FREEZE (precedence FREEZE > REJECT >
ESCALATE > ACCEPT among structural checks; statistics decide only when every
structural check passes). No clock reads, no randomness, no network.

Two entry points share one core:
  evaluate(...)      R0 path: raw 7-bit record (coin bit masked internally)
  evaluate_view(...) R1 path: blinded governor view (6-bit keys, no audit data)
"""
from __future__ import annotations

from datetime import datetime

from . import blinding
from . import evidence as ev
from . import ir, stats, witness_sim
from .policy import CEILING, CLAIMS, policy_sha256

SEVERITY = {"FREEZE": 3, "REJECT": 2, "ESCALATE": 1, "ACCEPT": 0}
VISIBLE_WIDTH = ir.N_QUBITS - 1


def owner_token(proposal):
    """Demo-only authorization token (NOT cryptographic; no keys in R0/R1)."""
    return f"OWNER-APPROVED:{proposal['experiment_id']}:{proposal['nonce']}"


# Checks whose detail text is a neutral measurement (shown on PASS too). For all other
# checks the detail describes the failure and is shown only when the check fails.
NEUTRAL_DETAIL = {"backend_permitted", "variant_permitted", "shots_within_limit",
                  "claim_discriminable_by_circuit", "hash_integrity", "shots_reconcile",
                  "freshness", "physics_model_consistency"}


def _check(checks, name, ok, verdict_if_fail, code, detail=""):
    checks.append({"check": name, "status": "PASS" if ok else verdict_if_fail,
                   "code": None if ok else code,
                   "detail": detail if (not ok or name in NEUTRAL_DETAIL) else ""})
    return ok


def claim_spec(claim):
    t = (claim or {}).get("type")
    if t in CEILING:
        return None, "REJECT", "CLAIM_EXCEEDS_CEILING", CEILING[t]
    if t not in CLAIMS:
        return None, "REJECT", "CLAIM_NOT_IN_VOCABULARY", f"claim type {t!r} not admissible"
    spec = CLAIMS[t]
    names = spec.get("params") or [spec["param"]]
    params = claim.get("params") or {}
    vals = {}
    for nm in names:
        v = params.get(nm)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v < 1:
            return None, "REJECT", "MALFORMED_CLAIM", f"{nm} must be in (0,1)"
        vals[nm] = float(v)
    if spec["direction"] == "within" and not vals["lo"] < vals["hi"]:
        return None, "REJECT", "MALFORMED_CLAIM", "need lo < hi"
    out = dict(spec, type=t, values=vals)
    out["threshold"] = vals[names[0]] if spec["direction"] != "within" else None
    return out, None, None, ""


def discriminability(spec, variant):
    """Separation of the claim's syndrome event between the claim's hypotheses
    and the competing hypotheses, computed EXACTLY from the circuit by the
    independent simulator. 1.0 means the event rate equals the fault-class rate."""
    hyps = witness_sim.single_fault_hypotheses()
    probs = {h: round(witness_sim.event_probability(variant, f, spec["event"]), 12)
             for h, f in hyps.items()}

    def pauli_of(h):
        return "I" if h == "clean" else h[0]

    if spec.get("competitor") == "all_weight1":
        claim_h = ["clean"]
        comp_h = [h for h in hyps if h != "clean"]
    else:
        claim_h = [h for h in hyps if pauli_of(h) in spec["claim_paulis"]]
        comp_h = [h for h in hyps if pauli_of(h) in spec["competitor_paulis"]]
    if spec["direction"] in ("at_least", "within"):
        sep = min(probs[h] for h in claim_h) - max(probs[h] for h in comp_h)
        confusable = sorted({c for c in comp_h for h in claim_h if probs[c] >= probs[h]})
    else:
        sep = min(probs[h] for h in comp_h) - max(probs[h] for h in claim_h)
        confusable = sorted({c for c in comp_h for h in claim_h if probs[c] <= probs[h]})
    return {"event": spec["event"], "separation": sep, "claim_hypotheses": claim_h,
            "competitors_confusable_with_claim": confusable, "event_probabilities": probs}


def backend_permitted(proposal, policy):
    b, bc = proposal.get("backend"), proposal.get("backend_class")
    ident = f"{b}|{bc}".lower()
    denied = [s for s in policy.get("denied_backend_substrings", []) if s in ident]
    ok = not denied and (b in policy["permitted_backends"]
                         or bc in policy.get("permitted_backend_classes", []))
    return ok, f"backend {b!r} class {bc!r}" + (f" denied by {denied}" if denied else "")


def _structural_static(proposal, policy, checks, spent=0):
    claim = proposal.get("claim")
    spec, v, code, detail = claim_spec(claim)
    if not _check(checks, "claim_admissible", spec is not None, v, code, detail):
        return None
    ok, detail = backend_permitted(proposal, policy)
    _check(checks, "backend_permitted", ok, "REJECT", "UNAUTHORIZED_BACKEND", detail)
    _check(checks, "variant_permitted", proposal.get("variant") in policy["permitted_variants"],
           "REJECT", "UNAUTHORIZED_CIRCUIT", f"variant {proposal.get('variant')!r}")
    shots = proposal.get("shots")
    ok = isinstance(shots, int) and not isinstance(shots, bool) and 1 <= shots <= policy["max_shots_per_run"]
    _check(checks, "shots_within_limit", ok, "REJECT", "SHOT_LIMIT_EXCEEDED",
           f"shots={shots} max={policy['max_shots_per_run']}")
    if ok:
        _check(checks, "budget_available", spent + shots <= policy["budget_units"], "REJECT",
               "BUDGET_EXCEEDED", f"spent={spent} + {shots} > {policy['budget_units']}")
        needs = shots > policy["auto_approve_shots"]
        _check(checks, "owner_authorization",
               not needs or proposal.get("owner_authorization") == owner_token(proposal),
               "ESCALATE", "HUMAN_AUTHORIZATION_REQUIRED",
               f"shots {shots} > auto-approve {policy['auto_approve_shots']}")
    if proposal.get("variant") in policy["permitted_variants"]:
        d = discriminability(spec, proposal["variant"])
        better = [v for v in policy["permitted_variants"]
                  if discriminability(spec, v)["separation"] >= policy["min_event_separation"] - 1e-9]
        _check(checks, "claim_discriminable_by_circuit",
               d["separation"] >= policy["min_event_separation"] - 1e-9, "ESCALATE",
               "NON_DISCRIMINATING",
               f"event {d['event']} separation={d['separation']:.3f}; confusable with "
               f"{d['competitors_confusable_with_claim']}; discriminating variants: {better}")
        spec["discriminability"] = d
        spec["discriminating_variants"] = better
    return spec


def _verdict(checks):
    return max((c for c in checks if c["status"] in SEVERITY and c["status"] != "ACCEPT"),
               key=lambda c: SEVERITY[c["status"]], default=None)


def required_shots(spec, alpha):
    if spec["direction"] == "within":
        return stats.min_shots_within(spec["values"]["lo"], spec["values"]["hi"], alpha)
    return stats.min_shots(spec["direction"], spec["threshold"], alpha)


def preflight(proposal, policy, spent=0):
    """Cheapest-experiment gate: decide whether running the circuit at all is
    justified (authorized, in budget, discriminating, adequately powered).
    Pure function: never touches a backend."""
    checks = []
    spec = _structural_static(proposal, policy, checks, spent)
    if spec is not None and isinstance(proposal.get("shots"), int):
        n_min = required_shots(spec, policy["alpha"])
        _check(checks, "statistical_power", n_min is not None and proposal["shots"] >= n_min,
               "ESCALATE", "UNDERPOWERED",
               f"even the best-case outcome cannot reach ACCEPT below n={n_min} shots")
    worst = _verdict(checks)
    return {
        "stage": "preflight",
        "decision": "CLEARED_TO_EXECUTE" if worst is None else worst["status"],
        "reason_code": None if worst is None else worst["code"],
        "checks": checks,
        "policy_sha256": policy_sha256(policy),
        "proposal_sha256": ir.sha256(proposal),
    }


# ---------------------------------------------------------------- evidence checks
def _counts_checks(counts, width, record_shots, proposal, checks):
    well = isinstance(counts, dict) and all(
        isinstance(k, str) and len(k) == width and set(k) <= {"0", "1"}
        and isinstance(v, int) and not isinstance(v, bool) and v > 0 for k, v in counts.items())
    if not _check(checks, "counts_well_formed", well, "FREEZE", "MALFORMED_COUNTS",
                  f"expected {width}-bit keys and positive int counts"):
        return False
    total = sum(counts.values())
    _check(checks, "shots_reconcile", total == record_shots == proposal["shots"], "FREEZE",
           "SHOT_COUNT_MISMATCH", f"sum={total} record={record_shots} proposal={proposal['shots']}")
    return True


def _meta_checks(proposal, rec, policy, now, checks):
    prov = (rec["experiment_id"] == proposal["experiment_id"] and rec["nonce"] == proposal["nonce"]
            and rec["backend"] == proposal["backend"])
    _check(checks, "provenance_fields", prov, "FREEZE", "PROVENANCE_MISMATCH",
           "experiment_id / nonce / backend must match the proposal")
    try:
        age = (datetime.fromisoformat(now) - datetime.fromisoformat(rec["created_at"])).total_seconds()
        fresh = 0 <= age <= policy["max_evidence_age_s"]
    except (TypeError, ValueError):
        age, fresh = None, False
    _check(checks, "freshness", fresh, "FREEZE", "STALE_EVIDENCE", f"age_s={age}")
    _check(checks, "authorized_circuit",
           rec["skeleton_sha256"] == ir.skeleton_sha256(proposal["variant"]), "FREEZE",
           "SKELETON_MISMATCH", "executed skeleton != authorized skeleton")


def _physics_check(proposal, visible_counts, backend, policy, checks):
    """Physics-model witness on governor-visible bits only: outcomes impossible for
    ANY Pauli fault on an ideal backend. Plausible forgeries are NOT detected."""
    support = witness_sim.pauli_model_support(proposal["variant"])
    total = sum(visible_counts.values())
    bad = sum(v for k, v in visible_counts.items() if k not in support)
    tol = policy["max_out_of_model_fraction"].get(backend, 0.0)
    parity_viol = sum(v for k, v in visible_counts.items()
                      if int(k[1]) != sum(map(int, k[2:])) % 2)
    ok = _check(checks, "physics_model_consistency", bad / total <= tol, "FREEZE",
                "PHYSICS_MODEL_VIOLATION",
                f"{bad}/{total} shots outside Pauli-model support (sZ-vs-data-parity mismatches: {parity_viol})")
    return {"out_of_model_shots": bad, "sZ_parity_violations": parity_viol, "tolerance": tol, "pass": ok}


def _statistics(spec, visible_counts, n, alpha, policy):
    test = witness_sim.EVENTS[spec["event"]]
    k = sum(v for key, v in visible_counts.items() if test(key))
    lo, hi = stats.cp_lower(k, n, alpha), stats.cp_upper(k, n, alpha)
    d = spec["direction"]
    if d == "at_most":
        thr = spec["threshold"]
        verdict = "ACCEPT" if hi <= thr else "REJECT" if lo > thr else "ESCALATE"
        rule = f"ACCEPT if upper<={thr}; REJECT if lower>{thr}; else ESCALATE"
    elif d == "at_least":
        thr = spec["threshold"]
        verdict = "ACCEPT" if lo >= thr else "REJECT" if hi < thr else "ESCALATE"
        rule = f"ACCEPT if lower>={thr}; REJECT if upper<{thr}; else ESCALATE"
    else:
        a, b = spec["values"]["lo"], spec["values"]["hi"]
        verdict = "ACCEPT" if lo >= a and hi <= b else "REJECT" if hi < a or lo > b else "ESCALATE"
        rule = (f"TOST: ACCEPT if lower>={a} and upper<={b}; REJECT if upper<{a} or lower>{b}; "
                "else ESCALATE")
    out = {"event": spec["event"], "k": k, "n": n, "rate": k / n, "alpha": alpha,
           "cp_lower": lo, "cp_upper": hi, "direction": d, "values": spec["values"],
           "rule": rule, "statistical_verdict": verdict,
           "two_sided_95": [stats.cp_lower(k, n, 0.025), stats.cp_upper(k, n, 0.025)]}
    if verdict == "ESCALATE":
        if d == "within":
            out["recommendation"] = "Interval not resolved: collect more shots under a new authorized run."
        else:
            proj = stats.projected_shots(d, spec["threshold"], k / n, alpha, n, policy["max_shots_per_run"])
            out["recommendation"] = (
                "Interval straddles the threshold. "
                + (f"If the observed rate {k / n:.4f} persists, ~{proj} shots would resolve it "
                   "(heuristic projection, needs a new authorized run)." if proj else
                   "Observed rate is too close to the threshold to resolve within the shot limit: "
                   "escalate to a human / revise the threshold."))
    return out


def ceiling_statement(spec, accepted):
    lvl = "one-sided 95%"
    st = {"supported" if accepted else "requested": spec["type"],
          "scope": f"this circuit, this backend, i.i.d. shots, {lvl} confidence",
          "not_established": [
              "absence of physical errors (a zero syndrome rate does not prove it)",
              "absence of syndrome-silent faults, e.g. logical XXII",
              "fault location or correction",
              "physical-hardware fidelity (ideal simulator)",
              "fault tolerance", "any quantum advantage",
              "authenticated origin of the evidence"]}
    if "observable" in spec:
        st["observable_statement"] = spec["observable"].format(**spec["values"])
        st["model_conditional_statement"] = spec["model_conditional"].format(**spec["values"]) + \
            " (holds only if the declared fault model is correct)"
    return st


def _finish(out, checks, spec, sinfo):
    worst = _verdict(checks)
    if sinfo is not None:
        out["statistics"] = dict(sinfo, decisive=worst is None)
    if worst is not None:
        out.update(verdict=worst["status"], reason_code=worst["code"])
        if spec and worst["code"] == "NON_DISCRIMINATING":
            out["recommendation"] = f"Re-design: run variant(s) {spec['discriminating_variants']}"
        return out
    v = sinfo["statistical_verdict"]
    out.update(verdict=v, reason_code={"ACCEPT": "SUPPORTED", "REJECT": "CONTRADICTED_BY_EVIDENCE",
                                       "ESCALATE": "INCONCLUSIVE"}[v],
               claim_ceiling=ceiling_statement(spec, v == "ACCEPT"))
    if "recommendation" in sinfo:
        out["recommendation"] = sinfo["recommendation"]
    return out


def evaluate(proposal, record, policy, now, replay=None, spent=0):
    """R0 path (raw record, coin masked internally). Kept for R0 compatibility."""
    checks = []
    spec = _structural_static(proposal, policy, checks, spent)
    out = {"stage": "evaluate", "policy_sha256": policy_sha256(policy),
           "proposal_sha256": ir.sha256(proposal),
           "evidence_record_sha256": record.get("record_sha256") if isinstance(record, dict) else None,
           "checks": checks, "statistics": None}
    sinfo = None
    if spec:
        if not isinstance(record, dict) or any(k not in record for k in ev.REQUIRED) \
                or not isinstance(record.get("counts"), dict) or not record.get("counts"):
            missing = [k for k in ev.REQUIRED if not isinstance(record, dict) or k not in record]
            _check(checks, "evidence_complete", False, "FREEZE", "MISSING_EVIDENCE",
                   f"missing/empty: {missing or ['counts']}")
        else:
            _check(checks, "evidence_complete", True, None, None)
            _check(checks, "schema", record["schema"] == ev.SCHEMA, "FREEZE", "SCHEMA_MISMATCH")
            h = ev.verify_hashes(record)
            _check(checks, "hash_integrity", all(h.values()), "FREEZE", "DIGEST_MISMATCH", str(h))
            if _counts_checks(record["counts"], ir.N_QUBITS, record["shots"], proposal, checks):
                _meta_checks(proposal, record, policy, now, checks)
                vis = blinding.marginalize_visible(record["counts"])
                _physics_check(proposal, vis, record["backend"], policy, checks)
                if record["backend"] in policy["require_replay_backends"]:
                    if replay is None:
                        _check(checks, "independent_replay", False, "ESCALATE", "REPLAY_REQUIRED",
                               "seeded backend: an independent re-execution digest is required")
                    else:
                        _check(checks, "independent_replay",
                               replay.get("counts_sha256") == ir.sha256(record["counts"]), "FREEZE",
                               "REPLAY_MISMATCH",
                               f"replay {replay.get('counts_sha256', '')[:12]} vs evidence "
                               f"{ir.sha256(record['counts'])[:12]}")
                if _verdict(checks) is None:
                    sinfo = _statistics(spec, vis, proposal["shots"], policy["alpha"], policy)
    out = _finish(out, checks, spec, sinfo)
    if out.get("statistics") is None:
        out["statistics"] = None
    return out


def evaluate_view(proposal, view, policy, now, custody="offline", replay=None, spent=0):
    """R1 path. Consumes ONLY the blinded governor view (6-bit visible keys).

    custody: "in_process" when the caller computed the view from the job result
             object in the same run; anything else is treated as an offline record.
    replay:  None | {"status": "UNAVAILABLE", "reason": ...}
                  | {"status": "PERFORMED", "visible_counts_sha256": ...}
    """
    checks = []
    spec = _structural_static(proposal, policy, checks, spent)
    out = {"stage": "evaluate_view", "decided_at": now, "custody": custody,
           "policy_id": policy["policy_id"], "policy_version": policy["version"],
           "policy_sha256": policy_sha256(policy), "proposal_sha256": ir.sha256(proposal),
           "governor_view_sha256": view.get("view_sha256") if isinstance(view, dict) else None,
           "inputs_used": "governor view only (no fault label, no coin bit, no commitment)",
           "checks": checks, "statistics": None,
           "discriminability": (spec or {}).get("discriminability")}
    assurance = {"evidence_consistency": "NOT_EVALUATED", "physical_plausibility": "NOT_EVALUATED",
                 "reproducibility": "NOT_EVALUATED",
                 "authenticated_provenance": "NOT_ESTABLISHED (no signatures or keys exist; "
                                             "custody=in_process only means the verdict was computed "
                                             "in the same run from the job result object)"}
    sinfo = None
    if spec:
        if not isinstance(view, dict) or any(k not in view for k in blinding.VIEW_FIELDS) \
                or not isinstance(view.get("visible_counts"), dict) or not view.get("visible_counts"):
            missing = [k for k in blinding.VIEW_FIELDS if not isinstance(view, dict) or k not in view]
            _check(checks, "evidence_complete", False, "FREEZE", "MISSING_EVIDENCE",
                   f"missing/empty: {missing or ['visible_counts']}")
        else:
            n0 = len(checks)
            _check(checks, "evidence_complete", True, None, None)
            leaked = [k for k in view if any(f in k.lower() for f in blinding.FORBIDDEN_IN_VIEW)
                      and k not in blinding.VIEW_FIELDS]
            _check(checks, "blinding", view["schema"] == blinding.VIEW_SCHEMA and not leaked,
                   "FREEZE", "BLINDING_VIOLATION", f"unexpected fields {leaked}")
            h = blinding.verify_view(view)
            _check(checks, "hash_integrity", all(h.values()), "FREEZE", "DIGEST_MISMATCH", str(h))
            vis = view["visible_counts"]
            if _counts_checks(vis, VISIBLE_WIDTH, view["shots"], proposal, checks):
                _meta_checks(proposal, view, policy, now, checks)
                assurance["evidence_consistency"] = "PASS" if all(
                    c["status"] == "PASS" for c in checks[n0:]) else "FAIL"
                ph = _physics_check(proposal, vis, view["backend"], policy, checks)
                assurance["physical_plausibility"] = (
                    ("PASS" if ph["pass"] else "FAIL")
                    + " (ideal-model invariant; physically plausible forgeries also pass)")
                rstat = (replay or {}).get("status")
                if rstat == "PERFORMED":
                    match = replay.get("visible_counts_sha256") == view["visible_counts_sha256"]
                    _check(checks, "independent_replay", match, "FREEZE", "REPLAY_MISMATCH")
                    assurance["reproducibility"] = "REPLAY_MATCHED" if match else "REPLAY_MISMATCH"
                else:
                    if view["backend"] in policy["require_replay_backends"]:
                        _check(checks, "independent_replay", False, "ESCALATE", "REPLAY_REQUIRED")
                    assurance["reproducibility"] = "UNAVAILABLE: " + (
                        (replay or {}).get("reason") or "no replay supplied")
                if policy.get("accept_requires_custody_or_replay"):
                    _check(checks, "provenance_gate",
                           custody == "in_process" or assurance["reproducibility"] == "REPLAY_MATCHED",
                           "ESCALATE", "PROVENANCE_UNVERIFIED",
                           "offline record without replay: consistency can be checked, origin cannot")
                if not any(c["status"] in ("FREEZE", "REJECT") for c in checks) and \
                        all(c["code"] != "NON_DISCRIMINATING" for c in checks):
                    sinfo = _statistics(spec, vis, proposal["shots"], policy["alpha"], policy)
    out["assurance"] = assurance
    return _finish(out, checks, spec, sinfo)
