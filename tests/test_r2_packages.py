"""QRG-R2 packages: deterministic, exact contents, secret/IP/path scan, and the
EXTRACTED ZIP exercised both through its Python bridge and in headless Chromium."""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_packages_r2 as bp  # noqa: E402

EXPECTED_FILES = sorted(bp.CODE + ["experiment_config.py", "requirements.txt", "README.md",
                                   "docs/SCIENTIFIC_LIMITATIONS.md", "docs/DISCLOSURE.md"])
DENY = [r"/home/[a-z][a-z0-9_-]+", r"BEGIN [A-Z ]*PRIVATE KEY", r"(?i)api[_-]?key\s*[:=]", r"(?i)password\s*[:=]",
        r"(?i)secret\s*[:=]", r"sk-[A-Za-z0-9]{16,}", r"ghp_[A-Za-z0-9]{20,}", r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"]
_PRIVATE = ROOT / ".release-denylist"  # git-ignored, never exported; adds private patterns when present
if _PRIVATE.exists():
    DENY += [l.strip() for l in _PRIVATE.read_text().splitlines() if l.strip() and not l.startswith("#")]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    return {k: bp.build(k, out) for k in bp.PACKAGES}


def test_deterministic(built, tmp_path):
    assert {k: bp.build(k, tmp_path)[1] for k in bp.PACKAGES} == {k: v[1] for k, v in built.items()}


def test_exact_contents_no_dev_material(built):
    for _, (path, _, names) in built.items():
        assert names == EXPECTED_FILES
        assert "main.py" not in names and not any(n.startswith(("dev/", "tests/", "results/")) for n in names)


def test_ab_differ_only_in_config_and_readme(built):
    za, zb = zipfile.ZipFile(built["A"][0]), zipfile.ZipFile(built["B"][0])
    assert sorted(n for n in za.namelist() if za.read(n) != zb.read(n)) == ["README.md", "experiment_config.py"]


def test_scan_for_credentials_ips_private_paths(built):
    for _, (path, _, _) in built.items():
        with zipfile.ZipFile(path) as zf:
            for n in zf.namelist():
                text = zf.read(n).decode("utf-8")
                for pat in DENY:
                    m = re.search(pat, text)
                    assert m is None, f"{path.name}:{n} matches {pat!r}: {m.group(0) if m else ''}"


def test_attribution_and_licence(built):
    with zipfile.ZipFile(built["A"][0]) as zf:
        readme = zf.read("README.md").decode()
        assert "This effort is supported by Qollab & IonQ" in readme
        assert "MIT License" in zf.read("LICENSE").decode()
        assert "Qollab &amp; IonQ" in zf.read("index.html").decode()


HARNESS = r'''
import json, sys
d = sys.argv[1]; sys.path.insert(0, d)
from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator
class Injected:
    def __init__(self): self._b = BasicSimulator(); self.name = self._b.name; self.options = self._b.options; self.calls = 0
    def run(self, qc, **kw):
        assert isinstance(qc, QuantumCircuit); self.calls += 1; return self._b.run(qc, **kw)
inj = Injected()
import qrg.js_api as api
out = api.run_experiment(inj)          # what main.js does via callPromising(backend)
print(json.dumps({"calls": inj.calls, "env": json.loads(out)}))
'''


@pytest.mark.parametrize("letter,exp", [("A", "A_NO_FAULT"), ("B", "B_Z_FAULT")])
def test_extracted_package_bridge(built, tmp_path, letter, exp):
    d = tmp_path / letter
    zipfile.ZipFile(built[letter][0]).extractall(d)
    h = tmp_path / "h.py"
    h.write_text(HARNESS)
    r = subprocess.run([sys.executable, "-I", str(h), str(d)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout.strip().splitlines()[-1])
    env = res["env"]
    assert res["calls"] == 1 and env["experiment"] == exp and env["status"] == "COMPLETED"
    assert env["verifier_report"]["status"] == "VERIFIED"
    (tmp_path / "ev.json").write_text(env["evidence_text"])
    v = subprocess.run([sys.executable, "-I", "verifier/verify_qrg.py", str(tmp_path / "ev.json")],
                       cwd=d, capture_output=True, text=True)
    assert v.returncode == 0


def test_extracted_package_ui_in_browser(built, tmp_path):
    pw = pytest.importorskip("playwright.sync_api")
    import test_browser as tb
    if not Path(tb.CHROMIUM).exists():
        pytest.skip("no chromium")
    d = tmp_path / "pkgB"
    zipfile.ZipFile(built["B"][0]).extractall(d)
    # test-only: add the dev mock + fixtures next to the extracted package for serving
    shutil.copytree(ROOT / "dev/mock", d / "dev/mock")
    shutil.copytree(ROOT / "dev/fixtures", d / "dev/fixtures")
    srv, url = tb.serve(d)
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch(executable_path=tb.CHROMIUM, args=["--no-sandbox"])
            page, f, errors = tb.open_app(b, url, {"mode": "fixture", "fixture": "envelope_B.json"}, root=d)
            assert "1 backend job" in f.inner_text("#qrg-status-text") and not errors
            assert f.evaluate("globalThis.__QRG_MOCK_CALLS__.length") == 1
            b.close()
    finally:
        srv.shutdown()


FROZEN = {"A": "2cb6ddeb2665713384226fbd2dd5d11e73edfe0be8200b423289424e5c6506cd",
          "B": "e726721c002516b5559e8c6a21ecea7c6291712e8412ce72ffcb7bdaf26cab99"}


def test_current_sources_rebuild_the_frozen_owner_tested_zips(built):
    """Release freeze: sources must reproduce the exact ZIP bytes the owner ran in Qollab."""
    assert {k: v[1] for k, v in built.items()} == FROZEN


def test_frozen_release_copies_untouched():
    import hashlib
    for k, name in (("A", "qrg_r2_A_clean_app.zip"), ("B", "qrg_r2_B_zfault_app.zip")):
        p = ROOT / "release/r2" / name
        if p.exists():
            assert hashlib.sha256(p.read_bytes()).hexdigest() == FROZEN[k]
