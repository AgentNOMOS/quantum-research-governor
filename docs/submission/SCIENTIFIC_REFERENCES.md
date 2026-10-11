# Scientific references — Quantum Research Governor

Every entry below was checked on 2026-10-10 against Crossref metadata (DOI → title, authors, year,
journal, volume, pages) and/or the arXiv API (identifier → title, authors, date). These works
establish the **methods** QRG uses. None of them validates this particular software; correctness
of QRG is supported only by its own tests and by the evidence it records.

## [[4,2,2]] error-detecting code
1. L. Vaidman, L. Goldenberg, S. Wiesner, "Error prevention scheme with four particles,"
   *Phys. Rev. A* **54**, R1745–R1748 (1996). doi:10.1103/PhysRevA.54.R1745 · arXiv:quant-ph/9603031.
   — Four-particle encoding with detection (testing for leaving the code space) instead of correction.
2. M. Grassl, Th. Beth, T. Pellizzari, "Codes for the quantum erasure channel,"
   *Phys. Rev. A* **56**, 33–38 (1997). doi:10.1103/PhysRevA.56.33 · arXiv:quant-ph/9610042.
   — Four-qubit codes; four qubits suffice to protect against a known-position erasure.

## Stabilizer formalism and syndrome extraction
3. D. Gottesman, "Class of quantum error-correcting codes saturating the quantum Hamming bound,"
   *Phys. Rev. A* **54**, 1862–1868 (1996). doi:10.1103/PhysRevA.54.1862.
4. A. R. Calderbank, E. M. Rains, P. W. Shor, N. J. A. Sloane, "Quantum error correction and
   orthogonal geometry," *Phys. Rev. Lett.* **78**, 405–408 (1997). doi:10.1103/PhysRevLett.78.405.
5. D. Gottesman, *Stabilizer Codes and Quantum Error Correction*, Ph.D. thesis, Caltech (1997).
   arXiv:quant-ph/9705052.
6. M. A. Nielsen, I. L. Chuang, *Quantum Computation and Quantum Information*, 10th anniversary
   ed., Cambridge University Press (2010). doi:10.1017/CBO9780511976667.
   — Stabilizer codes, ancilla-based syndrome measurement, Pauli error model.

## Detection versus correction; code distance
7. E. Knill, R. Laflamme, "Theory of quantum error-correcting codes," *Phys. Rev. A* **55**,
   900–911 (1997). doi:10.1103/PhysRevA.55.900.
   — Conditions for correctability/detectability; a distance-d code detects up to d−1 errors and
   corrects ⌊(d−1)/2⌋. For [[4,2,2]] (d = 2): single-qubit errors detectable, not correctable.
8. D. Gottesman, "Quantum fault tolerance in small experiments," arXiv:1610.03507 (2016).
   — Proposes small-code ([[4,2,2]]-type) demonstrations and criteria for claiming fault tolerance.

## Experimental [[4,2,2]] demonstrations
9. N. M. Linke, M. Gutierrez, K. A. Landsman, C. Figgatt, S. Debnath, K. R. Brown, C. Monroe,
   "Fault-tolerant quantum error detection," *Sci. Adv.* **3**, e1701074 (2017).
   doi:10.1126/sciadv.1701074 · arXiv:1611.06946. — **Trapped ions.**
10. M. Takita, A. W. Cross, A. D. Córcoles, J. M. Chow, J. M. Gambetta, "Experimental demonstration
    of fault-tolerant state preparation with superconducting qubits," *Phys. Rev. Lett.* **119**,
    180501 (2017). doi:10.1103/PhysRevLett.119.180501 · arXiv:1705.09259.
11. R. Harper, S. T. Flammia, "Fault-tolerant logical gates in the IBM Quantum Experience,"
    *Phys. Rev. Lett.* **122**, 080504 (2019). doi:10.1103/PhysRevLett.122.080504 · arXiv:1806.02359.

## Statistics
12. C. J. Clopper, E. S. Pearson, "The use of confidence or fiducial limits illustrated in the case
    of the binomial," *Biometrika* **26**, 404–413 (1934). doi:10.1093/biomet/26.4.404.
    — Exact binomial confidence bounds (used one-sided at α = 0.05).
13. D. J. Schuirmann, "A comparison of the two one-sided tests procedure and the power approach for
    assessing the equivalence of average bioavailability," *J. Pharmacokinet. Biopharm.* **15**,
    657–680 (1987). doi:10.1007/BF01068419. — Two one-sided tests (TOST) for interval claims.

## Related verification methods (context, not used directly)
14. G. Tóth, O. Gühne, "Detecting genuine multipartite entanglement with two local measurements,"
    *Phys. Rev. Lett.* **94**, 060501 (2005). doi:10.1103/PhysRevLett.94.060501.
15. S. T. Flammia, Y.-K. Liu, "Direct fidelity estimation from few Pauli measurements,"
    *Phys. Rev. Lett.* **106**, 230501 (2011). doi:10.1103/PhysRevLett.106.230501.

## Software
16. A. Javadi-Abhari et al., "Quantum computing with Qiskit," arXiv:2405.08810 (2024).
    Qiskit 2.5.2 (Apache-2.0) is the circuit/simulator stack used through Qollab.

## What is established vs. what QRG adds
| Established (cited above) | QRG application-level integration (this project) |
|---|---|
| [[4,2,2]] code, stabilizers XXXX/ZZZZ, ancilla syndrome extraction | Claim admissibility computed from the circuit: can the measured syndrome even separate the claim from competing fault hypotheses? |
| Distance-2 codes detect but do not correct | A physics-derived **claim ceiling** that refuses location, correction, "no error", hardware and advantage claims |
| Clopper–Pearson bounds, TOST | Four-valued verdict ACCEPT / REJECT / ESCALATE / FREEZE with explicit statistical meaning |
| Stabilizer parity relations | Parity invariant (sZ = data parity) used as a physics-plausibility check on evidence records |
| — | Blinding of synthetic-fault information from the decision-maker; standard-library independent verifier; verbatim evidence export |

QRG introduces no new quantum algorithm or code.
