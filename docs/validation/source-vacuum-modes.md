# Source structural vacuum modes

Updated 2026-10-26. This adds the explicit `drela-fixed-vacuum-v1`
structural operator, paired with `drela-segspl-v1` interpolation. Existing
default and source static policies keep their equations and saved identities.
This is an implementation verification, **not a newly passed ISAE case**.

The new operator extends the source section equations into fixed-frame vacuum
inertia and modal matrix assembly. It includes both distributed mass families,
their independent CG offsets and section rotary inertias, point masses and
pylons, and the finite-segment transverse inertia correction. The later [material-damping extension](source-material-damping.md) adds
nonzero damping; this original benchmark uses zero damping.
Airflow/apparent mass, moving frames, controllers, struts, engines,
body-axis charts and stepped axes remain outside this operator. Signed static
weights cannot be used as dynamic masses.

## Equations and interpretation

The [steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
Eqs. 48–56 define endpoint matrix and completed load averages. Its Eqs. 77–83
define the CG arm and section inertia, including the transverse
`mu * ds² / 12` correction. The
[unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
Eqs. 37–40 add local elastic acceleration, centrifugal loads and precession.
Rendered equations were checked to resolve the correction's axes and signs.

Each endpoint uses the interior one-sided material properties and its own
orthogonal physical frame. For each mass family, compute the complete force
and couple before averaging them across the interval. Transfer half of each
integrated interval force and couple to each endpoint. This preserves discrete
force/moment conservation and the meaning of the mixed internal resultants as
endpoint means. The finite-segment rotary correction is included once; no
translational Gauss integration is added on top of it. Point objects retain
their concentrated attachment rule and receive no segment correction.

For a scalar uniform interval of length `h`, this gives the mass block
`mu*h/4 * [[1,1],[1,1]]`. With varying properties, it averages completed
endpoint products; the resulting operator need not be symmetric. It is not a
conventional finite-element mass matrix, and arbitrary discrete energy
positivity is not claimed. Mass/first-moment reporting describes the gravity
rule; a single aggregate symmetric dynamic inertia tensor is left unavailable.

The existing source policy's unloaded material length is also used here.
Steady Eq. 80 writes `ds` without explicitly fixing that finite-extension
interpretation. Historical executable discretization and finite-extension
equivalence remain unproven. No parameter or frequency was fitted to resolve
that uncertainty.

The existing descriptor solver forms `M = -R_zdot` from actual external loads.
Source state columns use full residual differences. Midpoint mechanical and
section-output shortcuts now explicitly reject incompatible source operators
so they cannot silently replace the selected structural equations. Kinematic
descriptor rows, constraints and checked original-pencil eigenpairs remain in
the existing solver.

## Independent verification

The [literal synthetic model](../../examples/source-vacuum-check.asw) is a
single clamped/free beam with axial and torsional compliance. With four
uniform intervals, each scalar family's complete frequency set is

`omega_j = (2*n/L)*sqrt(stiffness/density)*tan((2*j-1)*pi/(4*n))`.

All 16 positive/negative poles match this independent discrete formula.
Maximum relative frequency error is **1.79e-11**; maximum original-pencil
left/right backward error is **4.52e-17**. The native solve, linearization,
eigenvectors and physical output recovery took **5.98 s**. The base residual
is **5.55e-17**. These are numerical verification results, not ASWING archive
tolerances.

The first example run exposed its unintended automatic reflection from a
`t=0` lifting-surface table. The example was corrected to a strictly positive
parameter interval to represent the intended single cantilever. The
independent spectrum and its tolerance were retained.

Reproduce the native example with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-source-vacuum-modes.py /tmp/source-vacuum-check
```

The output directory must not already exist. The verifier saves the exact
request, result, source hashes, declared gates and numerical comparison.

Another 26 focused tests cover endpoint load products, independent normal and
additional CG arms, finite-segment and point inertia, zero-mass rotary terms,
zero-rate agreement with the static law, rejected unsupported inputs, and
descriptor acceleration columns. Eight scalar axial/torsion systems check all
128 finite poles against independently assembled matrices. Maximum relative
pole error is 3.27e-12; uniform 4/8/16 refinements pass their declared continuum
convergence gates. Eleven further tests check factory scope and the dense/sparse
source tangent fallback. None of these results was fitted to an aircraft's
archived frequencies.

## Browser and saved projects

The offline browser test passes **806/806 checks**. All 16,200 entries of the
full A/M matrices agree with native output to within 1.12e-16 absolute; the
physical base and metadata also agree. Every browser and native left/right
eigenvector is checked independently against its full descriptor pencil, and
all 16 eigenvalues are uniquely matched without assuming solver ordering.
Arbitrary eigenvector phase is not used as an equality test.

In this verification run, startup took 59.72 s and the complete modal UI solve
took 14.14 s. These are observations on the test machine, not a general timing
guarantee. There were no external requests or offline HTTP requests during
calculation. The result and project reopen byte-for-byte without another solve;
desktop/mobile rendering and refusal of incompatible frame motion are checked.
The UI and saved-data checks also pass 38 Node tests and five syntax checks.

To try it, select **Coupled eigenmodes**, then **ASWING fixed-frame vacuum
modes · experimental** under Structural equations. The selection fixes the
frame and vacuum settings; Earth attitude and gravity remain active. The
saved [four-interval example project](../../examples/source-vacuum-check-project.json)
contains the computed solution for inspection without recomputation.

The [machine report](source-vacuum-modes.json) and
[reproduction evidence](source-vacuum-modes-20261026-evidence.zip) retain the
inputs, outputs, tests, source hashes and earlier fixture/harness corrections.
The ISAE modal comparison still needs compatible aerodynamic inertia where
relevant, resolved historical operating settings, and broader source-dynamic
coverage. Source damping is now covered by the linked follow-up; moving-frame, Bode
and time-response extensions remain incomplete.
