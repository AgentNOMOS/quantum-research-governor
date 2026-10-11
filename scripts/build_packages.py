"""Build deterministic Qollab private-upload ZIPs (fixed timestamps, sorted entries).

  .venv/bin/python scripts/build_packages.py
"""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
CODE = ["main.py", "LICENSE",
        "qrg/__init__.py", "qrg/ir.py", "qrg/witness_sim.py", "qrg/stats.py", "qrg/evidence.py",
        "qrg/policy.py", "qrg/blinding.py", "qrg/governor.py", "qrg/runner.py", "qrg/qollab_app.py",
        "verifier/__init__.py", "verifier/verify_qrg.py"]
PACKAGES = {
    "A": ("A_NO_FAULT", "qrg_r1_A_no_fault.zip", "Package A — no fault (clean encoded state)",
          "DETECTED_SYNDROME_RATE_AT_MOST eps=0.01"),
    "B": ("B_Z_FAULT", "qrg_r1_B_z_fault.zip", "Package B — SYNTHETIC stochastic Z fault on q2, nominal p=0.2",
          "PHASE_SYNDROME_RATE_WITHIN [0.15, 0.25]"),
    "C": ("C_SEED_REPLAY_PROBE", "qrg_r1_C_seed_replay_probe_OPTIONAL.zip",
          "Package C (optional) — seeded replay probe; run twice, compare visible_counts_sha256",
          "DETECTED_SYNDROME_RATE_AT_MOST eps=0.01 (seed_simulator=20261010)"),
}
DATE = (2026, 10, 10, 0, 0, 0)


def entry(zf, name, data):
    zi = zipfile.ZipInfo(name, DATE)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    zf.writestr(zi, data)


def build(letter, out_dir=None):
    exp, fname, title, claim = PACKAGES[letter]
    files = {p: (ROOT / p).read_bytes() for p in CODE}
    files["experiment_config.py"] = (
        f"# Package selector (the only file that differs between packages).\nEXPERIMENT = \"{exp}\"\n").encode()
    files["requirements.txt"] = b"qiskit>=2.5.2,<3\n"
    files["README.md"] = (ROOT / "packaging/README.template.md").read_text().replace(
        "{PKG_LABEL}", f"package {letter}").replace("{PKG_TITLE}", title).replace("{PKG_CLAIM}", claim).encode()
    files["docs/SCIENTIFIC_LIMITATIONS.md"] = (ROOT / "packaging/SCIENTIFIC_LIMITATIONS.md").read_bytes()
    files["docs/DISCLOSURE.md"] = (ROOT / "packaging/DISCLOSURE.md").read_bytes()
    out_dir = Path(out_dir) if out_dir else DIST
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / fname
    with zipfile.ZipFile(out, "w") as zf:
        for name in sorted(files):
            entry(zf, name, files[name])
    return out, hashlib.sha256(out.read_bytes()).hexdigest(), sorted(files)


def main():
    manifest = {}
    for letter in PACKAGES:
        path, sha, names = build(letter)
        manifest[path.name] = {"sha256": sha, "files": names, "bytes": path.stat().st_size}
        print(f"{sha}  {path.relative_to(ROOT)}")
    (DIST / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
