# Demo video script — 2:30 target (hard limits 2:00–3:00)

**Rules for recording**
- Record a **fresh Run** of the public Qollab project (package B, built-in simulator). Read every number
  **from the screen** — placeholders below are in [brackets]; never read a number from this script.
- Say "local" whenever a LOCAL demonstration is shown. Do not say "hardware", "IonQ device" or "proof".
- If the live verdict is not ACCEPT, narrate the verdict that is shown (the app is designed for that).
- Show real clicks: tabs, the counterfactual menu, Copy evidence.

| Time | Screen action | Narration |
|---|---|---|
| 0:00–0:15 | Project page, then press **Run**. Hold on the hero question while the status line shows "Running". | "A quantum computer has produced results. But which claims do those results actually justify? Quantum Research Governor answers that — live, with verifiable evidence." |
| 0:15–0:35 | Scene **A**. Point at hypothesis, backend, 2000-shot budget, claim, preflight ✓ list. Open the counterfactual menu, choose "Request: run on IonQ hardware", then "Circuit: ZZZZ check only". | "Before a single shot, the governor checks the proposal: authorized backend, budget, statistical power, and whether this circuit can even tell the claim apart from other explanations. These menu items are local previews — no quantum job. IonQ hardware isn't authorized here: rejected. A circuit without the XXXX check can't see phase errors: escalated." |
| 0:35–0:55 | Scene **B**. Trace the coloured stages: encode, orange synthetic fault, teal ZZZZ, purple XXXX. Point at the detection table rows ZIII and XXII. | "This is the real seven-qubit circuit. Four data qubits hold an encoded state of the four-two-two code. One ancilla asks a bit-flip question, ZZZZ; another asks a phase question, XXXX. A seventh qubit injects a labelled synthetic Z fault with probability 0.2. The code detects single faults, but cannot correct them — and some logical errors, like XXII, are completely silent." |
| 0:55–1:20 | Scene **C**. LIVE badge; read XXXX [k_X] of [n], ZZZZ [k_Z]; point at the bars. | "These counts came back from the backend in this Run. The XXXX check fired in [k_X] of [n] shots; ZZZZ in [k_Z]. A Z fault leaves every bit-string unchanged, so bit-parity alone would call this state clean. The intervals show the measurement uncertainty." |
| 1:20–1:45 | Scene **D**. Show both ✓ columns; click **Copy evidence JSON** (or Select all); point at the SHA-256. | "Now an independent witness. A separate verifier — standard library only — recomputes totals, decodes every syndrome, checks the parity invariant, recomputes the confidence bounds, the circuit and policy identity and the decision. The browser recomputes the SHA-256 of the exact evidence text, which anyone can copy and verify offline. Hashes show the record is intact — not who produced it." |
| 1:45–2:15 | Scene **E**. Live card with interval bar; scroll the REJECT, ESCALATE, FREEZE groups; pause on "Forged counts, hashes recomputed". | "The live verdict: [VERDICT]. The lower and upper bounds, [lo] to [hi], sit inside the claimed interval 0.15 to 0.25. Below are local demonstrations — none ran on the backend. Claims like 'the code corrected the error': REJECT. Too few shots or no owner sign-off: ESCALATE. Edited counts, impossible outcomes, or fault labels leaking to the governor: FREEZE." |
| 2:15–2:30 | Scene **F**; end on the title. | "And what we cannot claim: no correction, no hardware result, no proof that errors are absent, no quantum advantage. Quantum Research Governor: claims bounded by the evidence. This effort is supported by Qollab and IonQ." |

**Recording checklist**
1. Logged-out browser window on the public Qollab project URL; 1280–1440 px wide; zoom 100–110 %.
2. Close notifications; hide bookmarks; no private tabs or accounts visible.
3. Press Run on camera; wait for "Run complete · 1 backend job".
4. Fill the bracketed values from the screen while recording, or re-record narration afterwards.
5. Keep cursor movements slow; pause ~1 s on each verdict chip.
6. Export 1080p, check length 2:00–3:00, upload as **public/unlisted-with-link** (YouTube, Loom, Vimeo or Google Drive per rules) and test the link in a private window without signing in.
