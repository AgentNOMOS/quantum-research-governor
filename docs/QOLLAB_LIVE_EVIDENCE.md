# Real Qollab evidence (owner-executed) — and what is NOT live

All four runs below were executed by the project owner in the real Qollab browser on the built-in
**ideal** simulator (`basic_simulator`, class `qiskit.providers.basic_provider.basic_simulator.BasicSimulator`),
7 qubits, 2000 shots, one backend job per Run as recorded by the application's own instrumentation.
No provider-side job log was available; the one-job count is the application's record, not an
independent provider audit. None of these runs is evidence about physical hardware.

| Run | Package | Raw counts (c6..c0 = control sX sZ d3 d2 d1 d0) | Syndromes | One-sided 95 % bounds | Governor | Verifier |
|---|---|---|---|---|---|---|
| R1-A | `qrg_r1_A_no_fault.zip` | 0000000: 1031 · 0001111: 969 | any: 0/2000 | upper 0.0014967448951882841 | ACCEPT / SUPPORTED | VERIFIED |
| R1-B | `qrg_r1_B_z_fault.zip` | 0000000: 810 · 0001111: 770 · 1100000: 208 · 1101111: 212 | XXXX 420, ZZZZ 0 | [0.19509061378833903, 0.22554179990774226] | ACCEPT / SUPPORTED | VERIFIED |
| R2-A | `qrg_r2_A_clean_app.zip` | 0000000: 1008 · 0001111: 992 | any: 0/2000 | upper 0.0014967448951882841 | ACCEPT / SUPPORTED | VERIFIED |
| R2-B | `qrg_r2_B_zfault_app.zip` | 0000000: 812 · 0001111: 775 · 1100000: 205 · 1101111: 208 | XXXX 413 (0.2065), ZZZZ 0 | [0.19168686065152074, 0.22195326711385566] | ACCEPT / SUPPORTED | VERIFIED |

Claims: A — detected-syndrome rate ≤ 0.01; B — XXXX syndrome rate within [0.15, 0.25] (TOST).
Every number above is re-derived from the raw counts by `tests/test_r1_live_baseline.py` and
`tests/test_r2_live_baseline.py` (governor statistics and the independent verifier).
The complete R2 evidence JSON files were audited independently on the owner side; they are not
stored in this repository. To add them: save each as `evidence/qollab_r2_<A|B>.json` and run
`python verifier/verify_qrg.py evidence/qollab_r2_B.json`.

The built-in backend **advertises** `seed_simulator`; seeded reproducibility was **not** established.

## Data that is NOT live — never relabel it
| Kind | Where | What it is |
|---|---|---|
| Local test fixtures | `dev/fixtures/*.json` | produced by the real Python API on a local seeded BasicSimulator, for UI tests with a mocked bridge |
| Local reference runs | `results/r1_local_*` | local Python 3.14 runs of the R1 packages |
| Local research results | `results/r0_results.json`, `results/r1_calibration.json`, `results/r1_bias_check.json` | R0 scenario matrix, exact operating characteristics, bias check |
| Counterfactual demonstrations | Scene A menu, Scene E cards | zero-job preflights, other claims on the same evidence, mutations of a copy of the evidence |
