# Scientific limitations (QRG-R1)

1. **Ideal simulator only.** Results are not evidence about physical hardware, noise or fidelity.
2. **Synthetic faults.** The Z fault in package B is injected by a controlled-Z from a fault-control
   qubit prepared with RY so that P(fault) = 0.2 *by construction*. Measuring the syndrome recovers
   a quantity we put in; the demonstration is the measurement and governance chain, not discovery.
3. **Detection, not correction.** [[4,2,2]] has distance 2: every single-qubit Pauli fault flips at
   least one syndrome, but faults cannot be located or corrected.
4. **Syndrome-silent faults exist.** Logical operators (e.g. XXII) commute with both stabilizers.
   A zero syndrome rate therefore says nothing about the total physical error rate. Claims about
   physical or logical error rates are refused by policy.
5. **What claims mean.** Every claim is stated about an observable syndrome probability per shot.
   Its reading as a fault rate holds only under the declared weight-1 Pauli fault model.
6. **Statistics.** Exact one-sided Clopper–Pearson bounds at α = 0.05, assuming i.i.d. shots.
   ACCEPT means the complementary hypothesis is rejected at level α; ESCALATE means neither side
   was rejected; failing to reject is never reported as support. Package B uses an equivalence
   (TOST) test on [0.15, 0.25]: "consistent with 0.2" is never claimed as "equals 0.2".
   Exact operating characteristics are in the project repository (`results/r1_calibration.json`).
   One governed claim per evidence record; no multiple-testing correction across claims.
7. **Four different properties, not interchangeable:**
   * *reproducibility* — exact seeded replay; **unavailable** in packages A/B by design (no seed).
   * *evidence consistency* — hashes, totals, provenance fields, freshness, authorized circuit.
   * *physical plausibility* — outcomes possible under some Pauli fault on an ideal backend
     (sZ = data parity). **Plausible forgeries pass this check.**
   * *authenticated provenance* — **not established**: there are no signatures or keys. An exact
     simulator replay is not a signature either.
8. **Custody.** `custody = in_process` only means the verdict was computed in the same Run from the
   job result object. An offline record without replay is never ACCEPTed (`PROVENANCE_UNVERIFIED`).
9. Single-ancilla stabilizer extraction is not fault-tolerant.
