# Analytical source columns in time-step matrices

Date: 2026-11-04. Selected derivative, transient and offline browser checks pass.
The [structured record](source-time-mechanical-columns-20261104.json) retains
the source hashes, measurements and complete evidence inventory.

The accepted-step matrix now uses the existing source endpoint-average
constitutive derivatives for internal force, moment and reaction coordinates.
At fixed geometry and motion the section laws and nodal balances are linear
in these variables; hinge laws retain their existing analytical chain rule.
These variables do not enter time kinematics or circulation equations. Geometry,
motion, circulation and actuator columns retain their complete centered
finite-difference evaluations. Full matrix scaling, singular-value rank gates,
controller diagnostics and nonlinear/temporal tolerances are unchanged.

This follows the coupled residual/Jacobian formulation in the ASWING Unsteady
Technical Description, sections 11.3 and 12.2, equations 121–128. It reuses the
source derivative already checked for static and modal assembly. It introduces
no frozen aerodynamic terms or reduced physical equations. The rank matrix
remains dense; this is not a claim that the entire time solver has acquired
ASWING's original matrix implementation or performance.

Cold time-feedback initialization, BDF stepping/refinement and the ordinary
continuous Radau chart use the analytical block. Each Radau stage retains its
own current geometry and physical load block; internal-load rates have no
cross-stage contribution. Force/moment feedback retains the full stencil because
its measurement chain rule can depend on these coordinates. Custom operating
equations, unknown constitutive laws, unsupported charts and unsafe hinge
derivative branches retain the existing full calculation.

| Identical two-step profiled request | Before | After |
| --- | ---: | ---: |
| Elapsed seconds | 31.00646 | 24.03893 |
| Process CPU seconds | 29.17367 | 18.71188 |
| Full residual evaluations | 879 | 702 |
| Accepted-root matrices | 3 | 3 |

All three complete matrices (67×67, 109×109, 109×109) are exactly equal.
The complete output is also exactly equal after excluding only the root and
snapshot evaluation counters. Each of the three matrix builds replaces 60
full residual evaluations with one capture and the analytical 30-column block,
removing 177 evaluations overall. The observed elapsed/CPU reductions are
22.47%/35.86% on this one short profiled case, not a broad benchmark.

Thirty-three distinct Python checks pass, including fifteen new checks:
six full-residual derivative/coupling/fallback checks
and nine original independent controller-authority/trajectory cases run under
the source equations. The derivative checks cover loaded moving geometry,
material damping, both BDF orders, all three Radau stages and circulation
feedback. Force/moment feedback demonstrably retains nonzero mechanical
couplings. An injected unavailable derivative restores the identical full rank
matrix. The remaining eighteen checks cover nine existing controller-authority
cases, eight existing Radau cases and the original full free-frame refinement.
Two regression batches reached their execution caps after eight and seven
completed checks; their unfinished cases passed in subsequent serial jobs.

The full free-frame test passes the independent equation
`3 q'' + 10 q' + 310 q = command`, including both frequency samples and both
time histories through 0.08 seconds. Its original acceptance gates, mesh,
forcing and duration are unchanged. The complete test takes 330.99 seconds
including pytest startup; this is a single recorded run, not a controlled
performance comparison with earlier test runs.

| Time step | Accepted steps | Maximum normalized trajectory error | Maximum residual |
| --- | ---: | ---: | ---: |
| 0.005 | 16 | 0.198970% | 9.25e-15 |
| 0.0025 | 32 | 0.050428% | 2.42e-14 |

The fine error remains below the original 0.2% gate and below 35% of the coarse
error. Both frequency-response displacement relative errors are below 1.08e-9.

One actual offline Chromium UI workflow passes: source-airflow free-frame
feedback, four accepted steps with nonzero response, complete JSON export,
project save and exact restoration without recomputation. It takes 63.36 seconds,
with no page errors, failed requests or HTTP requests after going offline.
All 138 source/public/dist kernel modules match. Native replay of the exact
exported request passes all 17,608 numeric comparisons, plus structure, string
and boolean comparisons. The unchanged gate is `2e-8 + 2e-8 |native|`; only the
root evaluation counter is excluded. The largest error uses 9.11e-6 of its
allowed gate. No JavaScript production code changed; existing UI assets are
retained.

An earlier exact influence/geometry-cache experiment preserved the full matrices
and output but showed no meaningful speedup; it was not adopted. The first
analytical probe's JSON comparison failed only because it also needed to account
for the changed snapshot evaluation counters; all four differing fields are
recorded. The initial new wing fixture requested two intervals, below the
supported minimum of four, and was corrected without changing any physical
gate. Initial failed/interrupted logs are retained.

This does not establish native ASWING agreement or complete any ISAE family.
All 42 ISAE rows and acceptance thresholds remain unchanged. Full ASWING
functionality and the remaining validation discrepancies stay open.

Code and checks: [source time columns](../../openswing/time_tangent.py),
[accepted-step checks](../../openswing/time_integration.py),
[physical column tests](../../tests/test_time_source_mechanical_columns.py),
[source authority tests](../../tests/test_source_feedback_time_rank.py).
Requests, full matrices, profiles, results and execution logs are retained in
`artifacts/isae/source-time-tangent-20261104/`.
