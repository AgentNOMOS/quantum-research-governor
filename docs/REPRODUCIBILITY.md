# Reproducing and independently checking Quantum Research Governor

Tested with Python 3.13.5 and 3.14.3, Qiskit 2.5.2, Node 22 (JS tests), Chromium (browser tests).

## 1. Environment
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # qiskit==2.5.2, pytest
.venv/bin/pip install -r requirements-dev.txt      # optional: playwright client for browser tests
```

## 2. Run the quantum experiments locally (one job each)
```bash
.venv/bin/python - <<'PY'
import json
from qiskit.providers.basic_provider import BasicSimulator
from qrg import js_api
for exp in ("A_NO_FAULT", "B_Z_FAULT"):
    env = js_api.build_envelope(exp, BasicSimulator())
    open(f"evidence_{exp}.json", "w").write(env["evidence_text"])   # canonical text, verbatim
    print(exp, env["status"], json.loads(env["evidence_text"])["governor_decision"]["verdict"])
PY
```
Each Run is a fresh random sample. Package B's ACCEPT is likely (≈ 0.9999 at p = 0.2, see
`results/r1_calibration.json`) but not guaranteed; the app always shows the verdict actually computed.

## 3. Verify any evidence record independently (standard library only)
```bash
python3 verifier/verify_qrg.py evidence_B_Z_FAULT.json
```
The verifier never imports `qrg` or Qiskit and never trusts stored PASS values. It:
1. recomputes raw-count **totals** and the SHA-256 of counts and records;
2. **decodes syndromes** (key = control sX sZ d3 d2 d1 d0) and checks the governor view is the raw
   counts with the control bit removed;
3. recomputes the one-sided Clopper–Pearson **bounds** with an incomplete-beta method;
4. parses the **circuit** description to find which stabilizers were measured and checks the
   circuit-skeleton and **policy** hashes;
5. re-derives the **governor decision** from the policy contract;
6. reports an **offline assessment**: a pasted record can be checked for consistency, never for
   origin — offline records are never ACCEPTed (`PROVENANCE_UNVERIFIED`).

Frozen identities: policy SHA-256 `002d54cd7b5e0e6c919fade135f06f22160308ac314230393365ef4af71865a5`;
circuit skeleton SHA-256 `cc5fd2b9f2ec0f1ea8eb2f761bbbe81c1516860c7668dd67dfe496aca6cb911b`.

## 4. Rebuild the exact Qollab packages
```bash
python3 scripts/build_packages_r2.py
sha256sum dist/qrg_r2_*.zip
# 2cb6ddeb2665713384226fbd2dd5d11e73edfe0be8200b423289424e5c6506cd  qrg_r2_A_clean_app.zip
# e726721c002516b5559e8c6a21ecea7c6291712e8412ce72ffcb7bdaf26cab99  qrg_r2_B_zfault_app.zip
```

## 5. Run the test suites
```bash
.venv/bin/python -m pytest -q          # Python: science, governor, verifier, packages, browser (if chromium + playwright)
node --test tests/js/*.test.mjs        # JS UI logic incl. SHA-256 and re-serialisation trap
.venv/bin/python -m experiments.run_r0 # 27-scenario governance matrix
.venv/bin/python -m experiments.r1_calibration   # exact operating characteristics
```
Browser tests use a **mocked** Qollab bridge (`dev/mock/`), fed with fixtures from the real Python
API; they test the UI, not Qollab itself. Set `CHROMIUM=/path/to/chromium` if not at `/usr/bin/chromium`.

## 6. Run in Qollab
Upload `qrg_r2_B_zfault_app.zip` (primary) or `qrg_r2_A_clean_app.zip` (control) as a Qollab
project, choose the built-in simulator, press Run. See `docs/R2_QOLLAB_ACCEPTANCE_CHECKLIST.md`.
