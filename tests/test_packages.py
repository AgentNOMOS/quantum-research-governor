"""Build the real ZIPs, extract them, run main.py in an isolated interpreter
with an injected backend, and verify the console JSON line offline."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_packages  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    return {k: build_packages.build(k, out) for k in build_packages.PACKAGES}


def run_pkg(zip_path, tmp, mode="basic"):
    d = tmp / zip_path.stem
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(d)
    r = subprocess.run([sys.executable, "-I", str(ROOT / "tests/qollab_harness.py"), str(d), mode],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    return d, r.stdout


def bundle_of(out):
    lines = [l for l in out.splitlines() if l.startswith("QRG_BUNDLE_JSON ")]
    assert len(lines) == 1
    return json.loads(lines[0][len("QRG_BUNDLE_JSON "):])


def test_deterministic_build(built, tmp_path):
    again = {k: build_packages.build(k, tmp_path)[1] for k in build_packages.PACKAGES}
    assert again == {k: v[1] for k, v in built.items()}


def test_same_scientific_implementation(built):
    za, zb = zipfile.ZipFile(built["A"][0]), zipfile.ZipFile(built["B"][0])
    differ = [n for n in za.namelist() if za.read(n) != zb.read(n)]
    assert sorted(differ) == ["README.md", "experiment_config.py"]


@pytest.mark.parametrize("letter,verdict", [("A", "ACCEPT"), ("B", "ACCEPT")])
def test_extracted_package_runs_and_verifies(built, tmp_path, letter, verdict):
    d, out = run_pkg(built[letter][0], tmp_path)
    b = bundle_of(out)
    assert "HARNESS_BACKEND_RUN_CALLS 1" in out
    assert b["status"] == "COMPLETED" and b["governor_decision"]["verdict"] == verdict
    assert b["in_run_independent_verification"]["status"] == "VERIFIED"
    (tmp_path / "console.txt").write_text(out)
    r = subprocess.run([sys.executable, "-I", "verifier/verify_qrg.py", str(tmp_path / "console.txt")],
                       cwd=d, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "VERIFIED"


def test_no_backend_no_job(built, tmp_path):
    _, out = run_pkg(built["A"][0], tmp_path, "none")
    assert bundle_of(out)["status"] == "ERROR_NO_INJECTED_BACKEND"


def test_noseed_backend(built, tmp_path):
    _, out = run_pkg(built["B"][0], tmp_path, "noseed")
    b = bundle_of(out)
    assert "HARNESS_BACKEND_RUN_CALLS 1" in out and b["seed_probe"]["seed_simulator_advertised"] is False
    _, out = run_pkg(built["C"][0], tmp_path / "c", "noseed")
    assert bundle_of(out)["status"] == "SEED_REPLAY_UNAVAILABLE" and "HARNESS_BACKEND_RUN_CALLS 0" in out


def test_seed_probe_twice_identical(built, tmp_path):
    digests = []
    for i in range(2):
        _, out = run_pkg(built["C"][0], tmp_path / str(i))
        digests.append(bundle_of(out)["governor_view"]["visible_counts_sha256"])
    assert digests[0] == digests[1]
