# Selected feedback measurement recovery

Date: 2026-11-04. Native, offline UI and cross-runtime verification pass.
The [structured record](source-feedback-measurements-20261104.json) includes
source pins, measurements and evidence hashes.

The feedback evaluator now uses the controller's declared signals to determine
whether it needs section force, moment and strain recovery. Position, velocity,
attitude, acceleration and airflow signals use the existing moving-sensor formula
directly. Requested force, moment and circulation signals retain the complete
recovery path. Calling the public measurement function without a signal list
still returns its original complete measurement map.

This changes no aerodynamic or structural equation, finite-difference stencil,
rank check, nonlinear tolerance or time-integration acceptance gate. It retains
sensor offsets, Earth/body transformations, gravity, full or kinematic airflow,
partially defined axes and the original sensor-to-airflow row mapping.

| Identical two-step profiled request | Before | After |
| --- | ---: | ---: |
| Profiled elapsed seconds | 41.85096 | 31.50744 |
| Structural recovery calls | 583 | 3 |
| Physical residual evaluations | 879 | 879 |
| Accepted-root rank checks | 3 | 3 |

The complete JSON outputs are exactly equal. The observed elapsed-time reduction
is 24.72% for this one short case, using the same profiling instrumentation and
host. It is not a broad performance benchmark. Full Jacobian/rank construction
still dominates this case; its checks have not been skipped or relaxed.

Thirty-one distinct native cases have completed: twelve new moving/loaded sensor
parity cases, nine controller-authority checks, four controller-expression checks,
one partially defined sensor/trim check, and four independent circulation-feedback
transfer cases, plus the original full free-frame frequency/transient refinement.
The full free-frame test takes 374.91 seconds including pytest startup; its
acceptance gates, forcing, meshes, duration and time steps are unchanged.

The independently reduced free-frame equation is
`3 q'' + 10 q' + 310 q = command`. Both frequency samples pass the original
complex displacement and actuator gates; displacement relative errors are below
`1.08e-9`. Both time histories converge through the full 0.08-second interval.

| Time step | Accepted steps | Maximum normalized trajectory error | Maximum residual |
| --- | ---: | ---: | ---: |
| 0.005 | 16 | 0.198970% | 9.25e-15 |
| 0.0025 | 32 | 0.050428% | 2.42e-14 |

The fine error is below the original 0.2% gate and below 35% of the coarse error.
This closes the unfinished regression identified in the
[previous trim/time release](source-airflow-trim-20261104.md). That older report
retains its original revision-specific scope.

One actual offline Chromium UI case passes: source-airflow free-frame feedback,
four accepted time steps through 0.02 seconds, JSON export, project save and
restoration of the complete result without recomputation. The workflow takes
67.73 seconds and records no page errors, failed requests or HTTP requests after
going offline. All 137 source/public/dist kernel modules match. Replaying the
exact exported request natively passes all 17,608 numeric comparisons, plus
structure, string and boolean comparisons. The unchanged gate is
`2e-8 + 2e-8 |native|`; only the root residual-evaluation counter is excluded.
The largest error uses `9.11e-6` of its allowed gate. No JavaScript production
code changed, and the existing tested UI assets are retained.

The first new-test attempt contained a duplicate sensor identifier in its fixture.
The corrected fixture removes the previously declared sensor before installing
the two intended sensors. Initial failed and interrupted logs are retained. One
mixed regression batch reached its process limit after ten completed cases;
its remaining expression cases passed in a separate serial job. A temporary
tangent-cache probe was not adopted into production or used for the speed claim.

This is implementation and independent-equation validation, not native ASWING
validation. All 42 ISAE status rows and their numerical acceptance thresholds
remain unchanged. Full ASWING functionality and agreement remain incomplete.

Code and checks: [feedback evaluation](../../openswing/feedback.py),
[selected measurement tests](../../tests/test_feedback_measurement_selection.py),
[original physical feedback tests](../../tests/test_source_airflow_feedback.py),
[offline browser workflow](../../tests/browser/source-feedback-measurements.spec.js).
Complete profiles, requests, results and execution logs are retained in
`artifacts/isae/source-time-rank-20261104/`.
