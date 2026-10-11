# Quantum Research Governor — {PKG_LABEL}
**Governing Quantum Experiments Through Verifiable Evidence** · AgentNOMOS Quantum Lab ·
Qollab × IonQ Quantum Hackathon 2026. **This effort is supported by Qollab & IonQ.**

> A quantum experiment produced measurements. Does the evidence actually justify the proposed conclusion?

**This package:** {PKG_TITLE} · governed claim `{PKG_CLAIM}`.
Private R2 build — not a submission.

## What one Run does
Pressing **Run** evaluates `main.js` once. It makes exactly **one** call into Python
(`qrg.js_api.run_experiment`), which submits exactly **one bare 7-qubit `QuantumCircuit`** to the
backend injected by Qollab — no seed, no retry, no fallback simulator. Every button, tab and menu on
the page is local presentation only and can never start another job.

| Scene | What you see |
|---|---|
| A · Proposal | hypothesis, backend, shot budget, claim, required checks, governor preflight; LOCAL counterfactual previews |
| B · Circuit | the executed circuit: 4 data qubits ([[4,2,2]] code), ZZZZ and XXXX check ancillas, synthetic-fault control qubit; depth and 2-qubit gates from the real circuit object; what each check can and cannot detect |
| C · Measurements | LIVE counts from this Run, syndrome rates with exact intervals |
| D · Witness | independent standard-library verifier + browser cross-check (SHA-256, totals, decoding, parity invariant); verbatim evidence JSON with copy fallback |
| E · Decision | the LIVE verdict with its confidence bounds, plus clearly labelled REJECT / ESCALATE / FREEZE demonstrations that never touch the backend |
| F · Limits | what the evidence cannot prove |

## How the decision works
The [[4,2,2]] code state |00⟩_L is checked by two ancilla-measured stabilizers, ZZZZ (bit flips) and
XXXX (phase flips, invisible to ordinary bit parity). The governor sees only syndrome and data bits —
never the injected-fault label or the fault-control qubit — and decides with exact one-sided 95%
Clopper–Pearson bounds:
ACCEPT (claim supported within its ceiling), REJECT (contradicted, inadmissible or policy-violating),
ESCALATE (inconclusive, needs a human, or the circuit cannot distinguish the hypotheses),
FREEZE (evidence integrity failure).

## Verify offline
Copy the evidence JSON from Scene D into `evidence.json`, then run
`python verifier/verify_qrg.py evidence.json` (Python standard library only).

## Limitations, disclosure, licence
`docs/SCIENTIFIC_LIMITATIONS.md` · `docs/DISCLOSURE.md` (AI assistance and prior work) · MIT `LICENSE`.
Ideal built-in simulator only; synthetic faults are labelled; detection is not correction; a clean
syndrome does not prove the absence of errors; hashes do not authenticate origin; no hardware,
fidelity, fault-tolerance or quantum-advantage claim.
