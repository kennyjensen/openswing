# UA-1/UA-2 arc quadrature precision and expanded runtime checks

**4/4 short Python/browser comparisons pass**, including local nodal motion and structural resultants. The previous 0.000285 m/s² spanwise acceleration discrepancy is removed in the retained UA-1 replays. Fresh UA-1 and UA-2 starts also satisfy the independent rigid-wing condition of zero local motion within the declared 2e-8 physical-unit gate. These are eight-step checks, not full periodic cases.

The material arc uses Gauss quadrature of the analytic axis-derivative norm. The old batched dot product returned straight lengths one or two ULPs too large even when every sampled norm was exactly one. Small resulting strain/position errors became visible after BDF differentiation. A new analytic straight-axis test reproduces all four interval errors before the correction.

The implementation now integrates a constant baseline separately and applies the same Gauss weights to the remaining variation. The baseline is the smallest sampled derivative norm, so the remaining samples are nonnegative. This preserves the rule’s exact constant moment and avoids cancellation for strongly varying derivatives. It changes numerical evaluation, not the physical arc integral, quadrature order, refinement criteria, physical model or default tolerances.

| Short history | Python seconds | Browser seconds | Largest scaled difference | Result |
|---|---:|---:|---:|---|
| replay-requested | 3.59 | 5.59 | 3.331e-16 | Pass |
| replay-tight | 5.28 | 4.73 | 3.331e-16 | Pass |
| cold-UA1 | 4.34 | 5.24 | 1.701e-12 | Pass |
| cold-UA2 | 8.85 | 9.32 | 1.222e-09 | Pass |

The expanded 2e-8 runtime gate covers aerodynamic forces, span-scaled moments, pressure drag, section lift, circulation and its rate, all reported frame components, nodal positions/rotations, local velocities/rates/accelerations, internal forces/moments and support reactions. Structural moments use qS times span; other scalar comparisons use max(1, abs(expected)) in their stated units. Every scalar is checked for finite values. All 32 browser steps converge without rejection; all 136 loaded solver modules match their frozen source hashes. Accepted BDF predecessors are checked against the retained raw states.

The old-checkpoint replays retain earlier normal-motion errors in their initial history; importing a checkpoint does not silently replace that history with a new equilibrium. The independent zero-local-motion test therefore applies to the two fresh starts. Each runtime initializes those starts itself, with the original full forcing table and an eight-step duration.

| Fresh start | Largest Python local acceleration (m/s²) | Largest browser local acceleration (m/s²) |
|---|---:|---:|
| cold-UA1 | 7.533e-17 | 6.344e-17 |
| cold-UA2 | 1.698e-23 | 1.625e-23 |

**72 focused tests pass:** 10 constant/zero-width arc checks; 19 analytical, independent-quadrature and inverse-map checks including Daedalus; 35 source arc/strain/identity checks; and eight frozen historical mesh, deformation and warm-equilibrium compatibility checks. The original failing straight-axis test is preserved. Legacy mesh recipes and their immutable saved fixtures remain unchanged.

**Remaining:** complete current-source UA-1 stalled periodic verification, current-source UA-2 periodic revalidation and stall coverage, broader physical conditions and independently attributable native-ASWING outputs. No full-case score is incremented by these short studies. The overall ASWING implementation goal remains incomplete.

[Machine-readable report](isae-ua-arc-precision-20261103.json). [Raw evidence](../../artifacts/isae/ua-arc-precision-20261102). [Preceding solver-refinement report](isae-ua-time-refinement-20261102.md).
