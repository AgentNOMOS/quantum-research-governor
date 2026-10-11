"""QRG independent verifier (standalone, Python standard library only).

Does NOT import the qrg package. Recomputes from the raw evidence and the policy
contract, with methods deliberately different from the governor's:
  * confidence bounds via the regularized incomplete beta function (continued
    fraction) instead of summed binomial pmfs
  * claim/circuit compatibility via Pauli (anti)commutation with the stabilizers
    PARSED from the circuit description, instead of statevector simulation
  * physics invariant written from first principles (sZ = data parity; sX = 0 if
    XXXX is not measured)
Stored PASS/FAIL values in the bundle are never trusted; only final verdicts and
numbers are compared.

Usage: python verifier/verify_qrg.py <file-with-QRG_BUNDLE_JSON-line-or-json>
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime

PREFIX = "QRG_BUNDLE_JSON "
VERSION = "qrg-independent-verifier/1"
GHZ_ENCODE = [["h", 0], ["cx", 0, 1], ["cx", 0, 2], ["cx", 0, 3]]
SEV = {"FREEZE": 3, "REJECT": 2, "ESCALATE": 1}


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":")).encode()


def h256(o):
    return hashlib.sha256(canon(o)).hexdigest()


# ------------------------------------------------------------ incomplete beta
def _betacf(a, b, x):
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 10000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c; c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c; c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def beta_ppf(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betai(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp_lower(k, n, alpha):
    return 0.0 if k == 0 else beta_ppf(alpha, k, n - k + 1)


def cp_upper(k, n, alpha):
    return 1.0 if k == n else beta_ppf(1 - alpha, k + 1, n - k)


# ------------------------------------------------------------ circuit parsing
def measured_stabilizers(skel):
    """Infer which stabilizers each ancilla measures from the extraction ops."""
    data = skel["layout"]["data"]
    ops = [tuple(o) for o in skel["extract"]]
    stabs = {}
    for anc, bitname in ((skel["layout"]["sZ"], "sZ"), (skel["layout"]["sX"], "sX")):
        z_targets = sorted(o[1] for o in ops if o[0] == "cx" and o[2] == anc)
        x_targets = sorted(o[2] for o in ops if o[0] == "cx" and o[1] == anc)
        hs = sum(1 for o in ops if o[0] == "h" and o[1] == anc)
        if z_targets == sorted(data) and not x_targets and hs == 0:
            stabs[bitname] = "ZZZZ"
        elif x_targets == sorted(data) and not z_targets and hs == 2:
            stabs[bitname] = "XXXX"
        elif not z_targets and not x_targets:
            stabs[bitname] = None  # ancilla untouched: bit carries no information
        else:
            stabs[bitname] = "UNRECOGNIZED"
    return stabs


def anticommutes(p, s):
    return sum(1 for a, b in zip(p, s) if a != "I" and b != "I" and a != b) % 2 == 1


def event_fires(event, pattern, stabs):
    def bit(name):
        s = stabs.get(name)
        return bool(s) and s != "UNRECOGNIZED" and anticommutes(pattern, s)
    return {"SX": bit("sX"), "SZ": bit("sZ"), "ANY": bit("sX") or bit("sZ")}[event]


def weight1():
    hyps = {"clean": "IIII"}
    for k in range(4):
        for P in "XYZ":
            hyps[f"{P}{k}"] = "".join(P if i == k else "I" for i in range(4))
    return hyps


def separation(spec, stabs):
    hyps = weight1()
    pr = {h: float(event_fires(spec["event"], p, stabs)) for h, p in hyps.items()}
    pa = lambda h: "I" if h == "clean" else h[0]
    if spec.get("competitor") == "all_weight1":
        ch, co = ["clean"], [h for h in hyps if h != "clean"]
    else:
        ch = [h for h in hyps if pa(h) in spec["claim_paulis"]]
        co = [h for h in hyps if pa(h) in spec["competitor_paulis"]]
    if spec["direction"] in ("at_least", "within"):
        return min(pr[h] for h in ch) - max(pr[h] for h in co)
    return min(pr[h] for h in co) - max(pr[h] for h in ch)


# ------------------------------------------------------------ decision replica
def decide(bundle, custody, replay):
    """Independent re-implementation of the policy decision on the governor view."""
    pc = bundle["policy_contract"]
    pol, claims, ceiling = pc["policy"], pc["claims"], pc["ceiling"]
    prop, view, skel = bundle["proposal"], bundle["governor_view"], bundle["skeleton"]
    fails = []  # (severity verdict, code)
    t = prop["claim"]["type"]
    if t in ceiling:
        return {"verdict": "REJECT", "reason_code": "CLAIM_EXCEEDS_CEILING"}
    if t not in claims:
        return {"verdict": "REJECT", "reason_code": "CLAIM_NOT_IN_VOCABULARY"}
    spec = claims[t]
    names = spec.get("params") or [spec["param"]]
    vals = {}
    for nm in names:
        v = (prop["claim"].get("params") or {}).get(nm)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v < 1:
            return {"verdict": "REJECT", "reason_code": "MALFORMED_CLAIM"}
        vals[nm] = float(v)
    ident = f"{prop['backend']}|{prop.get('backend_class')}".lower()
    if any(s in ident for s in pol.get("denied_backend_substrings", [])) or not (
            prop["backend"] in pol["permitted_backends"]
            or prop.get("backend_class") in pol.get("permitted_backend_classes", [])):
        fails.append(("REJECT", "UNAUTHORIZED_BACKEND"))
    if prop["variant"] not in pol["permitted_variants"]:
        fails.append(("REJECT", "UNAUTHORIZED_CIRCUIT"))
    n = prop["shots"]
    if not (isinstance(n, int) and 1 <= n <= pol["max_shots_per_run"]):
        fails.append(("REJECT", "SHOT_LIMIT_EXCEEDED"))
    else:
        if n > pol["budget_units"]:
            fails.append(("REJECT", "BUDGET_EXCEEDED"))
        if n > pol["auto_approve_shots"] and prop.get("owner_authorization") != \
                f"OWNER-APPROVED:{prop['experiment_id']}:{prop['nonce']}":
            fails.append(("ESCALATE", "HUMAN_AUTHORIZATION_REQUIRED"))
    stabs = measured_stabilizers(skel)
    sep = separation(spec, stabs)
    if sep < pol["min_event_separation"] - 1e-9:
        fails.append(("ESCALATE", "NON_DISCRIMINATING"))
    vc = view.get("visible_counts") or {}
    if not vc:
        fails.append(("FREEZE", "MISSING_EVIDENCE"))
        return _pick(fails, None, stabs, sep)
    body = {k: v for k, v in view.items() if k != "view_sha256"}
    if h256(vc) != view.get("visible_counts_sha256") or h256(body) != view.get("view_sha256"):
        fails.append(("FREEZE", "DIGEST_MISMATCH"))
    if not all(len(k) == 6 and set(k) <= {"0", "1"} and isinstance(v, int) and v > 0 for k, v in vc.items()):
        fails.append(("FREEZE", "MALFORMED_COUNTS"))
        return _pick(fails, None, stabs, sep)
    total = sum(vc.values())
    if not total == view["shots"] == n:
        fails.append(("FREEZE", "SHOT_COUNT_MISMATCH"))
    if (view["experiment_id"], view["nonce"], view["backend"]) != (prop["experiment_id"], prop["nonce"], prop["backend"]):
        fails.append(("FREEZE", "PROVENANCE_MISMATCH"))
    try:
        age = (datetime.fromisoformat(bundle["governor_decision"]["decided_at"])
               - datetime.fromisoformat(view["created_at"])).total_seconds()
        if not 0 <= age <= pol["max_evidence_age_s"]:
            fails.append(("FREEZE", "STALE_EVIDENCE"))
    except (KeyError, TypeError, ValueError):
        fails.append(("FREEZE", "STALE_EVIDENCE"))
    if h256(skel) != view["skeleton_sha256"] or skel["encode"] != GHZ_ENCODE:
        fails.append(("FREEZE", "SKELETON_MISMATCH"))
    bad = 0
    for key, v in vc.items():
        sx, sz, data = int(key[0]), int(key[1]), [int(c) for c in key[2:]]
        if sz != sum(data) % 2 or (stabs.get("sX") is None and sx != 0):
            bad += v
    if bad / total > pol["max_out_of_model_fraction"].get(view["backend"], 0.0):
        fails.append(("FREEZE", "PHYSICS_MODEL_VIOLATION"))
    matched = False
    if (replay or {}).get("status") == "PERFORMED":
        matched = replay.get("visible_counts_sha256") == view["visible_counts_sha256"]
        if not matched:
            fails.append(("FREEZE", "REPLAY_MISMATCH"))
    elif view["backend"] in pol["require_replay_backends"]:
        fails.append(("ESCALATE", "REPLAY_REQUIRED"))
    if pol.get("accept_requires_custody_or_replay") and not (custody == "in_process" or matched):
        fails.append(("ESCALATE", "PROVENANCE_UNVERIFIED"))
    # statistics
    ev = spec["event"]
    k = sum(v for key, v in vc.items()
            if (ev == "SX" and key[0] == "1") or (ev == "SZ" and key[1] == "1")
            or (ev == "ANY" and (key[0] == "1" or key[1] == "1")))
    a = pol["alpha"]
    lo, hi = cp_lower(k, total, a), cp_upper(k, total, a)
    d = spec["direction"]
    if d == "at_most":
        thr = vals[names[0]]
        sv = "ACCEPT" if hi <= thr else "REJECT" if lo > thr else "ESCALATE"
    elif d == "at_least":
        thr = vals[names[0]]
        sv = "ACCEPT" if lo >= thr else "REJECT" if hi < thr else "ESCALATE"
    else:
        sv = ("ACCEPT" if lo >= vals["lo"] and hi <= vals["hi"]
              else "REJECT" if hi < vals["lo"] or lo > vals["hi"] else "ESCALATE")
    st = {"event": ev, "k": k, "n": total, "cp_lower": lo, "cp_upper": hi, "statistical_verdict": sv}
    return _pick(fails, st, stabs, sep, physics_bad=bad)


def _pick(fails, st, stabs, sep, physics_bad=None):
    out = {"measured_stabilizers": stabs, "separation": sep, "statistics": st,
           "physics_out_of_model_shots": physics_bad, "failed": [c for _, c in fails]}
    if fails:
        v, c = max(fails, key=lambda f: SEV[f[0]])
        out.update(verdict=v, reason_code=c)
    else:
        sv = st["statistical_verdict"]
        out.update(verdict=sv, reason_code={"ACCEPT": "SUPPORTED", "REJECT": "CONTRADICTED_BY_EVIDENCE",
                                            "ESCALATE": "INCONCLUSIVE"}[sv])
    return out


# ------------------------------------------------------------ bundle verification
def verify_bundle(bundle):
    mm = []
    if bundle.get("bundle_schema") != "qrg.r1.bundle.v1":
        return {"verifier": VERSION, "status": "INVALID_BUNDLE", "mismatches": ["bundle_schema"],
                "recomputed": {}}
    if bundle.get("status") not in (None, "COMPLETED") or "governor_view" not in bundle:
        return {"verifier": VERSION, "status": "NO_EVIDENCE", "mismatches": [],
                "recomputed": {}, "note": f"run status {bundle.get('status')}: nothing to verify"}
    raw, view, dec = bundle["raw_record"], bundle["governor_view"], bundle["governor_decision"]
    pc = bundle["policy_contract"]
    rec = {}
    # policy contract binding
    rec["policy_sha256"] = h256(pc)
    if rec["policy_sha256"] != dec.get("policy_sha256"):
        mm.append("policy_sha256")
    # raw record integrity
    raw_body = {k: v for k, v in raw.items() if k != "record_sha256"}
    rec["raw_counts_sha256_ok"] = h256(raw["counts"]) == raw["counts_sha256"]
    rec["raw_record_sha256_ok"] = h256(raw_body) == raw["record_sha256"]
    if not (rec["raw_counts_sha256_ok"] and rec["raw_record_sha256_ok"]):
        mm.append("raw_record_hashes")
    rec["raw_total_shots"] = sum(raw["counts"].values())
    # view must be exactly the coin-marginal of the raw counts, bound to the raw record
    marg = {}
    for k, v in raw["counts"].items():
        marg[k[1:]] = marg.get(k[1:], 0) + v
    rec["view_equals_raw_marginal"] = dict(sorted(marg.items())) == view["visible_counts"]
    rec["view_bound_to_raw"] = view.get("raw_record_sha256") == raw["record_sha256"]
    if not (rec["view_equals_raw_marginal"] and rec["view_bound_to_raw"]):
        mm.append("view_derivation")
    forbidden = [k for k in view if any(f in k.lower() for f in ("fault", "coin", "salt", "audit", "pattern"))]
    rec["view_contains_audit_fields"] = forbidden
    if forbidden:
        mm.append("blinding")
    # syndromes and frequencies
    n = sum(view["visible_counts"].values())
    sx = sum(v for k, v in view["visible_counts"].items() if k[0] == "1")
    sz = sum(v for k, v in view["visible_counts"].items() if k[1] == "1")
    rec["syndromes"] = {"n": n, "sX_k": sx, "sZ_k": sz, "sX_rate": sx / n, "sZ_rate": sz / n}
    # decision replica (in-process custody as reported by the run)
    r = decide(bundle, dec.get("custody"), bundle.get("replay"))
    rec.update(verdict=r["verdict"], reason_code=r["reason_code"], decision_detail=r)
    if (r["verdict"], r["reason_code"]) != (dec["verdict"], dec["reason_code"]):
        mm.append(f"verdict {dec['verdict']}/{dec['reason_code']} != recomputed {r['verdict']}/{r['reason_code']}")
    gs, vs = dec.get("statistics"), r["statistics"]
    if gs and vs:
        for key in ("k", "n"):
            if gs[key] != vs[key]:
                mm.append(f"statistics.{key}")
        for key in ("cp_lower", "cp_upper"):
            if abs(gs[key] - vs[key]) > 1e-8:
                mm.append(f"statistics.{key} {gs[key]} vs {vs[key]}")
    elif bool(gs) != bool(vs) and r["verdict"] in ("ACCEPT", "REJECT", "ESCALATE") and not r["failed"]:
        mm.append("statistics presence")
    gd = dec.get("discriminability") or {}
    if gd and abs(gd.get("separation", -9) - r["separation"]) > 1e-9:
        mm.append("discriminability.separation")
    # offline assessment: what this verifier itself would grant for a pasted record
    off = decide(bundle, "offline", bundle.get("replay"))
    offline = {"verdict_if_submitted_offline": off["verdict"], "reason_code": off["reason_code"],
               "evidence_consistency": "PASS" if not ({"DIGEST_MISMATCH", "SHOT_COUNT_MISMATCH",
                   "PROVENANCE_MISMATCH", "STALE_EVIDENCE", "SKELETON_MISMATCH",
                   "MALFORMED_COUNTS"} & set(off["failed"])) and "view_derivation" not in mm else "FAIL",
               "physical_plausibility": "FAIL" if "PHYSICS_MODEL_VIOLATION" in off["failed"] else
                   "PASS (plausible forgeries also pass)",
               "reproducibility": (bundle.get("replay") or {}).get("status", "UNAVAILABLE"),
               "authenticated_provenance": "NOT_ESTABLISHED (hashes bind content, not origin)"}
    # retrospective audit (never feeds any verdict above)
    aud = bundle.get("audit_only") or {}
    audit = {"USED_FOR_VERDICT": False}
    if aud:
        fault = aud["fault"]
        audit["commitment_opens"] = hashlib.sha256(aud["salt"].encode() + canon(fault)).hexdigest() \
            == raw["fault_commitment"]
        c1 = sum(v for k, v in raw["counts"].items() if k[0] == "1")
        both = sum(v for k, v in raw["counts"].items() if k[0] == k[1])
        audit.update(coin_rate=c1 / rec["raw_total_shots"], coin_equals_sX_fraction=both / rec["raw_total_shots"],
                     declared_fault=fault)
    status = "VERIFIED" if not mm else "MISMATCH"
    return {"verifier": VERSION, "status": status, "mismatches": mm, "recomputed": rec,
            "offline_assessment": offline, "audit_retrospective": audit,
            "stored_pass_values_trusted": False}


def load(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(PREFIX):
            return json.loads(line[len(PREFIX):])
    return json.loads(text)


def main(argv):
    text = open(argv[1], encoding="utf-8").read() if len(argv) > 1 else sys.stdin.read()
    res = verify_bundle(load(text))
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
