# QRG-R0 Governance Policy

Policy id `QRG-R0-POLICY` v0.1.0 — sha256 (policy + vocabulary + ceiling)
`fbb7d305b08873b987714f900484e8c8b2c2251873b26fac9082adbb166ce7b1`. Source: `qrg/policy.py`.

## Inputs
**Proposal**: experiment_id, nonce, hypothesis (text), claim {type, params}, variant
(authorized skeleton), backend, shots, seed, owner_authorization.
**Evidence record** (`qrg.evidence.v1`): experiment_id, nonce, backend, shots, seed,
skeleton_sha256, fault_commitment (sealed), created_at, counts, counts_sha256, record_sha256.
**Replay witness**: counts_sha256 of an independent seeded re-execution.
**Decision clock**: `now` is an explicit input (no clock reads → deterministic).

## Parameters
| key | value | meaning |
|---|---|---|
| alpha | 0.05 | one-sided Clopper–Pearson level |
| permitted_backends | basic_simulator | everything else REJECT |
| max_shots_per_run | 20000 | REJECT above |
| budget_units | 50000 | 1 unit / shot, cumulative |
| auto_approve_shots | 4096 | above → owner authorization or ESCALATE |
| max_evidence_age_s | 3600 | freshness window |
| min_event_separation | 1.0 | event must identify the fault class exactly |
| max_out_of_model_fraction | 0.0 (ideal) | physics invariant tolerance |
| require_replay_backends | basic_simulator | seeded replay required |

Owner authorization in R0 is a demo string `OWNER-APPROVED:<experiment_id>:<nonce>` —
**not cryptographic** (no keys exist in this project).

## Claim vocabulary (admissible)
| claim | event | direction | claim hyps vs competitors |
|---|---|---|---|
| CODE_SPACE_PRESERVED(eps) | sZ or sX | rate ≤ eps | clean vs all 12 weight-1 |
| PHASE_ERROR_PRESENT(rho) | sX | rate ≥ rho | Z_k,Y_k vs clean,X_k |
| BIT_FLIP_PRESENT(rho) | sZ | rate ≥ rho | X_k,Y_k vs clean,Z_k |

## Claim ceiling (always REJECT, never executed)
ERROR_LOCATED · ERROR_CORRECTED · NO_ERROR_OCCURRED · LOGICAL_STATE_INTACT ·
HARDWARE_FIDELITY · FAULT_TOLERANT · QUANTUM_ADVANTAGE — each with a physical reason in
`CEILING`. Unknown types → REJECT `CLAIM_NOT_IN_VOCABULARY`.

## Pipeline
1. **preflight** (before spending budget): claim admissible → backend → variant → shot limit →
   budget → owner authorization → *discriminability computed from the circuit* → statistical
   power. Output `CLEARED_TO_EXECUTE` or a verdict. REJECT is never executed.
2. **evaluate**: static checks again, then evidence complete → schema → digests → well-formed
   counts → shots reconcile → provenance (id, nonce, backend) → freshness → authorized skeleton
   → physics invariant → replay.
3. If every structural check passes: statistics decide ACCEPT / REJECT / ESCALATE.

Precedence among failed structural checks: **FREEZE > REJECT > ESCALATE**.

## Verdict semantics
| verdict | meaning | codes |
|---|---|---|
| ACCEPT | evidence supports exactly the stated claim within the stated ceiling | SUPPORTED |
| REJECT | contradicted, inadmissible, or policy violation | CONTRADICTED_BY_EVIDENCE, CLAIM_EXCEEDS_CEILING, CLAIM_NOT_IN_VOCABULARY, MALFORMED_CLAIM, UNAUTHORIZED_BACKEND, UNAUTHORIZED_CIRCUIT, SHOT_LIMIT_EXCEEDED, BUDGET_EXCEEDED |
| ESCALATE | inconclusive or human required; includes recommendation | INCONCLUSIVE, UNDERPOWERED, NON_DISCRIMINATING, HUMAN_AUTHORIZATION_REQUIRED, REPLAY_REQUIRED |
| FREEZE | integrity / reproducibility failure; no conclusion is defensible | MISSING_EVIDENCE, SCHEMA_MISMATCH, DIGEST_MISMATCH, MALFORMED_COUNTS, SHOT_COUNT_MISMATCH, PROVENANCE_MISMATCH, STALE_EVIDENCE, SKELETON_MISMATCH, PHYSICS_MODEL_VIOLATION, REPLAY_MISMATCH |

Every ACCEPT carries a `claim_ceiling` block listing what is **not** established.

## False-accept / false-reject analysis
* **Statistical**: each decision has false-accept ≤ α and false-reject ≤ α under the model
  (Monte Carlo: 0/200 and 1/200). There is no multiple-testing control across repeated
  claims on the same data — one claim per evidence record is a policy assumption (open).
* **Model**: guarantees hold for the declared weight-1 Pauli model on an ideal backend. A
  weight-2 logical fault (S24) is correctly reported as "code space preserved" — the claim is
  true, and NO_ERROR_OCCURRED is refused by the ceiling.
* **Integrity**: digests catch naive edits; the physics invariant catches impossible forgeries;
  seeded replay catches plausible forgeries. A dishonest *executor* who also controls replay is
  **not** detected in R0 (needs independent execution or signed hardware results).
* **False reject**: valid evidence older than 1 h is FROZEN; a missing replay ESCALATEs. These
  are deliberate conservative trade-offs.
