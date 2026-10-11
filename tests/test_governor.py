import copy

import pytest

from qrg import evidence as ev
from qrg import governor, ir, lab
from qrg.policy import make_policy
from experiments.referee import claim_true

P = make_policy()
T0, NOW = "2026-10-10T12:00:00+00:00", "2026-10-10T12:05:00+00:00"


def prop(claim, **kw):
    p = {"experiment_id": "T", "nonce": "n", "variant": "full", "backend": "basic_simulator",
         "shots": 1000, "seed": 5, "claim": claim}
    p.update(kw)
    return p


def synth(p, counts):
    """Evidence from hand-written counts (no execution), sealed honestly."""
    return ev.build(p, "basic_simulator", counts, "c" * 64, T0)


def rep(record):
    return {"counts_sha256": record["counts_sha256"]}


CS = {"type": "CODE_SPACE_PRESERVED", "params": {"eps": 0.01}}
PH = {"type": "PHASE_ERROR_PRESENT", "params": {"rho": 0.1}}


def test_accept_clean():
    p = prop(CS)
    r = synth(p, {"0000000": 500, "0001111": 500})
    v = governor.evaluate(p, r, P, NOW, replay=rep(r))
    assert v["verdict"] == "ACCEPT" and v["statistics"]["k"] == 0


def test_reject_contradicted():
    p = prop(PH)
    r = synth(p, {"0010001": 500, "0011110": 500})  # X0 signature, no sX
    assert governor.evaluate(p, r, P, NOW, replay=rep(r))["verdict"] == "REJECT"


def test_escalate_inconclusive_small_sample():
    p = prop(CS, shots=100)
    r = synth(p, {"0000000": 50, "0001111": 50})
    v = governor.evaluate(p, r, P, NOW, replay=rep(r))
    assert v["verdict"] == "ESCALATE" and v["reason_code"] == "INCONCLUSIVE"
    assert governor.preflight(p, P)["reason_code"] == "UNDERPOWERED"


def test_freeze_on_tamper_without_rehash():
    p = prop(CS)
    r = synth(p, {"0000000": 500, "0001111": 500})
    t = copy.deepcopy(r)
    t["counts"]["0000000"] -= 1
    t["counts"]["1100000"] = 1
    assert governor.evaluate(p, t, P, NOW, replay=rep(r))["reason_code"] == "DIGEST_MISMATCH"


def test_freeze_on_physics_violation_even_if_rehashed():
    p = prop(CS)
    r = synth(p, {"0000000": 499, "0000001": 1, "0001111": 500})  # odd data parity, sZ=0
    v = governor.evaluate(p, r, P, NOW, replay=rep(r))
    assert v["reason_code"] == "PHYSICS_MODEL_VIOLATION"


def test_freeze_on_replay_mismatch():
    p = prop(CS)
    r = synth(p, {"0000000": 500, "0001111": 500})
    v = governor.evaluate(p, r, P, NOW, replay={"counts_sha256": "0" * 64})
    assert v["reason_code"] == "REPLAY_MISMATCH"


@pytest.mark.parametrize("mut,code", [
    (lambda r: r.pop("counts"), "MISSING_EVIDENCE"),
    (lambda r: r.update(counts={}), "MISSING_EVIDENCE"),
    (lambda r: r.update(nonce="other"), "PROVENANCE_MISMATCH"),
    (lambda r: r.update(created_at="2026-10-10T09:00:00+00:00"), "STALE_EVIDENCE"),
    (lambda r: r.update(created_at="2026-10-10T13:00:00+00:00"), "STALE_EVIDENCE"),
    (lambda r: r.update(skeleton_sha256=ir.skeleton_sha256("z_only")), "SKELETON_MISMATCH"),
    (lambda r: r.update(counts={"000000": 1000}), "MALFORMED_COUNTS"),
    (lambda r: r.update(counts={"0000000": 900}), "SHOT_COUNT_MISMATCH"),
])
def test_freeze_cases(mut, code):
    p = prop(CS)
    r = synth(p, {"0000000": 500, "0001111": 500})
    mut(r)
    if "counts" in r and r["counts"]:
        r = ev.seal(r)  # attacker rehashes; deeper checks must still fire
    v = governor.evaluate(p, r, P, NOW, replay=rep(r) if "counts_sha256" in r else None)
    assert v["verdict"] == "FREEZE" and v["reason_code"] == code


@pytest.mark.parametrize("t", ["ERROR_CORRECTED", "ERROR_LOCATED", "NO_ERROR_OCCURRED",
                               "QUANTUM_ADVANTAGE", "HARDWARE_FIDELITY", "FAULT_TOLERANT",
                               "LOGICAL_STATE_INTACT"])
def test_ceiling_claims_rejected_before_execution(t):
    p = prop({"type": t, "params": {}})
    assert governor.preflight(p, P)["reason_code"] == "CLAIM_EXCEEDS_CEILING"


@pytest.mark.parametrize("claim", [{"type": "MAGIC", "params": {}},
                                   {"type": "PHASE_ERROR_PRESENT", "params": {"rho": 1.5}},
                                   {"type": "PHASE_ERROR_PRESENT", "params": {}}])
def test_vocabulary_and_param_validation(claim):
    assert governor.preflight(prop(claim), P)["decision"] == "REJECT"


def test_authorization_and_budget():
    assert governor.preflight(prop(CS, backend="ionq_qpu"), P)["reason_code"] == "UNAUTHORIZED_BACKEND"
    assert governor.preflight(prop(CS, shots=50000), P)["reason_code"] == "SHOT_LIMIT_EXCEEDED"
    assert governor.preflight(prop(CS, shots=4000), P, spent=47000)["reason_code"] == "BUDGET_EXCEEDED"
    p = prop(CS, shots=8000)
    assert governor.preflight(p, P)["reason_code"] == "HUMAN_AUTHORIZATION_REQUIRED"
    p["owner_authorization"] = governor.owner_token(p)
    assert governor.preflight(p, P)["decision"] == "CLEARED_TO_EXECUTE"
    p["owner_authorization"] = "OWNER-APPROVED:other:n"
    assert governor.preflight(p, P)["reason_code"] == "HUMAN_AUTHORIZATION_REQUIRED"


def test_non_discriminating_variant_escalates_and_recommends_full():
    p = prop(CS, variant="z_only")
    pre = governor.preflight(p, P)
    assert pre["reason_code"] == "NON_DISCRIMINATING"
    r = synth(p, {"0000000": 500, "0001111": 500})
    r = ev.seal(dict(r, skeleton_sha256=ir.skeleton_sha256("z_only")))
    v = governor.evaluate(p, r, P, NOW, replay=rep(r))
    assert v["verdict"] == "ESCALATE" and "full" in v["recommendation"]


def test_precedence_freeze_over_reject():
    p = prop(PH, backend="ionq_qpu")
    r = synth(dict(p, backend="basic_simulator"), {"0000000": 1000})
    r["counts"]["0000000"] = 3  # tamper, no rehash
    assert governor.evaluate(p, r, P, NOW)["verdict"] == "FREEZE"


def test_deterministic_output():
    p = prop(CS)
    r = synth(p, {"0000000": 500, "0001111": 500})
    a = governor.evaluate(p, r, P, NOW, replay=rep(r))
    b = governor.evaluate(copy.deepcopy(p), copy.deepcopy(r), P, NOW, replay=rep(r))
    assert ir.sha256(a) == ir.sha256(b)


def test_no_false_accept_over_executed_grid():
    """Real BasicSimulator runs: every weight-1 fault + logical XXII, both
    variants, three claims, two sample sizes. ACCEPT must imply referee-true."""
    faults = [{"pattern": "IIII"}, {"pattern": "XXII"}] + [
        {"pattern": "".join(P if i == k else "I" for i in range(4))} for k in range(4) for P in "XYZ"]
    claims = [CS, PH, {"type": "BIT_FLIP_PRESENT", "params": {"rho": 0.5}}]
    accepts = 0
    for v in ("full", "z_only"):
        for f in faults:
            for shots in (20, 400):
                base = prop(CS, variant=v, shots=shots, seed=99)
                rec, _ = lab.run_experiment(base, f, T0)
                for c in claims:
                    p = dict(base, claim=c)
                    verdict = governor.evaluate(p, rec, P, NOW, replay=rep(rec))["verdict"]
                    if verdict == "ACCEPT":
                        accepts += 1
                        assert claim_true(c, ir.validate_fault(f)), (v, f, shots, c)
                    if v == "z_only" and c is not claims[2]:
                        assert verdict == "ESCALATE"
    assert accepts > 0
