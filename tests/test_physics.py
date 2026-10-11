import subprocess
import sys
from itertools import product
from pathlib import Path

import pytest

from qrg import ir, runner, witness_sim
from experiments.referee import anticommutes

ROOT = Path(__file__).resolve().parent.parent


def test_independent_simulator_does_not_import_qiskit():
    code = "import sys; import qrg.witness_sim, qrg.governor; assert not any(m.startswith('qiskit') for m in sys.modules)"
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def test_stabilizers_commute_and_logical_state():
    assert not anticommutes("XXXX", "ZZZZ")
    d = witness_sim.visible_distribution("full", {"pattern": "IIII"})
    assert d == pytest.approx({"000000": 0.5, "001111": 0.5})


@pytest.mark.parametrize("P,sz,sx", [("X", 1, 0), ("Z", 0, 1), ("Y", 1, 1)])
def test_weight1_syndrome_table(P, sz, sx):
    for k in range(4):
        pat = "".join(P if i == k else "I" for i in range(4))
        f = {"pattern": pat}
        assert witness_sim.event_probability("full", f, "SZ") == pytest.approx(sz)
        assert witness_sim.event_probability("full", f, "SX") == pytest.approx(sx)
        # z_only cannot see the phase component at all
        assert witness_sim.event_probability("z_only", f, "SX") == pytest.approx(0)


def test_simulator_matches_symplectic_commutation_for_all_256_paulis():
    for pat in map("".join, product("IXYZ", repeat=4)):
        f = {"pattern": pat}
        assert witness_sim.event_probability("full", f, "SZ") == pytest.approx(float(anticommutes(pat, "ZZZZ")))
        assert witness_sim.event_probability("full", f, "SX") == pytest.approx(float(anticommutes(pat, "XXXX")))


def test_logical_xxii_is_syndrome_silent():
    assert witness_sim.event_probability("full", {"pattern": "XXII"}, "ANY") == pytest.approx(0)


def test_stochastic_channel_rate():
    f = {"pattern": "IIZI", "mode": "stochastic", "p": 0.2}
    assert witness_sim.event_probability("full", f, "SX") == pytest.approx(0.2)


def test_independent_sim_matches_qiskit_statevector():
    from qiskit.quantum_info import Statevector
    for v in ir.VARIANTS:
        for f in [*witness_sim.single_fault_hypotheses().values(),
                  {"pattern": "YIIZ", "mode": "stochastic", "p": 0.37}]:
            ops = [o for o in ir.circuit_ops(v, f) if o[0] != "measure_all"]
            q = Statevector(runner.to_qiskit(ops)).probabilities_dict()
            w = witness_sim.distribution(ops)
            for k in set(q) | set(w):
                assert abs(q.get(k, 0) - w.get(k, 0)) < 1e-12


def test_pauli_model_support_is_parity_invariant():
    for v, size in (("full", 32), ("z_only", 16)):
        sup = witness_sim.pauli_model_support(v)
        assert len(sup) == size
        for key in sup:  # visible key: sX sZ d3 d2 d1 d0
            assert int(key[1]) == sum(map(int, key[2:])) % 2
