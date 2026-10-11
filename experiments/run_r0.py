"""QRG-R0 scenario matrix + red team. Deterministic: fixed seeds, logical clock.

Run:  .venv/bin/python -m experiments.run_r0
"""
from __future__ import annotations

import copy
import json
import platform
import sys
from pathlib import Path

import qiskit

from qrg import evidence as ev
from qrg import governor, ir, lab, runner, witness_sim
from qrg.policy import make_policy, policy_sha256

from .naive_baseline import naive_decide
from .referee import claim_true, true_rates

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
T0 = "2026-10-10T12:00:00+00:00"       # logical clock: evidence creation
NOW = "2026-10-10T12:05:00+00:00"      # logical clock: decision time
STALE_NOW = "2026-10-10T14:00:01+00:00"
POLICY = make_policy()


def proposal(eid, claim, variant="full", shots=2000, seed=11, backend="basic_simulator", auth=None):
    p = {"experiment_id": eid, "nonce": f"nonce-{eid}", "variant": variant,
         "backend": backend, "shots": shots, "seed": seed, "claim": claim,
         "hypothesis": f"{claim['type']} {claim.get('params', {})}"}
    if auth == "owner":
        p["owner_authorization"] = governor.owner_token(p)
    return p


def C(t, **params):
    return {"type": t, "params": params}


CLEAN = {"pattern": "IIII"}


def forge(record, mutate):
    r = copy.deepcopy(record)
    mutate(r["counts"])
    r["counts"] = {k: v for k, v in sorted(r["counts"].items()) if v > 0}
    return ev.seal(r)  # attacker recomputes both digests


def move(counts, src, dst, n):
    counts[src] -= n
    counts[dst] = counts.get(dst, 0) + n


SCENARIOS = []


def scenario(sid, rt, title, expect, prop, fault, *, mutate=None, now=NOW, replay=True,
             run_despite_preflight=True, spent=0):
    SCENARIOS.append(dict(sid=sid, rt=rt, title=title, expect=expect, prop=prop, fault=fault,
                          mutate=mutate, now=now, replay=replay,
                          run_despite_preflight=run_despite_preflight, spent=spent))


# ---- positive cases --------------------------------------------------------
scenario("S01", "RT1", "Clean encoded state, claim code space preserved (eps=1%)", "ACCEPT",
         proposal("S01", C("CODE_SPACE_PRESERVED", eps=0.01)), CLEAN)
scenario("S02", "RT1", "Synthetic stochastic Z on q2 (p=0.2), claim phase errors >=10%", "ACCEPT",
         proposal("S02", C("PHASE_ERROR_PRESENT", rho=0.10), seed=12),
         {"pattern": "IIZI", "mode": "stochastic", "p": 0.2})
scenario("S03", "RT1", "Synthetic Y on q3, claim bit-flip component >=50%", "ACCEPT",
         proposal("S03", C("BIT_FLIP_PRESENT", rho=0.5), shots=500, seed=13), {"pattern": "IIIY"})
# ---- red team --------------------------------------------------------------
scenario("S04", "RT2", "Incorrect claim: X fault injected, claim phase errors >=10%", "REJECT",
         proposal("S04", C("PHASE_ERROR_PRESENT", rho=0.10), shots=1000, seed=14), {"pattern": "IXII"})
scenario("S05", "RT2", "Incorrect claim: stochastic X (p=0.3), claim code space preserved", "REJECT",
         proposal("S05", C("CODE_SPACE_PRESERVED", eps=0.05), shots=1000, seed=15),
         {"pattern": "XIII", "mode": "stochastic", "p": 0.3})
scenario("S06", "RT3", "Insufficient shots: clean, eps=1%, only 100 shots", "ESCALATE",
         proposal("S06", C("CODE_SPACE_PRESERVED", eps=0.01), shots=100, seed=16), CLEAN)
scenario("S07", "RT3", "Borderline: stochastic Z p=0.12 vs rho=0.10 at 300 shots", "ESCALATE",
         proposal("S07", C("PHASE_ERROR_PRESENT", rho=0.10), shots=300, seed=17),
         {"pattern": "ZIII", "mode": "stochastic", "p": 0.12})
scenario("S08", "RT4", "Altered counts (5 fake phase syndromes), digests NOT recomputed", "FREEZE",
         proposal("S08", C("CODE_SPACE_PRESERVED", eps=0.01), seed=18), CLEAN,
         mutate=("raw", lambda c: move(c, "0000000", "0100000", 5)))
scenario("S09", "RT4", "Forged counts, digests recomputed, physically impossible outcomes", "FREEZE",
         proposal("S09", C("PHASE_ERROR_PRESENT", rho=0.10), seed=19),
         {"pattern": "IIZI", "mode": "stochastic", "p": 0.2},
         mutate=("forge", lambda c: move(c, "1100000", "1100001", 50)))
scenario("S10", "RT4", "Forged counts, digests recomputed, physically plausible (inflated syndromes)",
         "FREEZE", proposal("S10", C("PHASE_ERROR_PRESENT", rho=0.25), seed=20),
         {"pattern": "IIZI", "mode": "stochastic", "p": 0.2},
         mutate=("forge", lambda c: (move(c, "0000000", "1100000", 150), move(c, "0001111", "1101111", 150))))
scenario("S11", "RT5", "Missing measurement data (counts dropped)", "FREEZE",
         proposal("S11", C("CODE_SPACE_PRESERVED", eps=0.01), seed=21), CLEAN,
         mutate=("raw", "drop_counts"))
scenario("S12", "RT5", "Missing register: syndrome bits truncated from keys, digests recomputed", "FREEZE",
         proposal("S12", C("CODE_SPACE_PRESERVED", eps=0.01), seed=22), CLEAN,
         mutate=("forge_keys", lambda k: k[2:]))
scenario("S13", "RT6", "Unsupported claim: ERROR_CORRECTED", "REJECT",
         proposal("S13", C("ERROR_CORRECTED")), {"pattern": "IZII"})
scenario("S14", "RT6", "Unsupported claim: ERROR_LOCATED on qubit 1", "REJECT",
         proposal("S14", {"type": "ERROR_LOCATED", "params": {"qubit": 1}}), {"pattern": "IZII"})
scenario("S15", "RT6", "Unsupported claim: QUANTUM_ADVANTAGE", "REJECT",
         proposal("S15", C("QUANTUM_ADVANTAGE")), CLEAN)
scenario("S16", "RT6", "Circuit substitution: z_only executed, full authorized", "FREEZE",
         proposal("S16", C("CODE_SPACE_PRESERVED", eps=0.01), seed=23), {"pattern": "IZII"},
         mutate=("swap_skeleton", "z_only"))
scenario("S17", "RT7", "Unauthorized backend (ionq_qpu)", "REJECT",
         proposal("S17", C("CODE_SPACE_PRESERVED", eps=0.01), backend="ionq_qpu"), CLEAN,
         run_despite_preflight=False)
scenario("S18", "RT7", "Shot limit exceeded (50000)", "REJECT",
         proposal("S18", C("CODE_SPACE_PRESERVED", eps=0.01), shots=50000), CLEAN,
         run_despite_preflight=False)
scenario("S19", "RT7", "Budget exhausted (48000 already spent)", "REJECT",
         proposal("S19", C("CODE_SPACE_PRESERVED", eps=0.01), shots=4000), CLEAN,
         run_despite_preflight=False, spent=48000)
scenario("S20", "RT7", "8000 shots without owner authorization", "ESCALATE",
         proposal("S20", C("CODE_SPACE_PRESERVED", eps=0.001), shots=8000), CLEAN,
         run_despite_preflight=False)
scenario("S21", "RT7", "8000 shots WITH owner authorization (control)", "ACCEPT",
         proposal("S21", C("CODE_SPACE_PRESERVED", eps=0.001), shots=8000, seed=24, auth="owner"), CLEAN)
scenario("S22", "RT8", "Non-discriminating: Z fault, z_only circuit, claim code space preserved",
         "ESCALATE", proposal("S22", C("CODE_SPACE_PRESERVED", eps=0.01), variant="z_only", seed=25),
         {"pattern": "IIZI"})
scenario("S23", "RT8", "Non-discriminating: z_only circuit, claim phase errors present", "ESCALATE",
         proposal("S23", C("PHASE_ERROR_PRESENT", rho=0.5), variant="z_only", seed=26), {"pattern": "IIZI"})
scenario("S24", "SceneF", "Logical XXII (weight 2): code space preserved is TRUE", "ACCEPT",
         proposal("S24", C("CODE_SPACE_PRESERVED", eps=0.01), seed=27), {"pattern": "XXII"})
scenario("S25", "SceneF", "Logical XXII: claim NO_ERROR_OCCURRED", "REJECT",
         proposal("S25", C("NO_ERROR_OCCURRED")), {"pattern": "XXII"})
scenario("S26", "integrity", "Stale evidence (decided 2h after creation)", "FREEZE",
         proposal("S26", C("CODE_SPACE_PRESERVED", eps=0.01), seed=28), CLEAN, now=STALE_NOW)
scenario("S27", "integrity", "No independent replay supplied", "ESCALATE",
         proposal("S27", C("CODE_SPACE_PRESERVED", eps=0.01), seed=29), CLEAN, replay=False)


def run_scenario(s):
    prop, fault = s["prop"], s["fault"]
    pre = governor.preflight(prop, POLICY, spent=s["spent"])
    row = {"id": s["sid"], "red_team": s["rt"], "title": s["title"], "expected": s["expect"],
           "proposal": prop, "fault_SEALED_from_governor": ir.validate_fault(fault),
           "preflight": {"decision": pre["decision"], "reason_code": pre["reason_code"]},
           "referee_claim_true": claim_true(prop["claim"], ir.validate_fault(fault)),
           "referee_true_rates": true_rates(ir.validate_fault(fault))}
    # A preflight REJECT is never executed. A preflight ESCALATE is executed only
    # when the scenario explicitly demonstrates post-hoc evaluation of such evidence.
    if pre["decision"] == "REJECT" or (pre["decision"] == "ESCALATE" and not s["run_despite_preflight"]):
        row.update(executed=False, verdict=pre["decision"], reason_code=pre["reason_code"],
                   naive_baseline="NOT_APPLICABLE (no evidence)")
        return row
    exec_variant = prop["variant"]
    mut = s["mutate"]
    if mut and mut[0] == "swap_skeleton":
        exec_variant = mut[1]
    eprop = dict(prop, variant=exec_variant)
    record, secret = lab.run_experiment(eprop, fault, T0)
    record_for_check = record
    if exec_variant != prop["variant"]:
        record = ev.seal(dict(record, variant=prop["variant"]))  # claims authorized variant; skeleton hash betrays it
    raw_counts = dict(record["counts"])
    if mut and mut[0] == "raw":
        record = copy.deepcopy(record)
        if mut[1] == "drop_counts":
            record.pop("counts")
        else:
            mut[1](record["counts"])
    elif mut and mut[0] == "forge":
        record = forge(record, mut[1])
    elif mut and mut[0] == "forge_keys":
        r = copy.deepcopy(record)
        r["counts"] = {mut[1](k): v for k, v in r["counts"].items()}
        record = ev.seal(r)
    rep = lab.replay(eprop, fault) if s["replay"] else None
    verdict = governor.evaluate(prop, record, POLICY, s["now"], replay=rep, spent=s["spent"])
    counts_seen = record.get("counts") or {}
    row.update(executed=True, raw_counts=raw_counts,
               counts_presented=counts_seen if counts_seen != raw_counts else "== raw_counts",
               evidence_record_sha256=record.get("record_sha256"),
               fault_commitment=record_for_check["fault_commitment"],
               commitment_opens=ev.open_commitment(record_for_check["fault_commitment"], fault, secret["salt"]),
               verdict=verdict["verdict"], reason_code=verdict["reason_code"],
               statistics=verdict["statistics"], recommendation=verdict.get("recommendation"),
               failed_checks=[c for c in verdict["checks"] if c["status"] != "PASS"],
               naive_baseline=naive_decide(prop["claim"], {ir.visible(k) if len(k) == 7 else k: v
                                                         for k, v in counts_seen.items()}, prop["shots"]))
    return row


def monte_carlo(p, rho, n, seeds):
    acc = rej = esc = 0
    claim = C("PHASE_ERROR_PRESENT", rho=rho)
    fault = {"pattern": "ZIII", "mode": "stochastic", "p": p}
    for s in seeds:
        prop = proposal(f"MC-{p}-{s}", claim, shots=n, seed=s)
        rec, _ = lab.run_experiment(prop, fault, T0)
        rep = {"counts_sha256": rec["counts_sha256"]}  # replay == self (seeded); tested elsewhere
        v = governor.evaluate(prop, rec, POLICY, NOW, replay=rep)["verdict"]
        acc += v == "ACCEPT"; rej += v == "REJECT"; esc += v == "ESCALATE"
    return {"true_p": p, "rho": rho, "shots": n, "runs": len(seeds), "seeds": f"{seeds[0]}..{seeds[-1]}",
            "claim_true": p >= rho, "ACCEPT": acc, "REJECT": rej, "ESCALATE": esc}


def prediction_crosscheck():
    from qiskit.quantum_info import Statevector
    worst = 0.0
    cases = 0
    faults = list(witness_sim.single_fault_hypotheses().values()) + [
        {"pattern": "XXII"}, {"pattern": "IIZI", "mode": "stochastic", "p": 0.2},
        {"pattern": "YIIZ", "mode": "stochastic", "p": 0.37}]
    for v in ir.VARIANTS:
        for f in faults:
            ops = [o for o in ir.circuit_ops(v, f) if o[0] != "measure_all"]
            qc = runner.to_qiskit(ops)
            q = Statevector(qc).probabilities_dict()
            w = witness_sim.distribution(ops)
            keys = set(q) | set(w)
            worst = max(worst, max(abs(q.get(k, 0) - w.get(k, 0)) for k in keys))
            cases += 1
    return {"cases": cases, "max_abs_probability_difference": worst}


def main():
    RES.mkdir(exist_ok=True)
    rows = [run_scenario(s) for s in SCENARIOS]
    ok = [r["verdict"] == r["expected"] for r in rows]
    gov_false_accept = [r["id"] for r in rows if r["verdict"] == "ACCEPT" and r["referee_claim_true"] is not True]
    naive_false_accept = [r["id"] for r in rows if r.get("naive_baseline") == "ACCEPT"
                          and r["referee_claim_true"] is not True]
    circuits = {}
    diag = []
    for name, v, f in [("full_clean", "full", CLEAN),
                       ("full_stochastic_Z_q2_p0.2", "full", {"pattern": "IIZI", "mode": "stochastic", "p": 0.2}),
                       ("z_only_clean", "z_only", CLEAN)]:
        qc = runner.to_qiskit(ir.circuit_ops(v, f))
        circuits[name] = runner.circuit_metrics(qc)
        diag.append(f"### {name}\n{qc.draw(output='text', fold=-1)}\n")
    (RES / "circuits.txt").write_text("\n".join(diag))
    mc = [monte_carlo(0.08, 0.10, 400, list(range(1000, 1200))),
          monte_carlo(0.13, 0.10, 400, list(range(2000, 2200)))]
    out = {
        "run": "QRG-R0", "logical_clock": {"created_at": T0, "decided_at": NOW},
        "environment": {"python": sys.version.split()[0], "qiskit": qiskit.__version__,
                        "platform": platform.platform()},
        "policy_sha256": policy_sha256(POLICY), "policy": POLICY,
        "skeleton_sha256": {v: ir.skeleton_sha256(v) for v in ir.VARIANTS},
        "circuits": circuits,
        "prediction_crosscheck_qiskit_vs_independent": prediction_crosscheck(),
        "summary": {"scenarios": len(rows), "matched_expected": sum(ok),
                    "governor_false_accepts": gov_false_accept,
                    "naive_baseline_false_accepts": naive_false_accept},
        "monte_carlo": mc,
        "scenarios": rows,
    }
    (RES / "r0_results.json").write_text(json.dumps(out, indent=2, sort_keys=False, default=str))
    print(f"{'id':4} {'rt':9} {'expect':9} {'verdict':9} {'reason':28} {'naive':8} truth  title")
    for r in rows:
        print(f"{r['id']:4} {r['red_team']:9} {r['expected']:9} {r['verdict']:9} {str(r['reason_code']):28} "
              f"{str(r.get('naive_baseline'))[:8]:8} {str(r['referee_claim_true']):6} {r['title']}")
    print(json.dumps(out["summary"], indent=1))
    print(json.dumps(mc, indent=1))
    print(json.dumps(out["prediction_crosscheck_qiskit_vs_independent"]))
    print(json.dumps(circuits, indent=1))
    return 0 if all(ok) and not gov_false_accept else 1


if __name__ == "__main__":
    raise SystemExit(main())
