# AE-4: circulation-rate force and moment audit

The independent circulation-rate force/moment calculation agrees with the
implemented equations at the actual 79 m/s Pazy operating point. **All 196
checks in six revised diagnostic jobs pass**. The largest relative matrix
difference is **1.51e−15** across both registered meshes. No production
equation or model parameter changed; AE-4 remains **227/1,200**.

The assessment was observed at
**2026-11-12T17:10:26.824820+00:00**. The original failed diagnostic attempt
is retained and explained below. These checks do not resolve the native
frequency mismatch or validate the whole case.

## Independent reconstruction

Drela's unsteady **Eqs. 35–36, p. 8** give the circulation-rate lift and its
quarter-chord couple. **Eq. 49, p. 10** gives the lagged tangency constraint.
The steady source-resultant interpretation and conservative balances use
**Eq. 51 and Eqs. 55–56, p. 13**.

At this vertical, untwisted, zero-lift Pazy state, freestream is 79 e_x, the span
direction is e_z, chord is 0.1 m and density is 1.23 kg/m³. Thus the integrated
circulation-rate force on one interval is
`f_U = -rho * chord * Gamma_dot * ds * e_y`.
Its quarter-chord arm from the beam axis is −0.025 e_x. These properties are
checked against the pinned model and saved equilibrium before applying the
closed-form formulas.

The oracle reconstructs Glauert sample positions from the saved material
coordinates, current interval lengths from the loaded endpoints, and forces
and moments directly from the equations. It calls no production load or
transfer helper to obtain expected values. The declared symmetric endpoint
transfer preserves the integrated wrench and mixed endpoint-average
resultants. Original native node positions and load sampling remain
unauthenticated; this test does not establish that missing historical setup.

| Check | Coverage | Largest error |
|---|---:|---:|
| Independent circulation-rate matrix columns, including force, moment and lag rows | 41+81 columns | 1.51e−15 relative, including separate force/moment row checks |
| Prescribed rate profiles: uniform, first/third sine, real/imaginary low-mode rates | Five per mesh | 1.70e−15 relative or contribution-scaled load error |
| First-order modal effect of replacing the assembled columns with the oracle | Both meshes | 3.68e−15/s |
| Global moment conservation about three reference points | All ten profiles | 4.23e−17 N·m absolute imbalance |

Positive and negative prescribed-rate evaluations isolate the odd,
circulation-rate response from quadratic pressure drag. Each profile checks
the section force and quarter-chord moment, both endpoint wrenches, nodal
loads, full residual action and moment conservation. Prescribed rates need
not satisfy equilibrium; these are residual/load evaluations, not claims of
ten new converged operating points.

The calculated force/moment-column differences are far too small to account
for the roughly 0.5 rad/s native frequency gap under this declared setup.
Other unsteady loads and historical sampling conventions remain open.

## Finite checks of the modal sensitivities

Each existing circulation-rate contribution was varied by ±0.1% in the saved
mass matrix, with the state matrix and all other entries held fixed. These
are mathematical diagnostics; no changed coefficient is adopted as a
physical model setting. Eight nearby-shift eigensolves check four central
differences against the earlier left/right-eigenvector sensitivities.

| Nominal mesh | Contribution | Central-difference versus adjoint relative error |
|---:|---|---:|
| 40 | Shed-vorticity lag | 6.252e−6 |
| 40 | Circulation-rate load | 3.094e−6 |
| 80 | Shed-vorticity lag | 6.362e−6 |
| 80 | Circulation-rate load | 3.151e−6 |

All are below the predeclared 5e−5 gate. Every perturbed mode retains its
left/right pencil and mass-pairing checks. The opposing modal effects of
lag and rate lift are confirmed; they do not imply a reason to change either
published term.

## Original diagnostic failure and correction

The first nominal 40 attempt passed 65 of 66 checks. Its third-sine profile
nearly cancels the global moment about one reference point: the expected
net magnitude is **7.50e−9 N·m**, while the sum of individual strip-moment
magnitudes is **0.01208 N·m**. An absolute imbalance of **1.33e−18 N·m**
therefore produced a relative-to-net error of **1.773e−10**, just above the
diagnostic's 1e−10 threshold.

The revised diagnostic normalizes that conservation defect by the sum of
individual moment magnitudes, retaining the 1e−10 threshold. This changes
the diagnostic criterion and gives a meaningful scale for a cancelling
load pattern. It changes no native comparison, production equation or
model parameter. The original failed result is preserved; it is not
retroactively marked passing or combined with the revised totals.

The [correction record](../../artifacts/isae/ae4-rate-load-audit-r2-20261112/diagnostic-correction.json)
pins the original script, plan, report and terminal receipt. The
[assessment qualification](../../artifacts/isae/ae4-rate-load-audit-r2-20261112/assessment-qualification.json)
explicitly distinguishes unchanged numerical thresholds from the revised
diagnostic normalization. The rerun is recorded under a fresh plan and
directory.

## Execution and next work

The authoritative index/catalog, Jan Part IV §3.4 and the original model,
driver and eigenvalue exports remain the source basis. Existing states,
matrices and eigenvectors retain their original pins; no historical result
is relabelled as a new solve. All six revised children and the initial
failed child are terminal and reaped. Work stayed serial with one BLAS
thread and unchanged **512 MiB /15 CPU /25 wall-second** caps. Revised-job
maxima were **1.21 CPU seconds, 2.24 wall seconds and 106.7 MiB RSS**; library
preload was separately bounded. No browser/build job ran.

The primary ledger remains **227/1,200**: 236 paired components, 9 mismatches,
16 unmatched, 12 unknown initial values and 936 unrun. Failed paired errors
remain median 8.29%, range 5.91–48.81%. The 79 m/s low-frequency errors remain
7.87% /8.29% on the registered meshes and 8.39% on the additional 160 mesh.
Historical 9,480 components, the overlapping 86/108 sample and later branches
and time histories remain separate and open.

Next independently check the **apparent-mass force and moment terms,
unsteady Eqs. 43–44**, at the same operating point. This completes another
defined part of the load-law audit without fitting parameters. Native
setup, near-onset damping, spatial convergence and tiny-root identity remain
open; broader sweep coverage resumes after the targeted unsteady-law checks.

Evidence: [revised plan](../../artifacts/isae/ae4-rate-load-audit-r2-20261112/plan.json),
[complete assessment](../../artifacts/isae/ae4-rate-load-audit-r2-20261112/assessment.json),
[preceding mesh/search audit](isae-ae4-low-mode-20261112.md).
