"""Generate browser-test fixtures from the REAL Python bridge API (dev only, never packaged).

  .venv/bin/python dev/make_fixtures.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qiskit.providers.basic_provider import BasicSimulator  # noqa: E402

from qrg import js_api, qollab_app  # noqa: E402

OUT = ROOT / "dev/fixtures"


class SeededInjected:
    """Stands in for Qollab's injected backend; seeds the INNER simulator only."""
    def __init__(self, seed, name="basic_simulator", fail=False):
        self._b, self.name, self.seed, self.fail = BasicSimulator(), name, seed, fail
        self.options = self._b.options

    def run(self, qc, **kw):
        if self.fail:
            raise RuntimeError("backend unavailable (simulated)")
        kw.setdefault("seed_simulator", self.seed)
        return self._b.run(qc, **kw)


def dump(name, env):
    if "traceback" in env:  # dev fixture only: never ship local absolute paths
        env["traceback"] = env["traceback"].replace(str(ROOT), "<repo>").replace(sys.prefix, "<python>")
    (OUT / name).write_text(json.dumps(env, sort_keys=True, separators=(",", ":")))
    print(name, env["status"], env.get("evidence_sha256", "")[:12])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dump("envelope_A.json", js_api.build_envelope("A_NO_FAULT", SeededInjected(101)))
    dump("envelope_B.json", js_api.build_envelope("B_Z_FAULT", SeededInjected(202)))
    dump("envelope_no_backend.json", js_api.build_envelope("A_NO_FAULT", None))
    dump("envelope_preflight_reject.json", js_api.build_envelope("A_NO_FAULT", SeededInjected(1, name="ionq_qpu")))
    dump("envelope_job_failed.json", js_api.build_envelope("B_Z_FAULT", SeededInjected(1, fail=True)))
    real = qollab_app.run
    qollab_app.run = lambda *a, **k: (_ for _ in ()).throw(ValueError("simulated internal failure"))
    try:
        dump("envelope_internal_error.json", js_api.build_envelope("A_NO_FAULT", SeededInjected(1)))
    finally:
        qollab_app.run = real


if __name__ == "__main__":
    main()
