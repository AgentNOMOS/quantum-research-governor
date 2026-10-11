# QRG-R0 Feasibility Report (2026-10-10)

## Candidate evaluation
| criterion | A. syndrome verification ([[4,2,2]]) | B. stabilizer/graph-state witness | C. adaptive governance alone |
|---|---|---|---|
| scientific validity | high (standard code, exact theory) | high | depends on A/B for substance |
| quantum-specific substance | high: phase errors only visible via XXXX | high | low on its own (classical decision logic) |
| original application angle | claim admissibility from syndrome discriminability | fidelity-bound claims | experiment selection |
| difference from Proj. 1 | strong (no game, no Bell pairs) | **weak**: Bell/GHZ verification is close to Mermin-Peres | strong |
| difference from Proj. 2 | strong | strong | moderate (both are "decision" apps) |
| qubits / 2q gates | 6 (+1 coin), 11–12 | 3–5, but **≥2 bases → ≥2 circuits** | — |
| one job per Run | **yes**: both stabilizers via ancillas | no (basis rotations per setting) unless one fidelity term | n/a |
| raw evidence quality | per-shot syndromes + redundant parity | expectation values per basis | — |
| independent verification | exact sim + symplectic rule + replay | exact sim | — |
| honest failure modes | rich (silent logical, non-locatable, blind variant) | moderate | — |
| jury demo | inject fault → syndrome lights → verdict | abstract | abstract |
| completion risk | low | medium (multi-circuit vs Qollab/IonQ) | medium |

**Selected: A**, using a light version of C (preflight refuses non-discriminating, underpowered
or unauthorized runs and recommends the cheapest discriminating alternative). B is rejected for
R0 because of its overlap with Project 1 and the multi-circuit requirement.

## Qollab / IonQ compatibility analysis (NOT browser-verified)
* One bare `QuantumCircuit` per `backend.run`, all measurements at the end, gates
  {h, cx, cz, ry} — tested locally with a spy backend (`tests/test_runner.py`).
* 7 qubits — within IonQ simulator limits (not attempted; no network jobs in R0).
* `seed_simulator` is used for replay; whether Qollab's injected backend honours it is
  **unknown** → open risk. Fallback: statistical (two-sample) replay, not built.
* The replay witness is a **second Run**, still one job per Run.
* The governor, statistics and independent simulator are pure Python (no numpy/scipy), which keeps
  a JS ↔ Python bridge simple; it still needs a user-executed browser test.

## Status of claims in this document
Demonstrated (local, Python 3.13.5, Qiskit 2.5.2 BasicSimulator): all results in
`results/r0_results.json`, 48/48 tests.
Planned / unverified: Qollab browser execution, IonQ simulator, hardware noise tolerance
calibration, statistical replay, UI.
