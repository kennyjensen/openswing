# FFWT-4 rigid-extension loads, steady tangents and finite-BDF limits

The proposed rigid-tip treatment now has **44 passing focused checks**.
Explicit massless rigid extensions and endpoint pylons agree in retained
section loads and reduced steady matrices for both fuselage and lifting-surface
material charts. A separate prescribed-history check establishes that this
does **not** give exact finite-step BDF equivalence. No production attachment
rule or original ISAE model was changed; FFWT-4 coverage remains 200/8,000.

This follows the [literal rigidity preflight](isae-ffwt4-rigid-attachments-20261106.md).
The three driver-selected PM2 models still have two rejected point attachments
each, and their 4,800 reference values remain uncomputed.

## Explicit mechanical comparison

One synthetic model has a retained beam and an actual massless, nonlifting
rigid extension joined at its endpoint. The point object attaches at the
extension's outer end. The comparison model attaches a rigid pylon at the
retained endpoint while keeping the point object's physical jig position,
mass, full inertia tensor and angular momentum unchanged. Both lower and
upper ends are tested. Every beam uses a valid explicit mesh of at least four
intervals; no production meshing limit is bypassed.

The tests impose general rigid poses, local translational/angular motion and
nonparallel moving-frame rates/accelerations. They solve the linear nodal
force/moment balance and check **every inward endpoint force/moment trace**
on the retained beam against an independent inertial-transport calculation.
The point oracle includes centrifugal, angular-acceleration, Coriolis,
full-tensor inertia and spin terms. Retained meshes have four and six intervals.

| Retained material chart | Maximum scaled section-load oracle error | Maximum scaled paired-load difference | Maximum scaled steady Schur-matrix difference |
| --- | ---: | ---: | ---: |
| Fuselage | 5.33e-16 | 7.61e-16 | 2.052e-8 |
| Lifting surface | 6.95e-16 | 6.95e-16 | 2.029e-8 |

These are scaled arithmetic differences, not percentages or native-reference
errors. Section-load gates are 2e-13. The steady matrix gate is 2e-7, allowing
for the production Jacobian's finite-difference geometry columns.

The matrix comparison uses the actual production Jacobians. It first removes
their force/length scaling, then eliminates the extension's poses, internal
forces and joint reactions with a Schur complement: 120 variables reduce to
60. All entries are compared with the endpoint-pylon model's Jacobian.
Upright and rotated poses are both covered. The static jig cases close the
complete source equations. Rotated cases impose a displaced clamp pose and
test nodal load balance and derivatives; their original fixed-clamp residual
is retained and is not claimed to be zero.

Two negative checks restrict the conclusion. Reanchoring at an interior point
preserves total force/moment but changes internal section loads. A finite
extension compliance also prevents the rigid reduction. Neither operation
can be substituted for the tested endpoint treatment.

## Why finite-step time integration remains a separate requirement

The source time equations discretize nodal position and material Euler angles
separately. For rigid rotation, the continuous identity `d(Ra)/dt = ω × Ra`
does not hold exactly when the derivative of `Ra` is replaced with a finite
BDF stencil while angular velocity comes from the Euler-angle stencil.
The production pylon rule combines the anchor's nodal velocity/acceleration
with angular-offset terms. Two otherwise equivalent anchors therefore give
different finite-step point velocities and accelerations.

A prescribed constant-yaw history uses 0.7 rad/s and an anchor separation of
0.0119 m. The production `LocalMotion` results are compared with an independent
complex BDF-symbol calculation. This is a consistency probe, not an integrated
FFWT-4 trajectory or an estimate of its actual error.

| BDF2 time step (s) | Point-velocity difference (m/s) | Point-acceleration difference (m/s²) |
| ---: | ---: | ---: |
| 0.040 | 2.176789e-6 | 3.047903e-6 |
| 0.020 | 5.442193e-7 | 7.619320e-7 |
| 0.010 | 1.360562e-7 | 1.904812e-7 |

Halving the step reduces the BDF1 differences by approximately two and the
BDF2 differences by approximately four. Stationary histories have exactly zero
difference. The independent acceleration oracle agrees within 1.02e-12 m/s².
This is consistent time-discretization error, so an exact finite-step
replacement is not justified by the continuous mechanics proof.

## Remaining implementation requirements

The mechanical and steady-tangent comparison is complete for these explicit
synthetic models. Point drag/volume flow, local-rate/acceleration matrix columns,
integrated histories and browser execution remain uncovered. Test an explicit
virtual anchor in the time equations, then compare refined trajectories before
considering an endpoint reduction. Preserve all original physical point
properties and do not count a synthetic comparison as an archived native pass.

Native ASWING's out-of-range attachment convention is still unknown. The
[complete source audit](isae-ffwt4-sources-20261106.md) and all corresponding
source qualifications remain in force. No physical parameter, reference
tolerance, source equation or time-accuracy gate was relaxed.

Evidence is under `artifacts/isae/ffwt4-rigid-extension-20261106/`:

- `assessment.json`: body-chart loads, steady matrices, BDF differences and pins.
- `surface-assessment.json`: target lifting-surface chart comparison and pins.
- `test-attempt-02.xml`, `bdf-tests.xml`, `surface-tests.xml`: 20 + 4 + 20 passing checks.
- `test-attempt-01.xml` and its preserved helper/test sources: initial fixture
  rejection for using fewer than four intervals. The corrected fixtures obey
  the existing production minimum; no solver or acceptance rule changed.

Reproduction helpers are `scripts/verify-isae-ffwt4-rigid-extension.py` and
`scripts/verify-isae-ffwt4-rigid-surface-extension.py`. Both require a fresh
output path and retain source hashes. All jobs ran serially with one BLAS
thread and a 512 MiB address-space limit.
