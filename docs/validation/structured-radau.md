# Sparse Radau time integration

Ordinary prescribed, free and mixed-frame Radau steps now use the existing
sparse beam/frame assembly. They no longer require a dense three-stage
matrix when this path succeeds. The original continuous equations, all three
stage residuals, nonlinear tolerances, accuracy controller and default BDF
method are unchanged. Inverse actuators, controllers and position histories
retain their general paths.

## What changed

The Newton approximation evaluates separate state and rate partials at the
current final-stage state, rate and time. The state partial retains the existing
BDF policy of lagging nonlocal geometry only in the Newton matrix. The rate
partial uses the current continuous equations at fixed state, including
nonzero circulation rate and finite rotation charts. Solved aircraft
accelerations remain algebraic variables: their time derivatives are not
introduced, while their state Jacobian columns remain included.

Diagonalizing only the constant 3-by-3 Radau stage matrix permits one real and
one complex shifted full-system factorization. The conjugate factor is recovered
by reality. The solver checks the original approximate three-stage matrix
product after reconstruction. No aircraft modes are removed and no aircraft
mass matrix is inverted. The original full collocation finite-difference
fallback remains available if assembly, factorization, solve or Newton progress
fails. This is modified Newton, not an exact stage-local Jacobian or a claim
that ASWING uses Radau.

## Checks and measured Daedalus step

Seventy-five distinct native cases pass: eight algebra/dispatch tests, ten
physical tests and 57 existing Radau, accuracy-control and inverse-position
regressions. The physical checks compare every continuous rate column with
uncached central differences at finite rotations and nonzero motion; the
maximum difference is 3.56e-9. Free, mixed and aerodynamic flap trajectories
agree with forced full collocation finite differences, with successful sparse
corrections and no dense fallback. Independent gravity and mass/inertia signs
and four injected fallback failures are checked.

The actual offline browser solves an eight-panel free-flight flap response,
exports it and resumes its Radau checkpoint. All stage gates and retained
values pass, and exported provenance matches the current kernel. This is a
functional browser check, not a full Daedalus browser timing measurement.

A single C16 Daedalus step from the saved 6.7 m/s trim, with +0.1 native F3,
dt=0.00125 s and requested tolerance 1e-10, completes with:

| Quantity | Result |
| --- | ---: |
| Structured builds / shifted factors | 1 / 2 |
| State / rate assembly residual evaluations | 92 / 183 |
| Newton corrections | 3 |
| Dense fallback / retry | 0 / 0 |
| Maximum original stage residual | 3.21079e-14 |
| Required stage tolerance | 1e-12 |
| State + rate partial storage | 4,527,872 bytes |
| Instrumented native runner time | 16.31 s |
| Peak child RSS | 136,692 KiB |

The previous general path would allocate a 6645-by-6645 real tangent
(353,248,200 bytes before factorization/copies) for this 2215-variable chart.
That is a matrix-size comparison, not a measured dense-baseline speedup or
total-memory ratio. The new partial-storage figure excludes shifted matrices
and factorization storage. The one-step timing includes launch, instrumentation
and output on a shared host; supervisor lifecycle was 17.65 s.

A fresh public checkpoint restore re-evaluates the saved Daedalus stage
equations without Newton solves or time tangents. It reproduces the stage
residual and endpoint to 1.74e-18 scaled difference. This validates the saved
discrete step, not a complete nonlinear trajectory or its temporal accuracy.

The first browser test stopped on an overly strict object-shape assertion:
continuation adds restart_context metadata to retained rows. The corrected
test checks every original key/value and the added context. The first new
aerodynamic test stopped on a +F1/F1 reporting-key error. Both receipts and
source versions are retained; neither required a physics or tolerance change.

## Remaining accuracy work

The separate [saved-linear Radau study](daedalus-linear-radau.md) improves
refinement substantially, but its roll response still fails the unchanged
0.5% time-grid criterion. No full nonlinear Daedalus convergence, browser
speedup or agreement with Drela's Bode drawing is established here.

[Machine-readable evidence](structured-radau.json) and
[raw source, runs and checks](structured-radau-20261025-evidence.zip) retain
the exact inputs and results.
