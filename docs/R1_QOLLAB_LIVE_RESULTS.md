# QRG-R1 — authoritative real Qollab results (owner-executed, 2026-10-10)

Both R1 packages were run by the owner in the real Qollab browser on the built-in simulator.
These are the only browser-verified results. R2 must not alter their scientific interpretation.

| | Package A (no fault) | Package B (synthetic stochastic Z on q2, p = 0.2) |
|---|---|---|
| backend | basic_simulator (`qiskit.providers.basic_provider.basic_simulator.BasicSimulator`) | basic_simulator |
| qubits / shots | 7 / 2000 | 7 / 2000 |
| raw counts (c6..c0) | `0000000`: 1031, `0001111`: 969 | `0000000`: 810, `0001111`: 770, `1100000`: 208, `1101111`: 212 |
| syndrome events | nontrivial: 0 | XXXX: 420, ZZZZ: 0 |
| governed claim | detected-syndrome rate ≤ 0.01 | XXXX syndrome rate ∈ [0.15, 0.25] (TOST) |
| one-sided 95% bounds | upper 0.0014967448951882841 | [0.19509061378833903, 0.22554179990774226] |
| governor | ACCEPT / SUPPORTED | ACCEPT / SUPPORTED |
| in-run verifier | VERIFIED | VERIFIED |
| backend jobs | 1 | 1 |

Seed: the built-in backend *advertises* `seed_simulator`; seeded reproducibility was **not**
established (package C was not run). Regression: `tests/test_r1_live_baseline.py`.
