# QRG-R1 Scientific Claim Audit (2026-10-10)

Scope: re-examine every R0 ACCEPT/REJECT for its exact assumptions, then fix what overstated.

## Findings on R0
| # | finding | severity | R1 action |
|---|---|---|---|
| F1 | `CODE_SPACE_PRESERVED` names a physical property; the observable is only the nontrivial-syndrome probability per shot | medium (wording overclaim) | New `DETECTED_SYNDROME_RATE_AT_MOST`; each R1 claim carries an *observable* statement and a separate *model-conditional* reading. R0 names kept only for R0 compatibility. |
| F2 | R0 fault commitment used a fixed public salt (`r0-demo-salt`) over a tiny fault space → the label was recoverable by brute force from the record. The R0 governor never read it, but the record was not blind. | medium (blinding) | Random salt per run; commitment, salt, label and coin bit live only in `audit_only`; governor consumes a separate 6-bit `governor view` (schema + tests). |
| F3 | R0 Monte Carlo (200 runs) was presented next to guarantees | low | Exact operating characteristics by binomial summation (`results/r1_calibration.json`); the Monte Carlo is labelled empirical. |
| F4 | R0 required seeded replay; Qollab seed support is unverified | medium (deployability) | Replay optional; ACCEPT requires in-process custody **or** matched replay; offline records without replay → ESCALATE `PROVENANCE_UNVERIFIED`. |
| F5 | "Compare with 0.2" invites "consistent ⇒ equals 0.2" (failure-to-reject misuse) | medium | Package B governs an equivalence claim (TOST) on the predeclared interval [0.15, 0.25]; the 0.2 comparison is descriptive and labelled non-confirmatory; `FAULT_PROBABILITY_EQUALS` is refused. |
| F6 | Physical / logical error-rate claims were not explicitly refused | medium | Added to ceiling: `PHYSICAL_ERROR_RATE_AT_MOST`, `NO_PHYSICAL_ERROR`, `LOGICAL_ERROR_RATE_AT_MOST`, `FAULT_PROBABILITY_EQUALS`. |
| F7 | Backend authorization by name only | low | Name or exact class allowlist, plus deny-substrings (ionq/qpu/forte/aria/harmony/tempo) checked on name **and** class; refusal before any job. |
| F8 | "No fault" was labelled `p = 1.0` in records | cosmetic | Labelled `p = 0.0`. |

## Assumptions behind each decision type
| decision | statistical meaning | assumptions |
|---|---|---|
| ACCEPT at_most ε | one-sided CP upper bound ≤ ε ⇒ "rate > ε" rejected at α | i.i.d. shots; counts authentic (in-process custody); for the fault-rate reading: weight-1 Pauli model |
| ACCEPT at_least ρ | lower bound ≥ ρ ⇒ "rate < ρ" rejected at α | same |
| ACCEPT within [lo, hi] | TOST: both one-sided level-α tests reject ⇒ size ≤ α | same |
| REJECT (statistical) | the claim itself is rejected at level α (bound on the wrong side) — a positive rejection, not a failure to support | same |
| ESCALATE (INCONCLUSIVE) | neither side rejected; never reported as support or refutation | — |
| REJECT (ceiling) | claim inadmissible for this experiment regardless of data — not a statement that it is false | physics of distance-2 detection |
| FREEZE | no conclusion drawn; evidence integrity/consistency failure | — |

R0 scenario re-check: S01/S02/S03/S21/S24 ACCEPTs are valid statements about syndrome rates; S24
(logical XXII) is the canonical example that the *observable* claim is true while the physical
state is wrong — exactly why physical-error claims are refused. S04/S05 REJECTs are positive
rejections (bound on the wrong side). No R0 decision used failure-to-reject as support.

## Exact operating characteristics (n = 2000, α = 0.05)
| package | rule | false accept (worst case, at boundary) | false reject (worst, at boundary) | P(ACCEPT) at design point |
|---|---|---|---|---|
| A: rate ≤ 0.01 | ACCEPT iff k ≤ 12; REJECT iff k ≥ 29 | 0.0383 (p → 0.01⁺) | 0.0336 (p = 0.01) | 1.0 at p = 0 |
| B: 0.15 ≤ rate ≤ 0.25 | ACCEPT iff 327 ≤ k ≤ 467 | 0.0497 / 0.0459 | 0.0472 / 0.0474 | 0.99988 at p = 0.2 |

R0 Monte Carlo vs exact (n = 400, ρ = 0.10): p = 0.08 exact P(ACCEPT) = 0.0007, P(REJECT) = 0.330
(observed 0/200, 77/200); p = 0.13 exact P(ACCEPT) = 0.581, P(REJECT) = 0.0002 (observed 121/200,
1/200). The observations are consistent with the exact values; only the exact values are bounds.

## Four properties that are NOT interchangeable
| property | how checked | in packages A/B |
|---|---|---|
| reproducibility | exact seeded replay (package C, two separate Runs) | UNAVAILABLE by design |
| evidence consistency | digests, totals, provenance fields, freshness, skeleton hash, view = marginal of raw | checked |
| physical plausibility | sZ = data parity; sX = 0 if XXXX unmeasured (ideal backend) | checked — **plausible forgeries pass** |
| authenticated provenance | would need signatures / trusted execution | **NOT ESTABLISHED** |

A matching exact replay is not a signature: anyone controlling both runs can make them agree.
