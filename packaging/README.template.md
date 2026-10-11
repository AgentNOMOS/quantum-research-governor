# Quantum Research Governor — R1 smoke test, {PKG_LABEL}
**Governing Quantum Experiments Through Verifiable Evidence** · AgentNOMOS Quantum Lab ·
Qollab × IonQ Quantum Hackathon 2026. This effort is supported by Qollab & IonQ.

> A quantum experiment has produced evidence. Can we trust the conclusion?

**This package:** {PKG_TITLE}
**Governed claim:** `{PKG_CLAIM}`

Status: private R1 smoke test. Ideal built-in simulator only. Not a submission.

## What happens when you press Run
1. `main.py` takes the `backend` object injected by Qollab. It never creates a simulator of its
   own; without an injected backend it stops with `ERROR_NO_INJECTED_BACKEND`.
2. A deterministic **preflight** checks claim, backend (IonQ / hardware names are refused),
   shot limit, budget, authorization, circuit discriminability and statistical power.
   A refused preflight submits **zero** jobs.
3. Exactly **one bare `QuantumCircuit`** (7 qubits) goes to `backend.run` — no seed, no retry.
   [[4,2,2]] code state |00⟩_L on q0–q3; ancilla q4 measures ZZZZ, ancilla q5 measures XXXX;
   q6 is a fault-control qubit whose outcome is **audit-only**.
4. The raw counts are split into a **governor view** (syndromes + data bits only) and an
   **audit-only** section (fault label, control-qubit outcome, sealed commitment).
5. The governor decides ACCEPT / REJECT / ESCALATE / FREEZE from the view only.
6. An **independent verifier** (`verifier/verify_qrg.py`, standard library only) recomputes
   totals, syndromes, confidence bounds, circuit compatibility, the policy decision and
   integrity, without trusting any stored PASS value.
7. The console ends with one line `QRG_BUNDLE_JSON {...}` holding the full evidence. Copy it into a
   file and run `python verifier/verify_qrg.py file.txt` to re-verify offline.

## Statuses
`COMPLETED` · `PREFLIGHT_REJECT` / `PREFLIGHT_ESCALATE` (no job) · `SEED_REPLAY_UNAVAILABLE` (no job) ·
`JOB_FAILED` (not retried) · `ERROR_NO_INJECTED_BACKEND` (no job).

## Scientific limitations
See `docs/SCIENTIFIC_LIMITATIONS.md`. In short: ideal simulator ≠ hardware; faults are labelled
synthetic injections; the [[4,2,2]] code detects but does not correct; a zero syndrome rate does
not prove the absence of physical errors (logical faults such as XXII are syndrome-silent);
hashes bind content but do not authenticate origin.

## Disclosure
AI assistance and prior work: `docs/DISCLOSURE.md`. License: MIT (`LICENSE`).
