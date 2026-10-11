"""QRG-R1 focused red team: blinding, ceiling, undetectable faults, seed
unavailability, impossible / plausible forgeries, zero-call preflight."""
import copy
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator

from qrg import blinding, governor, ir, qollab_app, runner, stats
from qrg import evidence as ev
from qrg.policy import make_policy_r1
from verifier import verify_qrg

ROOT = Path(__file__).resolve().parent.parent
P1 = make_policy_r1()


class SpyBackend:
    """Behaves like the injected Qollab backend; records calls; fixes the inner
    seed so tests are deterministic WITHOUT the app ever passing a seed."""

    def __init__(self, name="basic_simulator", seed_option=True, fail=False, inner_seed=7):
        self.inner = BasicSimulator()
        self.name = name
        self.calls = []
        self.fail = fail
        self.inner_seed = inner_seed
        self.options = self.inner.options if seed_option else SimpleNamespace(shots=1024)

    def run(self, run_input, **kw):
        self.calls.append((run_input, dict(kw)))
        if self.fail:
            raise RuntimeError("simulated backend failure")
        kw.setdefault("seed_simulator", self.inner_seed)
        return self.inner.run(run_input, **kw)


class IonQLikeBackend(SpyBackend):
    pass


def run_app(exp, backend, cfg=None):
    lines = []
    b = qollab_app.run(exp, backend, cfg=cfg, emit=lines.append)
    line = [x for x in lines if x.startswith(qollab_app.JSON_PREFIX)]
    assert len(line) == 1, "exactly one copyable JSON line"
    assert json.loads(line[0][len(qollab_app.JSON_PREFIX):]) == json.loads(json.dumps(b))
    return b, lines


# ------------------------------------------------------------ package behaviour
@pytest.mark.parametrize("exp,verdict", [("A_NO_FAULT", "ACCEPT"), ("B_Z_FAULT", "ACCEPT")])
def test_package_runs_one_bare_circuit_and_verifies(exp, verdict):
    spy = SpyBackend()
    b, _ = run_app(exp, spy)
    assert b["status"] == "COMPLETED" and b["backend_run_calls_this_run"] == 1
    assert len(spy.calls) == 1 and isinstance(spy.calls[0][0], QuantumCircuit)
    assert "seed_simulator" not in spy.calls[0][1]  # basic experiments never depend on a seed
    assert spy.calls[0][0].num_qubits == 7
    assert b["governor_decision"]["verdict"] == verdict
    assert b["in_run_independent_verification"]["status"] == "VERIFIED"
    assert verify_qrg.verify_bundle(b)["status"] == "VERIFIED"


def test_package_b_phase_channel_visible_only_in_xxxx():
    b, _ = run_app("B_Z_FAULT", SpyBackend(inner_seed=11))
    syn = b["descriptive_not_governing"]["syndromes"]
    assert syn["sZ_ZZZZ"]["k"] == 0 and 0.15 < syn["sX_XXXX"]["rate"] < 0.25
    assert b["descriptive_not_governing"]["zzzz_only_alternative"]["z_only_circuit_separation_for_claim"] == 0
    assert b["governor_decision"]["claim_ceiling"]["observable_statement"].startswith("0.15 <= P(sX=1")


def test_no_injected_backend_no_fallback():
    before = runner.BACKEND_RUN_CALLS
    b, _ = run_app("A_NO_FAULT", None)
    assert b["status"] == "ERROR_NO_INJECTED_BACKEND" and runner.BACKEND_RUN_CALLS == before


def test_job_failure_is_not_retried():
    spy = SpyBackend(fail=True)
    b, _ = run_app("A_NO_FAULT", spy)
    assert b["status"] == "JOB_FAILED" and len(spy.calls) == 1


# ------------------------------------------------------------ zero-call preflight
@pytest.mark.parametrize("backend,code", [
    (SpyBackend(name="ionq_simulator"), "UNAUTHORIZED_BACKEND"),
    (SpyBackend(name="qpu.forte-1"), "UNAUTHORIZED_BACKEND"),
    (IonQLikeBackend(name="basic_simulator"), "UNAUTHORIZED_BACKEND"),   # class name contains IonQ
    (SpyBackend(name="some_other_simulator"), "UNAUTHORIZED_BACKEND"),
])
def test_unauthorized_backend_zero_calls(backend, code):
    b, _ = run_app("A_NO_FAULT", backend)
    assert b["status"] == "PREFLIGHT_REJECT" and b["preflight"]["reason_code"] == code
    assert backend.calls == [] and b["backend_run_calls_this_run"] == 0


@pytest.mark.parametrize("shots,status,code", [(50000, "PREFLIGHT_REJECT", "SHOT_LIMIT_EXCEEDED"),
                                               (3000, "PREFLIGHT_ESCALATE", "HUMAN_AUTHORIZATION_REQUIRED"),
                                               (50, "PREFLIGHT_ESCALATE", "UNDERPOWERED")])
def test_shot_budget_zero_calls(shots, status, code):
    spy = SpyBackend()
    cfg = dict(qollab_app.EXPERIMENTS["A_NO_FAULT"], shots=shots)
    b, _ = run_app("A_NO_FAULT", spy, cfg)
    assert (b["status"], b["preflight"]["reason_code"]) == (status, code) and spy.calls == []


@pytest.mark.parametrize("t", ["PHYSICAL_ERROR_RATE_AT_MOST", "NO_PHYSICAL_ERROR", "LOGICAL_ERROR_RATE_AT_MOST",
                               "FAULT_PROBABILITY_EQUALS", "NO_ERROR_OCCURRED", "ERROR_CORRECTED"])
def test_unsupported_physical_claims_rejected_zero_calls(t):
    spy = SpyBackend()
    cfg = dict(qollab_app.EXPERIMENTS["A_NO_FAULT"], claim={"type": t, "params": {"eps": 0.01}})
    b, _ = run_app("A_NO_FAULT", spy, cfg)
    assert b["preflight"]["reason_code"] == "CLAIM_EXCEEDS_CEILING" and spy.calls == []


# ------------------------------------------------------------ seed policy
def test_seed_unavailable_basic_experiment_still_runs():
    spy = SpyBackend(seed_option=False)
    b, _ = run_app("A_NO_FAULT", spy)
    assert b["seed_probe"]["seed_simulator_advertised"] is False
    assert b["status"] == "COMPLETED" and len(spy.calls) == 1
    assert b["governor_decision"]["assurance"]["reproducibility"].startswith("UNAVAILABLE")


def test_seed_probe_package_refuses_without_seed_support_zero_calls():
    spy = SpyBackend(seed_option=False)
    b, _ = run_app("C_SEED_REPLAY_PROBE", spy)
    assert b["status"] == "SEED_REPLAY_UNAVAILABLE" and spy.calls == []


def test_seed_probe_package_reproducible_on_basic_simulator():
    d = []
    for _ in range(2):
        b, _ = run_app("C_SEED_REPLAY_PROBE", BasicSimulator())
        d.append(b["governor_view"]["visible_counts_sha256"])
    assert d[0] == d[1]


# ------------------------------------------------------------ blinding
def _raw(counts, fault, eid="X"):
    prop = {"experiment_id": eid, "nonce": "n", "variant": "full", "shots": sum(counts.values()), "seed": None}
    c, salt = ev.fault_commitment(fault)
    raw = ev.build(prop, "basic_simulator", counts, c, "2026-10-10T12:00:00+00:00")
    return ev.seal(dict(raw, backend_class=P1["permitted_backend_classes"][0])), salt


def _prop(claim, shots=2000, eid="X"):
    return {"experiment_id": eid, "nonce": "n", "variant": "full", "backend": "basic_simulator",
            "backend_class": P1["permitted_backend_classes"][0], "shots": shots, "seed": None, "claim": claim}


NOW = "2026-10-10T12:01:00+00:00"
PH = {"type": "PHASE_SYNDROME_RATE_WITHIN", "params": {"lo": 0.15, "hi": 0.25}}


def _strip(d):
    d = copy.deepcopy(d)
    d.pop("governor_view_sha256", None)
    return d


def test_governor_decision_invariant_to_coin_and_fault_label():
    # Same visible marginal; coin bit and fault label differ completely.
    r1, _ = _raw({"0100000": 400, "0000000": 800, "0001111": 800}, {"pattern": "IIZI", "mode": "stochastic", "p": 0.2})
    r2, _ = _raw({"1100000": 400, "1000000": 800, "0001111": 800}, {"pattern": "XXXX"})
    v1, v2 = blinding.governor_view(r1), blinding.governor_view(r2)
    assert v1["visible_counts"] == v2["visible_counts"]
    d1 = governor.evaluate_view(_prop(PH), v1, P1, NOW, custody="in_process")
    d2 = governor.evaluate_view(_prop(PH), v2, P1, NOW, custody="in_process")
    assert _strip(d1) == _strip(d2) and d1["verdict"] == "ACCEPT"


def test_view_has_no_audit_fields_and_audit_is_separate():
    r, salt = _raw({"0000000": 1000, "0001111": 1000}, {"pattern": "IIII"})
    v = blinding.governor_view(r)
    blob = json.dumps(v)
    for f in ("pattern", "salt", "coin", "fault_commitment", "IIII"):
        assert f not in blob
    assert all(len(k) == 6 for k in v["visible_counts"])
    a = blinding.audit_section(r, {"pattern": "IIII"}, salt)
    assert a["AUDIT_ONLY"] is True and ev.open_commitment(a["fault_commitment"], a["fault"], salt)


def test_injected_audit_field_in_view_freezes():
    r, _ = _raw({"0000000": 1000, "0001111": 1000}, {"pattern": "IIII"})
    v = blinding.seal_view(dict(blinding.governor_view(r), fault_label="IIZI"))
    d = governor.evaluate_view(_prop(PH), v, P1, NOW, custody="in_process")
    assert (d["verdict"], d["reason_code"]) == ("FREEZE", "BLINDING_VIOLATION")


def test_seven_bit_keys_cannot_reach_governor():
    r, _ = _raw({"0000000": 1000, "0001111": 1000}, {"pattern": "IIII"})
    v = blinding.seal_view(dict(blinding.governor_view(r), visible_counts=r["counts"]))
    assert governor.evaluate_view(_prop(PH), v, P1, NOW, custody="in_process")["reason_code"] == "MALFORMED_COUNTS"


def test_app_passes_only_view_to_governor(monkeypatch):
    seen = {}
    real = governor.evaluate_view

    def capture(proposal, view, *a, **kw):
        seen["args"] = json.dumps([proposal, view, a, kw], default=str)
        return real(proposal, view, *a, **kw)

    monkeypatch.setattr(governor, "evaluate_view", capture)
    run_app("B_Z_FAULT", SpyBackend())
    for f in ('"pattern"', '"salt"', "audit", "fault_commitment", '"p": 0.2'):
        assert f not in seen["args"]


def test_governor_source_never_touches_coin():
    src = inspect.getsource(governor)
    assert "COIN" not in src and "audit_section" not in src and "audit_only" not in src


# ------------------------------------------------------------ undetectable faults
def test_logical_fault_is_syndrome_silent_and_not_overclaimed():
    cfg = dict(qollab_app.EXPERIMENTS["A_NO_FAULT"], fault={"pattern": "XXII", "mode": "deterministic"})
    b, _ = run_app("A_NO_FAULT", SpyBackend(), cfg)
    d = b["governor_decision"]
    assert d["verdict"] == "ACCEPT" and d["statistics"]["k"] == 0  # claim is about syndromes: true
    ne = " ".join(d["claim_ceiling"]["not_established"])
    assert "zero syndrome rate does not prove" in ne and "XXII" in ne
    assert set(b["governor_view"]["visible_counts"]) == {"000011", "001100"}  # logical flip, silent


# ------------------------------------------------------------ forgeries
def test_physically_impossible_record_freezes():
    r, _ = _raw({"0000000": 990, "0000001": 10, "0001111": 1000}, {"pattern": "IIII"})
    d = governor.evaluate_view(_prop({"type": "DETECTED_SYNDROME_RATE_AT_MOST", "params": {"eps": 0.01}}),
                               blinding.governor_view(r), P1, NOW, custody="in_process")
    assert (d["verdict"], d["reason_code"]) == ("FREEZE", "PHYSICS_MODEL_VIOLATION")


def test_plausible_rehashed_forgery_is_never_accepted_offline():
    b, _ = run_app("B_Z_FAULT", SpyBackend())
    f = copy.deepcopy(b)
    raw = f["raw_record"]
    # Forge: move clean shots to the phase-syndrome bin (physically plausible), rehash everything.
    raw["counts"]["0000000"] -= 300
    raw["counts"]["1100000"] = raw["counts"].get("1100000", 0) + 300
    raw = ev.seal(raw)
    f["raw_record"] = raw
    f["governor_view"] = blinding.governor_view(raw)
    vr = verify_qrg.verify_bundle(f)
    # Hashes and physics all pass ...
    assert vr["recomputed"]["raw_record_sha256_ok"] and vr["recomputed"]["view_equals_raw_marginal"]
    assert vr["offline_assessment"]["physical_plausibility"].startswith("PASS")
    # ... yet offline it is never accepted, and provenance is not claimed.
    assert vr["offline_assessment"]["verdict_if_submitted_offline"] != "ACCEPT"
    assert vr["offline_assessment"]["reason_code"] == "PROVENANCE_UNVERIFIED"
    assert vr["offline_assessment"]["authenticated_provenance"].startswith("NOT_ESTABLISHED")
    d = governor.evaluate_view(f["proposal"], f["governor_view"], P1, f["governor_decision"]["decided_at"],
                               custody="offline", replay=f["replay"])
    assert d["verdict"] == "ESCALATE" and d["reason_code"] == "PROVENANCE_UNVERIFIED"
    # The stored in-process verdict no longer matches the forged counts -> verifier flags it.
    assert vr["status"] == "MISMATCH"


def test_naive_view_edit_detected_by_verifier():
    b, _ = run_app("A_NO_FAULT", SpyBackend())
    f = copy.deepcopy(b)
    f["governor_view"]["visible_counts"]["100000"] = 5
    f["governor_view"]["visible_counts"]["000000"] -= 5
    vr = verify_qrg.verify_bundle(f)
    assert vr["status"] == "MISMATCH" and "view_derivation" in vr["mismatches"]


def test_verifier_ignores_stored_pass_values():
    b, _ = run_app("A_NO_FAULT", SpyBackend())
    f = copy.deepcopy(b)
    f["governor_decision"]["verdict"] = "REJECT"
    for c in f["governor_decision"]["checks"]:
        c["status"] = "PASS"
    assert verify_qrg.verify_bundle(f)["status"] == "MISMATCH"


# ------------------------------------------------------------ verifier independence
def test_verifier_does_not_import_qrg():
    code = ("import sys; import verifier.verify_qrg; "
            "assert not any(m == 'qrg' or m.startswith('qrg.') or m.startswith('qiskit') for m in sys.modules)")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


@pytest.mark.parametrize("n", [20, 400, 2000])
def test_verifier_bounds_agree_with_governor(n):
    for k in sorted({0, 1, n // 10, n // 5, n // 2, n - 1, n}):
        assert abs(verify_qrg.cp_lower(k, n, 0.05) - stats.cp_lower(k, n, 0.05)) < 1e-9
        assert abs(verify_qrg.cp_upper(k, n, 0.05) - stats.cp_upper(k, n, 0.05)) < 1e-9


def test_verifier_parses_measured_stabilizers_from_circuit():
    assert verify_qrg.measured_stabilizers(ir.skeleton("full")) == {"sZ": "ZZZZ", "sX": "XXXX"}
    assert verify_qrg.measured_stabilizers(ir.skeleton("z_only")) == {"sZ": "ZZZZ", "sX": None}


def test_verifier_cli_on_console_line(tmp_path):
    lines = []
    qollab_app.run("B_Z_FAULT", SpyBackend(), emit=lines.append)
    p = tmp_path / "console.txt"
    p.write_text("\n".join(lines))
    r = subprocess.run([sys.executable, "verifier/verify_qrg.py", str(p)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "VERIFIED"


def test_equivalence_power_helper():
    n = stats.min_shots_within(0.15, 0.25, 0.05)
    assert n is not None and n <= 2000


def test_pass_checks_never_show_failure_text():
    b, _ = run_app("A_NO_FAULT", SpyBackend())
    for c in b["preflight"]["checks"] + b["governor_decision"]["checks"]:
        if c["status"] == "PASS":
            for bad in ("!=", " > ", "cannot", "offline record", "denied"):
                assert bad not in c["detail"], c
