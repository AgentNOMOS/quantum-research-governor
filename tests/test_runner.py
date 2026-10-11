from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator

from qrg import ir, runner


class SpyBackend:
    """Wraps BasicSimulator and records every backend.run call."""

    def __init__(self):
        self.inner = BasicSimulator()
        self.name = self.inner.name
        self.calls = []

    def run(self, run_input, **kw):
        self.calls.append((run_input, kw))
        return self.inner.run(run_input, **kw)


def test_exactly_one_bare_circuit_per_run():
    spy = SpyBackend()
    qc = runner.to_qiskit(ir.circuit_ops("full", {"pattern": "IZII"}))
    runner.execute(qc, 256, seed=7, backend=spy)
    assert len(spy.calls) == 1
    assert isinstance(spy.calls[0][0], QuantumCircuit)


def test_seeded_execution_is_reproducible_and_matches_theory():
    qc = runner.to_qiskit(ir.circuit_ops("full", {"pattern": "IZII"}))
    _, a = runner.execute(qc, 500, seed=3)
    _, b = runner.execute(qc, 500, seed=3)
    assert a == b
    assert set(a) <= {"0100000", "0101111"}  # sX=1 always, data in {0000,1111}


def test_circuit_size():
    m = runner.circuit_metrics(runner.to_qiskit(ir.circuit_ops("full")))
    assert m["qubits"] == 7 and m["two_qubit_gates"] == 11 and m["depth_excl_measure"] == 10
