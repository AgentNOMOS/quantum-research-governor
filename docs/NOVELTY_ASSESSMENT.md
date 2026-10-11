# QRG-R0 Novelty Assessment

## Known science (not ours)
* [[4,2,2]] / smallest error-detecting code: Vaidman–Goldenberg–Wiesner 1996; Grassl et al. 1997.
* Hardware demonstrations: **Linke et al., "Fault-tolerant quantum error detection", Sci. Adv.
  3, e1701074 (2017)** — trapped ions (Monroe group, the academic lineage of IonQ); **Takita et al.,
  PRL 119, 180501 (2017)** — IBM superconducting qubits; Harper & Flammia (2019) — logical RB in
  the [[4,2,2]] code space; Córcoles et al. 2015 — detecting arbitrary errors on a 4-qubit lattice.
* Stabilizer witnesses and certification: Tóth & Gühne 2005; Flammia & Liu 2011 (direct fidelity
  estimation); Eisert et al. 2020 (certification and benchmarking review).
* Exact binomial confidence bounds: Clopper & Pearson 1934.
* Generic AI-claim verification (non-quantum-native): AutoVerifier (arXiv 2604.02617), POPPER
  (sequential falsification, e-values), OmniScientist (code-enforced exit checks), P-Bench.
  None decide claims from quantum measurement data with circuit-derived discriminability.

## Our application-level contribution (proposed, demonstrated only on an ideal simulator)
1. **Circuit-derived claim admissibility**: before spending shots, the governor computes from the
   circuit itself (exact independent simulation) whether the measured event can separate the
   claimed hypothesis class from its competitors. Same claim, different circuit → different
   verdict (S22: classical parity check cannot see the phase fault → ESCALATE + "run `full`").
2. **Physics-derived claim ceiling**: what may be claimed follows from code distance and
   stabilizer algebra (detect ≠ locate ≠ correct; logical faults are silent), not from a
   hand-written blacklist alone — every ceiling entry has a physical justification and tests.
3. **Physics-model tamper witness**: the redundant ZZZZ readout makes forged counts detectable
   even when hashes are recomputed (S09).
4. **Four-valued verdict with statistical meaning** (ACCEPT/REJECT/ESCALATE/FREEZE), with
   ESCALATE distinct from REJECT and FREEZE distinct from both.
5. **Sealed fault**: the governor judges from counts only; the referee opens a hash commitment.

## Distinctness
| comparator | why QRG is different |
|---|---|
| quantum circuit tutorial | the output is a governed decision about a claim, with red-team evidence that it refuses bad claims |
| generic QAOA scheduler (Project 2) | no optimisation; measures stabilizers to test hypotheses |
| static evidence dashboard | the measured counts change the verdict (S01 vs S05 vs S06 vs S07) |
| classical rule engine + quantum logo | strawman baseline in `experiments/naive_baseline.py` false-accepts S10, S16, S22 and accepts unverifiable evidence (S08/S09/S11/S26/S27); the decisive difference in S22 needs the XXXX measurement and circuit-level discriminability |
| Magic Square (Project 1) | no nonlocal game, no Bell pairs, no win-probability; GHZ-type code state, stabilizer syndromes, error detection, claim governance |

## Honest limits of the novelty
* No new quantum algorithm or code. The quantum part is textbook.
* The contribution is the governance integration; on an ideal simulator its value is pedagogical.
* The claim vocabulary is small and hand-designed.
