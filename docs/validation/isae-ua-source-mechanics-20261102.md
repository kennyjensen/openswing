# Source-formulation time solver: exact internal-load derivatives

Updated 2026-11-02. The source-formulation BDF solver now calculates the
internal-force, internal-moment and reaction columns of its Newton matrix
directly. The original complete residual still determines acceptance. Physical
equations, nonlinear tolerances, time grids and output sampling are unchanged.

This arose while preparing the next UA-1 stalled periodic comparison. A
six-step profile reproduced the retained loads and rates exactly and attributed
3.78 of 6.33 instrumented seconds to matrix construction. Those instrumented
times identify the work; the separate timings below measure performance.

## Mathematics and implementation

[Drela's steady description, Eqs. 18–20](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) defines the section load law used here. At fixed endpoint geometry, it is linear in
the physical internal loads. In local section axes they have the form

```
kappa = B (M + H N)
epsilon = D N + H^T kappa
```

The source compatibility equations map these through the average of the
endpoint transforms. The new derivative uses that same average; it does not
substitute the older midpoint-rotation law. Evaluating this linear load map
on its six basis directions gives the exact compliance columns, without a
perturbation step or a subtraction of nearly equal residuals. Material damping
depends on fixed geometry and motion, so it adds no internal-load derivative.
Nodal force balance, force couples, reactions and nonlinear hinge-law
derivatives retain their existing physical expressions.

The assembler inserts these sparse columns and recolors the remaining
geometry/velocity columns. Circulation and frame blocks keep their current
form. Geometry influences and the original residual are evaluated under the
same policies as before. Unsupported or uncaptured derivative contexts retain
the original finite-difference path. In particular, this does not enable the
old midpoint tangent helpers for source-formulation dynamics.

Changed implementation:
[mechanical derivatives](../../openswing/mechanical_tangent.py),
[time residual capture](../../openswing/time_integration.py), and
[structured assembly](../../openswing/structured_time.py).

## Checks and timing

All **13 focused tests pass**. The six new tests check two complete-residual
stencils, coupled section properties and offsets, nonlinear joints, damped
Euler/BDF2 assembly, reduced residual-call count, and both fallback paths.
The existing checks cover analytic unsteady lift, checkpoint continuation,
body-beam motion, preservation of older tangent guards, and a two-step Radau
oscillator with discrete-stage replay.

The performance comparison uses the same retained 40-step stalled-heave
segment, identical checkpoint and forcing, one BLAS thread, and three serial
runs of each matrix path. Runtime excludes Python import and result-file
writing. Each process has a 45-second cap.

| Quantity | Original differences | Direct source columns |
|---|---:|---:|
| Median solve time | 17.20 s | 15.38 s |
| Matrix-building residual evaluations | 612 | 450 |
| Matrix builds | 9 | 9 |
| Newton iterations | 230 | 230 |
| Accepted/rejected steps | 40 / 0 | 40 / 0 |

The median time reduction is **10.6%**, with **26.5% fewer matrix-building
residual evaluations**. This is a measured improvement for this segment,
not a claim about every aircraft or an ASWING executable timing comparison.
The disabled path reproduces the saved physical outputs exactly. The direct
path's largest difference is **2.552e-13** on the declared physical scales,
below the preregistered 1e-8 comparison limit. Both retain the original
normalized nonlinear residual limit of 1e-10.

## Browser and remaining scope

The actual built worker completed **16 steps / 17 unique states**, with no rejected steps. The maximum scaled retained-Python difference is **1.5675e-09**, below 2e-8. Both continuation boundaries preserve the physical BDF predecessors. This starts from a retained CPython checkpoint; it does not establish a new complete browser case or a cold-start comparison.

The original verifier exited 1 after the second successful solve because its deep equality check distinguished `-0` from `0` in an Euler angle. Both complete outputs and the failed driver are retained. A separate reader accepts signed zeros as equal finite physical values and keeps exact equality for every nonzero join value. Four focused reader tests pass. The reassessment performs no new solve and changes no physical accuracy limit.

An independent eight-cycle stall reference has been evaluated with DOP853 and
Radau. Both show persistent positive stall after settling and less than
0.00002% waveform change from cycle three to four. Four cycles are therefore
the planned production settling scope. That production periodic comparison
has not yet been run. Existing UA-1/UA-2 scientific pass counts remain scoped
to their retained studies; this optimization adds no native-ASWING comparisons.

Evidence is retained in
[`artifacts/isae/ua-time-source-mechanics-20261102`](../../artifacts/isae/ua-time-source-mechanics-20261102)
and
[`artifacts/isae/ua1-stall-periodic-preparation-20261102`](../../artifacts/isae/ua1-stall-periodic-preparation-20261102).
The [benchmark](../../scripts/benchmark-source-time-mechanics.py) and
[focused tests](../../tests/test_source_time_mechanical_tangent.py) are included
in the source distribution.

[Machine-readable report](isae-ua-source-mechanics-20261102.json).
