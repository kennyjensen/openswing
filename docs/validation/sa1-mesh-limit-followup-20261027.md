# SA-1: finer-mesh convergence and quarter-chord invariance

**SA-1 remains 19/154 registered archived-output checks passing.** The original
22 baseline jobs are complete. A further 22 diagnostic solves at 800 and 1,600
intervals all converged, but the high-angle lift discrepancy remains about
2.67%. No production equation, model, acceptance tolerance or registered
denominator changed.

## What the refinement establishes

The [fixed protocol](../../artifacts/isae/sa1-mesh-limit-r2-20261027/protocol.json)
extends the existing cosine, pointwise discretization to two finer levels. It
keeps the original eleven angles, current wind-aligned influences, source model,
section law and Newton/Armijo policy from the
[preceding angle-sequence study](sa1-alpha-continuation-followup-20261027.md).
Each mesh starts independently from zero circulation at zero incidence, then
visits the original angles in order. No parameters or conventions are selected
by agreement with native outputs.

| Intervals | CL at 1.9971 degrees | CL at 18.091 degrees | CDi at 18.091 degrees |
|---:|---:|---:|---:|
| 200 | 0.144881031987 | 1.050230824802 | 0.064091930438 |
| 400 | 0.144881032405 | 1.050234204274 | 0.064092182069 |
| 800 | 0.144881032509 | 1.050235049176 | 0.064092244983 |
| 1,600 | 0.144881032535 | 1.050235260403 | 0.064092260711 |
| Archived ASWING | 0.144797 | 1.07903 | 0.0672406 |

At 18.091 degrees, the successive CL changes are 3.37947e-6, 8.44902e-7
and 2.11227e-7. The last observed order is 1.999986. The last change is only
7.34e-6 of the remaining native CL difference, 0.02879474. CDi similarly
shows observed order 1.999969 while retaining a 0.00314834 native difference.
This strongly disfavors insufficient resolution of this particular current
discretization as the explanation for those discrepancies.

The [complete refinement assessment](../../artifacts/isae/sa1-mesh-limit-r2-20261027/refinement-summary.json)
retains all eleven rows and seven outputs. Its Richardson limits are empirical
estimates, not certified continuum bounds or additional acceptance passes.
Order estimates are withheld for opposite-sign changes or changes at/below a
predeclared 1e-10 normalized reporting floor. This reporting filter changes no
solver or native-output tolerance. In particular, the finest attached CL change
is below that reporting floor; its native difference still exceeds 8.40e-5.

## Geometry and verification

The [first geometry attempt](../../artifacts/isae/sa1-mesh-limit-20261027/geometry-process-receipt.json)
stopped at the application's 512-interval input limit, before any aerodynamic
operator, residual or nonlinear solve. Its log and failure receipt are retained.
The revised isolated geometry process temporarily allows exactly the integers
800 and 1,600 through that count guard, delegates every other input to the
original guard, and restores it in `finally`. It uses the unchanged geometry
recipe; no production file or application limit is modified.

The [geometry receipt](../../artifacts/isae/sa1-mesh-limit-r2-20261027/geometry-process-receipt.json)
records exact equality of generated 200/400 metadata, sample coordinates,
lengths and positions with the previously saved states. The actual sample
coordinates are retained at every resolution. Parser/geometry dependency
imports are disclosed separately; this process performs no aerodynamic solve.

The [completed numerical run](../../artifacts/isae/sa1-mesh-limit-r2-20261027/summary.json)
used 72 Newton corrections for its 22 targets. All accepted full steps; there
were no failed targets or backtracking trials. The maximum independently
recomputed normalized residual is 5.25e-12, below the unchanged 1e-11 gate.

The [independent checker](../../artifacts/isae/sa1-mesh-limit-r2-20261027/verification.json)
rebuilds both operators with scalar arithmetic, replays all 94 accepted iterate
records and 72 line-search trials, and reconstructs the integrated coefficients.
It enforces all 96 declared centered derivative checks, including zero states,
and performs 88 complex-step directional checks. Maximum normalized coefficient
replay difference is 4.45e-16; maximum relative complex-step difference is
2.17e-14. It performs no nonlinear solves and imports no production modules.

## Another source ambiguity excluded for this wing

The [quarter-chord translation proof](sa1-quarter-chord-translation-20261027.md)
examines the physical and wind-aligned quarter-chord descriptions in the source
papers. For this straight, constant-chord wing, consistently changing all bound
endpoints, force receivers and control points is a common translation. Every
receiver-to-vortex difference, influence coefficient and circulation residual
remains identical. The existing physical quarter-chord moment arm is a separate
definition and also remains unchanged. Moving a receiver alone would be a
different, unsupported convention.

The study does not recover the historical node layout, load recovery, startup
settings or executable stall constants. It establishes no production correction.
Further refinement of this same mesh family is unlikely to resolve SA-1; the
remaining work needs evidence distinguishing those historical choices from the
published-equation implementation. The exact 19/154 baseline remains intact.
