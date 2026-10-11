"""QRG-R1 Qollab entrypoint.

Uses ONLY the backend object injected by the Qollab runtime (global `backend`).
No fallback simulator is ever created here. Package selection lives in
experiment_config.py (the only file that differs between packages).
"""
from experiment_config import EXPERIMENT
from qrg.qollab_app import run

try:
    _INJECTED = backend  # noqa: F821  (provided by the Qollab runtime)
except NameError:
    _INJECTED = None

run(EXPERIMENT, _INJECTED)
