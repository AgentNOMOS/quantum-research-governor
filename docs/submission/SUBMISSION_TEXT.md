# Quantum Research Governor
### Governing Quantum Experiments Through Verifiable Evidence

*AgentNOMOS Quantum Lab · Qollab × IonQ Quantum Hackathon 2026 · Theme: Quantum Unlocked*
**This effort is supported by Qollab & IonQ.**

> A quantum experiment produced measurements. Does the evidence actually justify the proposed conclusion?

## The problem
Quantum results are easy to over-read. A clean-looking histogram can hide faults the experiment was
never able to see; a small sample can look convincing; a copied result file can be edited. Before a
claim is made, someone has to ask: *was this experiment even capable of answering the question, is
the sample large enough, is the record intact, and what does the evidence not prove?*

Quantum Research Governor turns those questions into an interactive, verifiable decision.

## The quantum experiment
One 7-qubit Qiskit circuit, run once per press of **Run** on Qollab's built-in simulator:
- **q0–q3** hold the logical state |00⟩_L = (|0000⟩ + |1111⟩)/√2 of the **[[4,2,2]] error-detecting code**.
- **q4** measures the stabilizer **ZZZZ** (flags bit-flip faults).
- **q5** measures the stabilizer **XXXX** (flags phase-flip faults — invisible to any ordinary bit-parity check).
- **q6** injects a clearly labelled **synthetic fault**: in the primary package, a Z fault on q2 with probability 0.2.

Depth 10 (11 with measurement), 12 two-qubit gates, everything measured once at the end, exactly one
bare `QuantumCircuit` per backend job.

## How the app works — six scenes
- **A · Proposal.** Hypothesis, backend, shot budget and the precise claim. A deterministic **preflight**
  checks authorization, budget, statistical power and whether the circuit can distinguish the claim
  from competing explanations, before any shot is spent. A menu of counterfactual requests (IonQ hardware,
  100 shots, a ZZZZ-only circuit, "no error occurred"…) shows LOCAL preflight verdicts with no quantum job.
- **B · Circuit.** The executed circuit, drawn from the same operations that were submitted, with gate
  counts taken from the real circuit object, and a table of which faults each check can see — including
  the **syndrome-silent** logical error XXII.
- **C · Measurements.** LIVE counts from this Run only, syndrome rates with exact confidence intervals,
  and why ZZZZ alone would report the phase-faulted state as clean.
- **D · Independent witness.** A separate standard-library Python verifier and a JavaScript cross-check
  recompute totals, syndrome decoding, the parity invariant, confidence bounds, circuit and policy
  identity, SHA-256 and the decision — never trusting stored PASS flags. The complete evidence JSON can
  be copied verbatim and re-verified offline.
- **E · Decision.** The LIVE verdict with its bounds, plus demonstrations of every other verdict that are
  explicitly labelled as local and never executed on the backend.
- **F · Limits.** What this evidence cannot prove.

## Four verdicts
- **ACCEPT** — the evidence supports exactly this bounded claim (the opposite is rejected at the 5 % level).
- **REJECT** — the claim is contradicted, inadmissible (e.g. "the code corrected the error"), or the request violates policy (e.g. IonQ hardware, 50 000 shots).
- **ESCALATE** — inconclusive or human required: too few shots, missing owner authorization, a circuit that cannot distinguish the hypotheses, or an offline record whose origin cannot be checked.
- **FREEZE** — evidence integrity failure: edited counts, physically impossible outcomes, missing data, stale records, or fault information leaking to the decision-maker.

## Statistics
Claims are about observable syndrome rates. The governor uses exact one-sided 95 % Clopper–Pearson
bounds: package A tests "nontrivial-syndrome rate ≤ 0.01"; package B tests "XXXX syndrome rate within
[0.15, 0.25]" with two one-sided tests. Failing to reject is never reported as support. Exact operating
characteristics at 2000 shots: worst-case false-accept ≤ 0.05; for B, P(ACCEPT) ≈ 0.9999 when the true
rate is 0.2 — likely, not guaranteed. The page always shows the verdict actually computed in the Run.

## What was actually executed in Qollab
On Qollab's built-in ideal simulator (2000 shots, one recorded backend job each):
- Clean-state control: 0 of 2000 shots with a nontrivial syndrome → ACCEPT, verifier VERIFIED.
- Synthetic phase fault: 413 of 2000 shots flagged by XXXX, 0 by ZZZZ; one-sided bounds [0.1917, 0.2220] → ACCEPT, verifier VERIFIED.
(Earlier R1 runs: 0/2000 and 420/2000.) Nothing was run on IonQ hardware or the IonQ cloud simulator.

## Scientific limitations
The [[4,2,2]] code detects single-qubit faults but cannot locate or correct them; logical errors such as
XXII are syndrome-silent, so a clean syndrome does not prove that no error occurred. An ideal simulator is
not hardware. The synthetic fault is injected with a known probability, so measuring it demonstrates the
evidence chain, not a discovery. A SHA-256 hash shows that text was not changed, not who produced it;
physically plausible forgeries pass physics checks. The backend advertises seed support, but seeded
replay was not demonstrated. No fault tolerance, hardware fidelity or quantum advantage is claimed. The
governor is deterministic research-policy software, not an autonomous AI scientist.

## What is original — and what is not
**Established science (cited):** the [[4,2,2]] code (Vaidman–Goldenberg–Wiesner 1996; Grassl–Beth–Pellizzari
1997), the stabilizer formalism (Gottesman; Calderbank–Rains–Shor–Sloane), detection vs correction
(Knill–Laflamme), trapped-ion and superconducting demonstrations (Linke et al. 2017; Takita et al. 2017;
Harper–Flammia 2019), Clopper–Pearson (1934) and TOST (Schuirmann 1987).
**Our contribution (built during the hackathon window):** the governance layer — circuit-derived claim
admissibility, a physics-derived claim ceiling, the four-verdict decision with explicit statistical
meaning, blinding of synthetic-fault data from the decision-maker, a parity-based plausibility check, an
independent standard-library verifier, verbatim evidence export, and the six-scene interactive explanation.
No new quantum algorithm is claimed.

## AI use and prior work
Code, tests and documentation were written during the hackathon window with an AI coding assistant
(Anthropic Claude via Claude Code) under the team's direction and review. The project is a clean-room
educational implementation inspired by the team's research-governance approach; it contains no code from
other projects. Qiskit (Apache-2.0) is used through Qollab. No third-party JavaScript libraries.

## Reproduce
Source (MIT): **[GitHub URL — to be added]** · Demo video: **[public video URL — to be added]**
`pip install -r requirements.txt`, `pytest -q`, `node --test tests/js/*.test.mjs`, and
`python verifier/verify_qrg.py evidence.json` for any copied evidence record. `scripts/build_packages_r2.py`
rebuilds the exact Qollab ZIPs (SHA-256 published in the repository).
