# ST-4 airflow refinement and structured modal assembly

The original Weight7a point-1 calculation now has 4 spatial grids.
The lowest-frequency error changes from 122.95% → 96.22% → 78.71% → 66.49%.
Mesh resolution contributes to the difference, but the latest refinement passes
only **5/12 component checks** at the unchanged 0.1% limit.
No complete archived root matches its printed precision. This remains a
conditional comparison, not a validated ST-4 family or recovered historical setup.

The same complete 32-interval cold public-API solve now takes
**29.54 s instead of 101.98 s**
(3.45× faster; 71.0% less elapsed time).
Its original request, matrix export, equations, mode count, shift and tolerances
are retained. These are individual measured runs, not a statistical benchmark.

## Physical comparison

The literal model, point weights, material distributions and zero Reference area
are unchanged. All runs use speed 120, density 1.0771417304, zero incidence and
sideslip, Earth gravity 9.81 toward −z, PG Mach zero, aerodynamic lag enabled,
fixed perturbation frame, 16 roots near 0 + 300i and a 1e-5 differentiation step.
Uniform requested interval counts include an additional mandatory weight station.
No historical node distribution or startup sidecar is available. The
[original pilot report](isae-st4-zero-area-airflow-20261103.md) retains the full
source/driver audit and declared setup limitations.

| Requested intervals | Descriptor dimension | Complete native solve, seconds | Peak RSS, MiB | Strict archived scalar matches |
|---:|---:|---:|---:|---:|
| 16 | 341 | 53.95 | 109.0 | 1/12 |
| 32 | 645 | 101.98 | 156.6 | 1/12 |
| 48 | 949 | 147.42 | 226.6 | 1/12 |
| 64 | 1253 | 55.44 | 276.9 | 1/12 |

The 16/32/48 runs use the retained pre-optimization assembly. Subsequent runs
use the new assembly; the separate identical 32-interval replay verifies its
matrix and modal equivalence. Earlier plans retain their original kernel pins
and the changed source file is preserved under the study's `before/` directory.

At the finest 64-interval grid:

| Archive ordinal | ASWING real, imaginary (/s) | OpenSwing real, imaginary (/s) | Real-component error | Imaginary-component error |
|---:|---|---|---:|---:|
| 1 | -24.82247, 5.876936 | -23.9771, 9.784753 | 3.4057% | 66.4941% |
| 2 | -4.444598, 101.9036 | -4.310029, 101.6643 | 3.0277% | 0.2349% |
| 3 | -3.494512, 187.8581 | -3.731216, 188.8101 | 6.7736% | 0.5068% |
| 4 | -8.33652, 355.7367 | -8.303538, 355.7596 | 0.3956% | 0.0064% |
| 5 | -394.8427, 0 | -397.3594, -9.616105e-13 | 0.6374% | 9.62e-13 /s absolute |
| 6 | -8.274898, 542.5079 | -8.262053, 541.0582 | 0.1552% | 0.2672% |

The sole passing scalar at each grid is the approximately zero imaginary
component of the real root. Four higher oscillatory frequencies differ by
0.0064–0.5068%; real-component errors span
0.1552–6.7736%. The lowest pair remains substantially
different. The archive itself changes that pair from complex at operating points
1 and 2 to two real roots at point 3; its small imaginary part is sensitive to
the balance of stiffness, inertia and damping. This does not excuse its error
or identify which historical setting or implemented term is responsible.

## Convergence and independent checks

All 128 saved left/right eigenvector checks pass by direct multiplication
of full A/M arrays, maximum infinity-norm backward error 1.79e-15
against 1e-8. The optimized 32-interval replay passes another 32 checks.
These verify the assembled eigenproblem, not physical or historical ASWING fidelity.
The first saved-only assessment exceeded its memory cap by retaining matrix lists
from successive grids. The verifier now discards those lists after each check;
the same saved results pass within the unchanged cap, without repeating solves.

For the 48→64 comparison:

| Archive ordinal | Real-component mesh change | Imaginary-component mesh change | Combined shape MAC |
|---:|---:|---:|---:|
| 1 | 0.8023% | 7.3371% | 0.99999532 |
| 2 | 0.3762% | 0.0073% | 0.99999670 |
| 3 | 0.7421% | 0.1397% | 0.99999679 |
| 4 | 0.0839% | 0.0353% | 0.99999912 |
| 5 | 0.2951% | Reference-zero absolute gate | 0.99996679 |
| 6 | 0.1389% | 0.0954% | 0.99999732 |

Relative changes use the finer-grid component; the reference-zero imaginary
component retains its printed-precision absolute gate. Cross-grid injective
complex proximity and direct archive assignments agree for all six tracked roots.
Shape MAC uses material-coordinate trapezoidal weights and linearly interpolated
scaled translations/rotations. This supports cross-grid correspondence; it is
not a mass metric or proof of native mode identity. All returned roots, including
negative-frequency and real roots, remain in the artifacts. No complete-spectrum
or branch-continuation claim is made.

## Implementation and delivery

`solve_modes` now uses the existing structured tangent for full-descriptor
Arnoldi: complete moving geometry/induced-flow derivatives, direct circulation
and local-motion derivatives, and supported grouping of mechanical columns.
Unsupported derivative blocks retain the full residual stencil. No influence
matrix is frozen while its geometry changes. The existing dense row scaling,
modal selection and left-vector recovery are retained, as is the sparse shifted
factorization inside Arnoldi. This does not claim end-to-end sparse storage.

The initial 16-interval assembly diagnostic gives maximum row-scaled A difference
5.51e-13, identical M, and root difference
5.34e-13. The complete cold 32-interval replay gives
row-scaled A/M differences 3.92e-16 /
0 and maximum scaled complex-root
difference 1.8e-12. Its peak RSS changes from
156.6 to 171.8 MiB;
the improvement is in elapsed time, not reduced peak memory.

All 35 distinct selected regression checks pass: 33 initially and two corrected
rechecks. The initial two failures were invalid new test requests (incompatible
interpolation/operator policies and a vacuum gravity field at the wrong API
level). The requests were corrected; no numerical acceptance limits changed.
Coverage includes loaded midpoint/source airflow pencils, lag on/off, source
vacuum, existing modal physics and published Arnoldi checks.

The actual offline browser uses the structured path and completes the original
16-interval case in 14.64 s, compared with the prior recorded 45.98 s.
All 16 roots agree with the original native reference within
5.18e-13 scaled complex difference (gate 2e-7).
Dimensional zero-area output, unavailable coefficients and byte-exact saved-project
reopening pass, with no page errors. This uses the development workbench;
production packaging is verified separately in the delivery receipt.

All numerical jobs run serially with one BLAS thread, 180-second time limits and
512 MiB address-space caps. Browser and packaging checks run after numerical jobs.
No native ASWING executable is available, no tolerance changed and no parameters
were fitted. Registered family counts and all broad partial requirements remain.
The next scientific work is finer-grid convergence and review of the documented
spanwise circulation discretization, retaining historical setup uncertainty.

Evidence: [assessment](../../artifacts/isae/st4-airflow-refinement-20261103/assessment.json),
[structured diagnostic](../../artifacts/isae/st4-airflow-refinement-20261103/structured-probe.json),
[cold replay](../../artifacts/isae/st4-airflow-refinement-20261103/optimized-n32/execution.json),
[browser](../../artifacts/isae/st4-airflow-refinement-20261103/browser.json),
[regressions](../../artifacts/isae/st4-airflow-refinement-20261103/tests.log),
[corrected requests](../../artifacts/isae/st4-airflow-refinement-20261103/tests-recheck.log).
