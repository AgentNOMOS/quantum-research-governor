"""QRG-R2 bridge API: one job, verbatim evidence, zero-job demonstrations,
blinding and scientific/governor regression against R1."""
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator

from qrg import governor, ir, js_api, qollab_app, runner
from qrg.policy import make_policy_r1, policy_sha256
from verifier import verify_qrg

ROOT = Path(__file__).resolve().parent.parent
R1_POLICY_SHA = "002d54cd7b5e0e6c919fade135f06f22160308ac314230393365ef4af71865a5"


class Spy:
    def __init__(self, name="basic_simulator", fail=False, seed=3):
        self._b, self.name, self.fail, self.seed = BasicSimulator(), name, fail, seed
        self.options, self.calls = self._b.options, []

    def run(self, qc, **kw):
        self.calls.append((qc, dict(kw)))
        if self.fail:
            raise RuntimeError("backend down")
        kw.setdefault("seed_simulator", self.seed)
        return self._b.run(qc, **kw)


@pytest.fixture(params=["A_NO_FAULT", "B_Z_FAULT"])
def env_and_spy(request):
    spy = Spy()
    return js_api.build_envelope(request.param, spy), spy


def test_exactly_one_bare_circuit_including_demonstrations(env_and_spy):
    env, spy = env_and_spy
    assert env["status"] == "COMPLETED"
    assert len(spy.calls) == 1 and isinstance(spy.calls[0][0], QuantumCircuit)
    assert "seed_simulator" not in spy.calls[0][1]
    assert env["backend_run_calls_this_run"] == 1
    assert env["backend_run_calls_total_including_demonstrations"] == 1


def test_bridge_returns_single_json_string():
    spy = Spy()
    out = js_api.run_experiment(spy)  # experiment_config at repo root
    assert isinstance(out, str) and json.loads(out)["envelope_schema"] == js_api.ENVELOPE_SCHEMA
    assert len(spy.calls) == 1


def test_evidence_text_is_canonical_and_verifies(env_and_spy, tmp_path):
    env, _ = env_and_spy
    text = env["evidence_text"]
    assert hashlib.sha256(text.encode("ascii")).hexdigest() == env["evidence_sha256"]
    assert json.dumps(json.loads(text), sort_keys=True, separators=(",", ":")) == text  # Python round-trip stable
    assert env["verifier_report"]["status"] == "VERIFIED"
    p = tmp_path / "evidence.json"
    p.write_text(text)
    r = subprocess.run([sys.executable, "-I", "verifier/verify_qrg.py", str(p)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "VERIFIED"


def test_text_equals_r1_console_line(monkeypatch):
    """The exported text must be byte-identical to the R1 copyable console line."""
    captured = []
    real = qollab_app.run

    def wrapped(*a, emit=print, **k):
        def tee(line):
            captured.append(line)
            emit(line)
        return real(*a, emit=tee, **k)

    monkeypatch.setattr(qollab_app, "run", wrapped)
    env = js_api.build_envelope("B_Z_FAULT", Spy())
    r1_line = [l for l in captured if l.startswith(qollab_app.JSON_PREFIX)]
    assert len(r1_line) == 1 and r1_line[0][len(qollab_app.JSON_PREFIX):] == env["evidence_text"]
    assert not any(l.startswith(qollab_app.JSON_PREFIX) for l in env["log"])
    assert json.loads(env["evidence_text"])["bundle_schema"] == "qrg.r1.bundle.v1"


EXPECTED = {
    "reject-no-physical-error": ("REJECT", "CLAIM_EXCEEDS_CEILING"),
    "reject-error-corrected": ("REJECT", "CLAIM_EXCEEDS_CEILING"),
    "reject-quantum-advantage": ("REJECT", "CLAIM_EXCEEDS_CEILING"),
    "reject-ionq-backend": ("REJECT", "UNAUTHORIZED_BACKEND"),
    "reject-shot-limit": ("REJECT", "SHOT_LIMIT_EXCEEDED"),
    "reject-contradicted-live": ("REJECT", "CONTRADICTED_BY_EVIDENCE"),
    "escalate-underpowered": ("ESCALATE", "UNDERPOWERED"),
    "escalate-authorization": ("ESCALATE", "HUMAN_AUTHORIZATION_REQUIRED"),
    "escalate-non-discriminating": ("ESCALATE", "NON_DISCRIMINATING"),
    "escalate-offline-record": ("ESCALATE", "PROVENANCE_UNVERIFIED"),
    "freeze-edited-counts": ("FREEZE", "DIGEST_MISMATCH"),
    "freeze-impossible-outcome": ("FREEZE", "PHYSICS_MODEL_VIOLATION"),
    "freeze-missing-data": ("FREEZE", "MISSING_EVIDENCE"),
    "freeze-stale": ("FREEZE", "STALE_EVIDENCE"),
    "freeze-blinding": ("FREEZE", "BLINDING_VIOLATION"),
}


def test_demonstrations_verdicts_and_independent_agreement(env_and_spy):
    env, _ = env_and_spy
    got = {d["id"]: (d["governor"]["verdict"], d["governor"]["reason_code"]) for d in env["demonstrations"]}
    assert got == EXPECTED
    for d in env["demonstrations"]:
        assert d["executed_on_backend"] is False
        if d["verifier"] is not None:
            assert d["agree"], d["id"]
            assert (d["verifier"]["verdict"], d["verifier"]["reason_code"]) == got[d["id"]]


def test_demonstrations_leave_evidence_untouched(env_and_spy):
    env, _ = env_and_spy
    assert env["evidence_sha256_after_demonstrations"] == env["evidence_sha256"]
    b = json.loads(env["evidence_text"])
    before = json.dumps(b, sort_keys=True)
    js_api.build_demonstrations(b)
    assert json.dumps(b, sort_keys=True) == before


def test_blinding_regression_governor_inputs(monkeypatch):
    seen = []
    real = governor.evaluate_view

    def capture(proposal, view, *a, **kw):
        seen.append(json.dumps([proposal, view, a, kw], default=str))
        return real(proposal, view, *a, **kw)

    monkeypatch.setattr(governor, "evaluate_view", capture)
    env = js_api.build_envelope("B_Z_FAULT", Spy())
    assert len(seen) >= 8  # live verdict + evidence demonstrations
    secret = json.loads(env["evidence_text"])["audit_only"]
    for s in seen:
        for needle in ('"salt"', '"pattern"', '"coin_marginal"', secret["salt"], secret["fault_commitment"]):
            assert needle not in s


def test_governor_policy_and_claims_unchanged_from_r1():
    assert policy_sha256(make_policy_r1()) == R1_POLICY_SHA
    assert qollab_app.EXPERIMENTS["A_NO_FAULT"]["claim"] == {"type": "DETECTED_SYNDROME_RATE_AT_MOST", "params": {"eps": 0.01}}
    assert qollab_app.EXPERIMENTS["B_Z_FAULT"]["claim"] == {"type": "PHASE_SYNDROME_RATE_WITHIN", "params": {"lo": 0.15, "hi": 0.25}}
    assert qollab_app.EXPERIMENTS["B_Z_FAULT"]["fault"] == {"pattern": "IIZI", "mode": "stochastic", "p": 0.2}
    assert ir.skeleton_sha256("full") == "cc5fd2b9f2ec0f1ea8eb2f761bbbe81c1516860c7668dd67dfe496aca6cb911b"


@pytest.mark.parametrize("exp", ["A_NO_FAULT", "B_Z_FAULT"])
def test_drawn_circuit_is_the_executed_circuit(exp):
    cfg = qollab_app.EXPERIMENTS[exp]
    ops = ir.circuit_ops(cfg["variant"], cfg["fault"])
    want = Counter((o[0], tuple(o[1:]) if o[0] != "ry" else (o[2],)) for o in ops if o[0] != "measure_all")
    L = js_api.circuit_layout(cfg["variant"], cfg["fault"])
    got = Counter((o["gate"], tuple(o["qubits"])) for o in L if o["gate"] != "measure")
    assert got == want
    assert sum(1 for o in L if o["gate"] == "measure") == 7
    assert len({o["layer"] for o in L if o["gate"] == "measure"}) == 1


def test_detection_table_physics():
    rows = {r["pauli"]: r for r in js_api.detection_table()}
    assert rows["XIII"]["detected_full"] and rows["XIII"]["detected_zzzz_only"]
    assert rows["ZIII"]["detected_full"] and not rows["ZIII"]["detected_zzzz_only"]
    assert not rows["XXII"]["detected_full"] and not rows["ZIZI"]["detected_full"]


@pytest.mark.parametrize("backend,status,calls", [
    (None, "ERROR_NO_INJECTED_BACKEND", 0),
    (Spy(name="ionq_qpu"), "PREFLIGHT_REJECT", 0),
    (Spy(fail=True), "JOB_FAILED", 1),
])
def test_error_envelopes(backend, status, calls):
    env = js_api.build_envelope("A_NO_FAULT", backend)
    assert env["status"] == status and env["demonstrations"] == []
    assert env["backend_run_calls_total_including_demonstrations"] == calls
    if backend is not None:
        assert len(backend.calls) == calls


def test_internal_error_never_raises_across_bridge(monkeypatch):
    monkeypatch.setattr(qollab_app, "run", lambda *a, **k: 1 / 0)
    out = json.loads(js_api.run_experiment(Spy()))
    assert out["status"] == "INTERNAL_ERROR" and "ZeroDivisionError" in out["status_message"]
