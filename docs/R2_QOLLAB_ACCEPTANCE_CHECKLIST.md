# QRG-R2 — real Qollab acceptance checklist (owner)

Local tests used a MOCKED bridge; only this checklist establishes browser compatibility.
Run package A and package B in two separate private Qollab projects, built-in simulator only.

1. Upload the ZIP, select the built-in simulator (not IonQ), press **Run** once.
2. Status line reads `Run complete · 1 backend job · governor verdict … · verifier VERIFIED`.
3. Hero card shows a LIVE verdict (expected: ACCEPT for A and, with ~99.99 % probability, for B).
4. Scene B shows 7 wires; depth 11 (incl. measurement) / 10, two-qubit gates 11 (A) or 12 (B).
5. Scene C shows LIVE counts that sum to 2000; A: only 0000000/0001111; B: four bitstrings, sZ = 0.
6. Scene D: every check ✓ in both columns; the browser SHA-256 matches the declared one.
7. Scene D: press **Copy evidence JSON**; note which message appears (clipboard / fallback / manual).
   Paste into `evidence.json` and run `python verifier/verify_qrg.py evidence.json` → `VERIFIED`.
8. Scene E: one LIVE card; REJECT, ESCALATE and FREEZE groups all say "no quantum job" / "copy";
   note says SHA-256 before and after: identical.
9. Click every tab, Previous/Next, the counterfactual menu and both buttons. The page must not
   start another job (Qollab job count / console should show a single run).
10. Narrow the window (or use a phone): no horizontal page scrolling.
11. Report back: status line, `backend` name/class (Scene A), raw counts (Scene C), copy-button
    message, and the evidence SHA-256.
