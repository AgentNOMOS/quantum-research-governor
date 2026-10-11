# AI and prior-work disclosure

**AI assistance.** Code, tests and documentation were drafted with an AI coding assistant
(Anthropic Claude, via Claude Code) under the direction of the AgentNOMOS Quantum Lab team.
Scientific choices and claims are subject to human owner review.

**Clean-room.** This is an independent educational implementation inspired by a research-
governance philosophy (hypothesis → cheapest discriminating experiment → evidence → independent
verification → claim ceiling). It contains no code from other AgentNOMOS systems and the original
governance software is not a quantum-native system.

**Prior work (the quantum science is established, not ours):**
* [[4,2,2]] error-detecting code: Vaidman, Goldenberg & Wiesner (1996); Grassl et al. (1997).
* Linke et al., "Fault-tolerant quantum error detection", Science Advances 3, e1701074 (2017) —
  trapped ions.
* Takita et al., PRL 119, 180501 (2017) — superconducting qubits; Harper & Flammia (2019) —
  logical randomized benchmarking in the [[4,2,2]] code space.
* Stabilizer witnesses: Tóth & Gühne (2005); direct fidelity estimation: Flammia & Liu (2011).
* Clopper & Pearson (1934) exact binomial bounds; Schuirmann (1987) two one-sided tests (TOST).

**Our contribution** is the governance integration: circuit-derived claim admissibility,
physics-derived claim ceiling, explicit blinding of fault data, a physics-model plausibility check,
and an independent verifier — demonstrated on an ideal simulator only.

**Interface.** The R2 browser interface (index.html, main.js, main.css, ui/*.js) is original code
written for this project; it uses no third-party JavaScript libraries. SHA-256 in the browser is a
small self-contained implementation of FIPS 180-4.

**Software:** Qiskit (Apache-2.0), used through the Qollab-provided runtime.
