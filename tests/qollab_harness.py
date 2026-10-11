"""Qollab-like harness: run an EXTRACTED package's main.py with an injected backend.

  python -I tests/qollab_harness.py <extracted_dir> [basic|noseed|none]
"""
import os
import runpy
import sys
from types import SimpleNamespace

d, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "basic")
sys.path.insert(0, d)
os.chdir(d)
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.providers.basic_provider import BasicSimulator  # noqa: E402


class Injected:
    def __init__(self, seed_option):
        self._b = BasicSimulator()
        self.name = self._b.name
        self.options = self._b.options if seed_option else SimpleNamespace(shots=1024)
        self.calls = 0

    def run(self, run_input, **kw):
        self.calls += 1
        assert isinstance(run_input, QuantumCircuit), "bare circuit required"
        return self._b.run(run_input, **kw)


inj = None if mode == "none" else Injected(seed_option=(mode != "noseed"))
g = {} if inj is None else {"backend": inj}
runpy.run_path(os.path.join(d, "main.py"), init_globals=g, run_name="__main__")
print(f"HARNESS_BACKEND_RUN_CALLS {0 if inj is None else inj.calls}")
