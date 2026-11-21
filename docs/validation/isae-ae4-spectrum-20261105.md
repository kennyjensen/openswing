# AE-4 zero-pass point: independent spectrum and source audit

The new 102 m/s coarse case passes **4/4** native-reference components at 5%.
The 103 m/s case remains **0/8 on each mesh**: the native export contains an
extra small complex root, so the existing complete-set comparison cannot pair
the spectra. Both fresh solves converge and pass their physical numerical
checks. No target, matching rule, equation or production default was changed.

Accumulated sampled results are now **67/88**, comprising 67 passes, five
finite damping failures and sixteen unavailable components. Combining the
two fresh jobs with the previous shared batch gives **11/40** selected declared
components, including twelve blocked initial-state components. Against the
full shared sweep this is **11/1,200 so far**, with 1,160 slots unrun. Repeated
meshes and earlier repeated cases are not independent native evidence.

## Independent full-matrix calculation

The retained coarse 103 m/s matrix was solved independently with LAPACK's
generalized Schur method. All **797 rows and columns** remain; no mass-rank
reduction, mode filtering or eigenvalue rounding is used. Homogeneous
eigenvalues and all left/right vectors are retained. LAPACK reports 512
nonzero-beta pairs and 285 zero-beta infinite pairs. Huge finite roots are
preserved without claiming they are resolved physical modes.

The four roots nearest the original `0+200i` shift are exactly the same set
returned by the production Arnoldi search. The maximum scaled root difference
is **3.081e-10**. Sixteen small/nearby roots receive explicit checks against the
original physical matrices; maximum right and left normwise residuals are
**3.836e-16** and **3.964e-18**. The smallest computed root is
`0.09329738948+0i`; the calculation does not recover a root near the native
`0.000071831111+0.000077428896i`.

This rules out a missed small mode in the current local Arnoldi search within
the numerical accuracy of this independent audit. It does not authenticate the
historical physical matrix or restraint settings. The QZ calculation alone
took 16.44 s on this host, excluding startup, loading and subsequent auditing.

## What the original files establish

The undeformed `alpha_0.sh` driver requests `NN4`; `divergence_speed.sh` requests
`NN10`. Both use `I40`, the same literal model, the solid wall and shift
`0+200i`. Under the literal insertion-stack interpretation, commanded IAS103
maps to point104 in the first export and point45 in the second.

The two main oscillatory roots are identical to the printed digits in both
exports: `29.005996+114.62964i` and `−3.5140312+182.09349i`. The tiny roots
are different:

| Export | Tiny complex roots | Candidate slow branch |
|---|---|---|
| NN4 | `7.1831111e-5 + 7.7428896e-5i` | `0.033334576 + 0i` |
| NN10 | `−1.2182900e-4 + 4.9725326e-5i`; `1.2220101e-4 + 5.0090789e-5i` | `0.033334177 + 3.6546462e-7i` |

This supports investigating coordinate integrators and numerical sensitivity;
it does **not** establish that the tiny native roots can be discarded. The
original rows remain required. The available eigenvector exports belong to
other deformed/LCO scopes and do not identify these particular modes.

The [unsteady theory, §13.3.1](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
specifies the full complex shifted inverse and a reused LU factorization,
consistent with the current solver. ARPACK's alternative real-part operator is
not evidence that this formulation should change. The [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
maps constraint-editor `D` to **DONE**, whereas `A` selects anchored defaults.
The script's `% D` therefore does not recover its historical restraint settings.
The available output documentation describes `EVCOUT`/`E`, not the exact
filter used by the `WW` eigenvalue export.

The [steady theory, Eq.178](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
describes zero prescribed acceleration for a tunnel-clamped wing. Our fixed
frame omits twelve global kinematic states; prescribed acceleration can retain
coordinate integrators. This is a plausible setup distinction to investigate,
not evidence authenticating the native frame or permission to append synthetic
zero roots. Ground-image dependence on Earth position and attitude must also
be respected (Eq.177).

## Remaining physical discrepancy

The finer 103 m/s solution has a slow real root `0.101941727/s`, compared with
`0.093297390/s` on the coarse mesh. The candidate native slow branch is
`0.033334576/s`. Conditional on that correspondence, the differences are
**179.88% and 205.81%**. The mesh change is **8.48%** using the fine value;
this mode is not spatially converged at the existing 0.1% gate.

The coarse 102–103 m/s roots bracket a zero crossing. Straight-line
interpolation gives 102.83261 m/s versus the candidate native 102.94015 m/s,
a **0.1045%** speed difference. These are interpolation diagnostics, not exact
neutral-point solves or additional passing tests. The large relative damping
error near zero remains a real open comparison.

The independent shared summary verifies all five computed jobs and twenty
blocked jobs. Its native-paired 103 m/s mesh checks remain failed because
predictions are unavailable; no missing comparison is promoted to a pass.
All processes finished. Jobs ran serially with one BLAS thread, 90-second
worker limits, and 512/768 MiB address caps for coarse/fine jobs. No new browser
or regression-suite run was needed for these unchanged production/helper
sources; the earlier 207-test receipt is retained as earlier evidence.

Next work is the actual modal constraint setup and slow-branch discretization,
while the remaining sweep, native mode identities and eleven missing family
adapters remain open. No whole family or project goal is marked complete.

- [Machine-readable evidence](isae-ae4-spectrum-20261105.json)
- [Independent QZ audit](../../artifacts/isae/ae4-spectrum-20261105/qz-report.json)
- [Original-source audit](../../artifacts/isae/ae4-spectrum-20261105/native-audit.json)
- [Combined shared summary](../../artifacts/isae/ae4-spectrum-20261105/analysis/summary.md)
