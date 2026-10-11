"""Qiskit execution: exactly ONE bare QuantumCircuit per backend.run call."""
from __future__ import annotations

from qiskit import QuantumCircuit

from . import ir


def to_qiskit(ops, name="qrg_422_syndrome"):
    qc = QuantumCircuit(ir.N_QUBITS, ir.N_QUBITS, name=name)
    for op in ops:
        g = op[0]
        if g == "measure_all":
            qc.barrier()
            qc.measure(range(ir.N_QUBITS), range(ir.N_QUBITS))
        elif g == "ry":
            qc.ry(op[1], op[2])
        elif g in ("h", "x", "y", "z"):
            getattr(qc, g)(op[1])
        elif g in ("cx", "cy", "cz"):
            getattr(qc, g)(op[1], op[2])
        else:
            raise ValueError(g)
    return qc


def default_backend():
    from qiskit.providers.basic_provider import BasicSimulator
    return BasicSimulator()


BACKEND_RUN_CALLS = 0  # every backend.run made through this module, per process


def backend_identity(backend):
    name = getattr(backend, "name", None)
    if callable(name):  # BackendV1 style
        name = name()
    cls = type(backend)
    return {"name": str(name), "class": f"{cls.__module__}.{cls.__qualname__}"}


def probe_seed_option(backend):
    """Inspect advertised options WITHOUT submitting a job."""
    opts = getattr(backend, "options", None)
    fields = getattr(opts, "__dict__", {}) or {}
    try:
        has = "seed_simulator" in fields or hasattr(opts, "seed_simulator")
    except Exception:  # pragma: no cover - exotic option objects
        has = False
    return {"seed_simulator_advertised": bool(has),
            "method": "static inspection of backend.options (no job submitted)",
            "note": "advertised != honoured; reproducibility needs two separately authorized seeded Runs"}


def normalize_counts(counts):
    norm = {}
    for k, v in counts.items():
        k = str(k).replace(" ", "")
        if k.startswith("0x"):
            k = format(int(k, 16), f"0{ir.N_QUBITS}b")
        k = k.zfill(ir.N_QUBITS)
        norm[k] = norm.get(k, 0) + int(v)
    return dict(sorted(norm.items()))


def execute(qc, shots, seed=None, backend=None):
    """Single job, single circuit, no retry. Returns (backend_name, counts)."""
    global BACKEND_RUN_CALLS
    backend = backend or default_backend()
    kwargs = {"shots": shots}
    if seed is not None:
        kwargs["seed_simulator"] = seed
    BACKEND_RUN_CALLS += 1
    job = backend.run(qc, **kwargs)  # one bare circuit, never a list
    counts = job.result().get_counts()
    return backend_identity(backend)["name"], normalize_counts(counts)


def circuit_metrics(qc):
    ops = dict(qc.count_ops())
    two_q = sum(1 for inst in qc.data if inst.operation.num_qubits == 2)
    return {"qubits": qc.num_qubits, "clbits": qc.num_clbits,
            "depth": qc.depth(), "depth_excl_measure": qc.depth(lambda i: i.operation.name not in ("measure", "barrier")),
            "two_qubit_gates": two_q, "ops": {k: int(v) for k, v in ops.items()}}
