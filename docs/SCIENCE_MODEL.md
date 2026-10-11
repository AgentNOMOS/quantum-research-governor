# QRG-R0 Science Model

## 1. Quantum primitive: [[4,2,2]] error-detecting code
* 4 data qubits encode 2 logical qubits; stabilizers **S_X = XXXX**, **S_Z = ZZZZ**; distance 2.
* Logical operators (one standard choice): X̄₁=XXII, Z̄₁=ZIZI, X̄₂=XIXI, Z̄₂=ZZII.
* Prepared state: |00⟩_L = (|0000⟩+|1111⟩)/√2 (H, then 3 CNOTs) — +1 eigenstate of both stabilizers.
* Any single-qubit Pauli anticommutes with at least one stabilizer → **detected**, but every
  qubit gives the same syndrome → **not locatable, not correctable** (distance 2).
* Weight-2 Paulis that are logical operators (e.g. XXII) commute with both stabilizers →
  **syndrome-silent**.

Why this is quantum-specific: a Z (phase) error leaves every computational-basis bit string
unchanged in distribution (Z₂|00⟩_L = (|0000⟩−|1111⟩)/√2). Only the XXXX stabilizer, measured
coherently through an ancilla, can see it. A classical parity checker on readout bits (our
`z_only` variant) is provably blind to it — this is demonstrated, not asserted (S22/S23).

## 2. Circuit (one circuit, one job)
Qubits: q0–q3 data · q4 ZZZZ ancilla (bit sZ) · q5 XXXX ancilla (bit sX) · q6 fault coin
(**audit-only**, inadmissible). Everything is measured once at the end (no mid-circuit
measurement, no classical feed-forward).

```
encode:   H q0; CX q0→q1, q0→q2, q0→q3
fault:    [labelled synthetic layer; sealed from the governor]
extract:  CX q0..q3 → q4                      (ZZZZ → sZ)
          H q5; CX q5 → q0..q3; H q5          (XXXX → sX)   [omitted in z_only]
measure:  all 7 qubits → c0..c6
```
Full diagrams: `results/circuits.txt`.

| circuit | qubits | depth (excl. measure) | 2-qubit gates | gates |
|---|---|---|---|---|
| full, no fault | 7 (6 used) | 10 | 11 CX | 3 H |
| full + stochastic fault | 7 | 10 | 11 CX + 1 CZ | 3 H, 1 RY |
| z_only | 7 (5 used) | 8 | 7 CX | 1 H |

Measurement basis: computational (Z) basis on all qubits; the X-type stabilizer is mapped to
the Z basis of q5 by the H–CX–H ancilla gadget. Qiskit key order: `c6 c5 c4 c3 c2 c1 c0`
= `coin sX sZ d3 d2 d1 d0`.

## 3. Synthetic fault layer (LABELLED — not hardware noise)
* deterministic: Pauli string `pattern` (pattern[k] acts on data qubit k).
* stochastic: RY(θ) on the coin, sin²(θ/2)=p, then coin-controlled Pauli string. Because the coin
  is measured at the end and never interferes again, the data experience the Pauli channel
  ρ → (1−p)ρ + pPρP. The coin bit is retained only for referee audit; the governor masks it.

## 4. Theoretical prediction (three independent derivations)
1. **Qiskit `Statevector`** of the built circuit.
2. **`qrg/witness_sim.py`**: 128-amplitude pure-Python statevector from the same IR, no Qiskit.
3. **Referee symplectic rule**: syndrome bit = parity of anticommuting positions.

Cross-checks (tests): (1)≡(2) on 32 circuits, max |Δp| = 5.3e-34; (2)≡(3) for all 256 Pauli
strings on both stabilizers.

| fault | sZ | sX | data readout |
|---|---|---|---|
| none | 0 | 0 | 0000 / 1111 (½ each) |
| X_k | 1 | 0 | single bit k flipped |
| Z_k | 0 | **1** | **unchanged** (0000/1111) |
| Y_k | 1 | 1 | bit k flipped |
| XXII (logical) | 0 | 0 | 0011 / 1100 — syndrome-silent |

## 5. Physics-model invariant (tamper witness)
For any Pauli fault (and any mixture) before ideal extraction, **sZ = parity(data bits)** on
every shot. The governor computes the union of supports over all 4⁴ data Pauli strings
(32 visible outcomes for `full`, 16 for `z_only`) with the independent simulator; on an ideal
backend any shot outside it is impossible → FREEZE. On real hardware readout/gate noise
violates it at some rate, so the tolerance must become a calibrated parameter (planned).

## 6. Statistics
* Each admissible claim is a statement about the **rate of a fault class**, tied to one
  syndrome event (ANY, sX, sZ). The governor first proves — from the circuit, exactly —
  that the event's probability is 1 under every claim hypothesis and 0 under every competing
  weight-1 hypothesis (separation = 1). Only then does event rate = fault-class rate.
* k events in n shots → exact one-sided Clopper–Pearson bounds at α = 0.05.
  * "rate ≤ ε": ACCEPT if U ≤ ε; REJECT if L > ε; else ESCALATE.
  * "rate ≥ ρ": ACCEPT if L ≥ ρ; REJECT if U < ρ; else ESCALATE.
* Meaning: ACCEPT ⇒ the complementary hypothesis is rejected at level α. Failing to
  reject is **never** reported as support; it is ESCALATE.
* Zero-event power: n ≥ ln α / ln(1−ε) (ε=1% ⇒ n ≥ 299). Preflight refuses underpowered runs.
* Shot noise is the only uncertainty source on the ideal simulator; seeds are fixed so every
  count in `results/` is reproducible.

### Error-rate evidence (Monte Carlo, real BasicSimulator runs, 400 shots, ρ = 0.10)
| true p | claim "≥0.10" is | ACCEPT | REJECT | ESCALATE |
|---|---|---|---|---|
| 0.08 (seeds 1000–1199) | false | **0/200** (false accept) | 77 | 123 |
| 0.13 (seeds 2000–2199) | true | 121 | **1/200** (false reject) | 78 |

Both error rates are under α = 0.05 per decision, as the construction guarantees. The cost is
a large ESCALATE band near the threshold: the governor buys a low false-accept rate with
indecision, which it reports.

## 7. What this experiment cannot establish
weight ≥ 2 faults · fault location · correction · logical phase errors on |00⟩_L (Z̄ act
trivially) · hardware fidelity · fault-tolerance (single-ancilla extraction is not FT; cf. the
flagged FT prep of Linke 2017 / Takita 2017) · any quantum advantage.
