# Daedalus: current circulation lag and aerodynamic phase

The current source-equation/SEGSPL aircraft agrees with an independent
aerodynamic evaluator at the steady equilibrium and along its complex rudder
response at **0.2 Hz and 1.157378 Hz**. All **82 circulation-rate columns** of
the saved descriptor matrix also agree with an independent construction.
There is no missing lag term, duplicated circulation-rate load or rate-column
scaling error in these comparisons. **This finds no correction to the Bode
gap:** yaw at the selected dip remains **0.074218 versus 0.033986 deg/s/F3**.
No production physics, aircraft parameters or completion fractions changed.

![Independent and current circulation-rate lift](../../artifacts/daedalus-circulation-phase-20261114/report/rate-lift.png)

These are integrated forces on unequal-width strips, not force per unit span.
The supplied harmonic aircraft motion is an input to both calculations.

## Equations and scope

The authoritative [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed pp. 8 and 10–11, supplies quarter-chord lift and moment in Eqs. 34–36,
the lagged tangency constraint in Eqs. 48–49, and the locally two-dimensional
limit in Eqs. 50–56. The constraint contains `−(2/π) Γdot / Vperp`; the rate
lift is `rho * chord * Γdot / Vperp * (V cross span)`. Both terms are required
for its implied lag function `(1 + 2ik)/(1 + 4ik)`.

The [earlier complete aerodynamic check](daedalus-full-aero.md) used an older
midpoint/natural-spline operator. This study captures the accepted current
108-node, 82-circulation, 2044-coordinate source model anew. Its normalized
steady residual is **1.902e−10**. The supplied states also satisfy the saved
full harmonic matrices; no trim or harmonic solution is substituted.

The reference imports no OpenSwing physics. It reconstructs section geometry
and motion, integrates vortex/volume/propeller fields independently, and
evaluates circulation, stall leakage, lift, profile drag, pitching moment,
apparent loads, body loads, point drag and engine loads. Parsed material
samples and the physical input chart are supplied. No captured native airflow
or load is used as an expected-physics input.

The first baseline comparison correctly rejected reuse of the old discrete
policies: its straight-endpoint length differs from the current Eq. 48
average-strain arc measure, and it lacks the current profile-drag centroid
transport. The maximum wing interval-length difference was **0.002482 ft**.
The new independent reference explicitly implements those two choices:
`ds = norm(solve((Ra + Rb)/2, rb − ra))`, and a constant profile force applied
at the endpoint midpoint. Positions and section frames already agreed within
7.106e−15 and 2.221e−16, respectively. The original failed job and the old
reference remain intact; no tolerance or physical parameter was adjusted.
These discrete choices follow the declared current policy and the
[steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
printed pp. 12–14, Eqs. 48–56. They are not independently authenticated
historical executable quadrature conventions.

## Results

Fresh native fourth-order directional stencils use widths 1e−3 and 5e−4.
The independent calculation uses complex steps 1e−24 and 1e−20 and vortex
quadrature orders 16 and 32. The unchanged componentwise comparison gate is
`abs(error) <= 2e−7 + 2e−7*abs(reference)`.

| Harmonic quantity | Largest absolute native/reference difference |
| --- | ---: |
| Lifting-strip force | 5.265e−11 |
| Lifting-strip couple | 1.198e−11 |
| Circulation-rate lift | 1.735e−17 |
| Apparent force / couple | 2.776e−17 |
| Normalized local circulation residual | 1.484e−11 |
| Total aerodynamic force | 3.270e−10 |
| Total aerodynamic moment | 1.645e−9 |

Loads use the model's native lb and lb ft per F3 unit. The maximum baseline
output difference is 5.966e−13. Increasing vortex quadrature changes results
by at most 1.421e−14; changing complex-step width gives 4.219e−15. Native
stencil-width change is at most 2.391e−9 in total moment. The saved-data report
recomputes **621 array comparisons / 79,569 scalar comparisons**; these are
component checks, not independent aircraft cases or new ISAE passes.

Separately, the independent matrix construction checks **167,608 entries** in
all 82 circulation-rate columns, including entries that must be zero. It
retains the profile-drag derivative through the lagged tangency defect and
the conservative nodal/global wrench transfer. With `M = −dR/dzdot`, the
largest absolute error is **6.939e−17**; all other unrelated rows are exactly
zero. Its fixed gate is `2e−8 + 2e−8*abs(reference)`.

The wing's local reduced frequency ranges from **0.129 to 0.618** at the dip.
Eq. 56 therefore predicts appreciable aerodynamic lag in its local 2D limit:
about **13–19 degrees**, versus about 3–11 degrees at 0.2 Hz. These are useful
physical scales, not the exact finite-wing or coupled-aircraft transfer function.

## Evidence, limitations and next action

- [Comparison data and verification](../../artifacts/daedalus-circulation-phase-20261114/report/result.json)
- [Per-quantity comparison table](../../artifacts/daedalus-circulation-phase-20261114/report/comparisons.csv)
- [All circulation-rate matrix columns](../../artifacts/daedalus-circulation-phase-20261114/mass-columns/result.json)
- [Bounded capture/reference driver](../../scripts/check_daedalus_circulation_phase.py)
- [Independent source evaluator](../../scripts/daedalus_source_aero_reference.py)
- [Independent matrix construction](../../scripts/check_daedalus_circulation_mass.py)
- [Saved-data report generator](../../scripts/report_daedalus_circulation_phase.py)

All **17 serial jobs** are terminal and reaped: 16 succeed and the initial
old-policy comparison is retained as rejected. Maximum CPU time is **3.775 s**,
wall time **9.130 s**, and peak RSS **114.91 MiB**. Each uses one BLAS thread,
512 MiB address space, 15 CPU seconds and 25 wall seconds. The report verifies
2,525 input hashes, including three archived versions of the evolving driver,
and the authoritative steady/unsteady PDF and text hashes.

The current body apparent-mass factor remains the disclosed value 1; the
printed formula's factor 2 and historical settings are not resolved by
checking the selected convention. Ground, gusts, moving mean equilibria,
material interpolation and the input-state chart are outside this reference.
Neither a full independent aircraft response nor a native-ASWING match is
claimed. The current aerodynamic replay substantially narrows an equation or
phase-implementation explanation, but does not identify the published plot's
original settings.

Next check the **current full-aircraft angular-momentum balance and its
structural load transfer**, combining the newly checked airloads with current
endpoint real-inertia equations. The older complete balance check used the
previous operator. Preserve the Bode discrepancy and the four stricter
wing/brace mechanics checks as open. ISAE status/history and browser/build
verification are unchanged.
