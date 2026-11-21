# Derived section loads and elastic incidence

The workbench now exposes four additional outputs from the ASWING user guide's
[Displayed Variables description](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt):

| Quantity | Result field | Stored unit | Definition |
| --- | --- | --- | --- |
| Local quarter-chord pitching moment | `cm` | dimensionless | Flap-mixed section Cm with the actual section-normal Mach correction |
| Normal aerodynamic lift per length | `f_aero` | input F/L | Circulatory and enabled circulation-rate lift projected on the current physical section normal |
| Normal gravity/inertial load per length | `f_reac` | input F/L | Distributed real-mass gravity/inertia plus apparent-mass force projected on that normal |
| Effective incidence change from deformation | `da_eff` | radians | `(n - n_jig) dot V_relative / abs(V_relative)` |

The normal is the physical section normal. It does not include the zero-lift
angle or the flap-induced tangency correction. `da_eff` uses the total relative
velocity at the bound-vortex force point, including gust, induced and elastic
motion contributions. It is the documented linearized measure, not an arcsine
or a difference of exact angles. The workbench displays it in degrees; raw strip
and time-history CSV retain radians. A zero-speed sample is undefined and remains
a gap. The definition and sample convention are included in exported results.

`f_aero` excludes profile drag, apparent mass and point loads. `cm` excludes
moment-arm contributions and apparent-mass couples. `f_reac` includes both the
ordinary and additional distributed masses; it excludes point masses, engines,
struts, externally applied point loads and support reactions. Those concentrated
loads remain in their existing outputs. In particular, a heavy point object
does not become an invented spanwise load density.

For coupled steady and time states, distributed inertia uses the same eight-point
material quadrature and moving-section kinematics as the physical residual.
The result sums its endpoint force contributions per interval, adds the existing
apparent force, projects on the current normal and divides by current length.
This attachment happens on the owned result after the residual evaluation;
changing gravity cannot leave stale values in the aerodynamic cache. Rigid
analysis uses its existing distributed centroid mass representation. Raw
`evaluate_aerodynamics` calls do not invent real-mass loads and leave `f_reac`
unavailable until a complete analysis evaluates those loads.

These force densities are interval averages reported at the aerodynamic material
stations. The original guide shifts derived values by half an interval in its
text table to share node rows; OpenSwing reports the actual material station.
The exact original-executable midpoint/interpolation convention is unverified.
No load law, equilibrium residual or time equation is changed by these outputs.

## Independent references

`scripts/verify-section-outputs.py` constructs an original two-metre straight
wing with unit chord, ordinary line mass 2 kg/m, additional line mass .5 kg/m,
and a separate 10 kg point mass. The reference uses G=9.80665 m/s², density
1.225 kg/m³ and sound speed 340.294 m/s. Cm=-.04 and dCMdF1=.005 with setting 3
give a pre-compressibility moment coefficient -.025.

The 14 cases check 608 physical scalar values:

- Three rigid meshes check actual local Mach, rotated Earth gravity, vertical
  acceleration and the analytic flat-section expression
  `f_reac = mu*(g_normal-a_normal) - rho*pi*c²*a_normal/4`.
- Three prescribed elliptic-circulation cases check circulatory lift and enabled
  or disabled rate lift. For Gamma=sin(theta) and projected semispan one metre,
  the independent Glauert midpoint downwash identity is
  `w = -N*sin(pi/(2*N))/(2*pi)`. Normal lift is
  `rho*30*Gamma + rho*c*Gamma_dot*30/sqrt(30²+w²)` when lag is enabled.
- Five prescribed moving-section cases use positive/negative elastic rotations,
  stretch, local translation/acceleration, rigid rotation, gust and K/F/K/L.
  The known relative velocity is `(31,1,5)` m/s. For section rotation theta about
  y, the exact reference for the documented incidence measure is
  `[31*sin(theta)+5*(cos(theta)-1)]/sqrt(31²+1+5²)`.
  Centripetal and Coriolis forces include both distributed centroid offsets;
  the original material mass is retained under stretch. The apparent-mass
  reference includes the velocity-cross-angular-rate term.
- Two alternative L/T/F systems repeat the moving-section reference, including
  conversion of accelerations, circulation rates, weight densities and forces.
- A solved rigid mounted state launches three actual stationary time snapshots.
  Every strip retains `f_reac=-2.5*G`, while the support force includes the total
  15 kg. This checks the distinction between distributed and concentrated mass.

The prescribed moving/circulation cases are intentionally not equilibrium
solutions. They verify instantaneous displayed quantities against independent
kinematic/load formulas. They do not validate a nonlinear operating branch.
Native maximum absolute discrepancy is 1.422e-14 in the stated SI/dimensionless
reference quantities. The records preserve all source hashes and library versions.

Additional tests cover control/zero-lift offsets, undefined incidence at zero
relative speed, body-only gaps and gravity changes that reuse an aerodynamic
cache. The display tests distinguish raw radians from displayed degrees and
retain missing values in old solution archives and sampled histories.

## Browser use and reproduction

Select **Normal section-load reference**, speed 30, alpha/beta zero, fixed PG
Mach zero and flap 1 setting 3. The **Span loading** selector offers section
moment, normal aerodynamic load, normal inertial load and elastic incidence.
The rigid example has zero elastic incidence. The existing **Flexible high
aspect ratio wing** in mounted mode provides a computed deformed comparison.
The solver report documents the definitions; plots, saved solutions, sampled
time envelopes and CSV preserve the selected quantity and units.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-section-outputs.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_section_outputs.py
node --test tests/loading-data.test.mjs tests/distribution-history.test.mjs
npm run build
node scripts/test-section-outputs-wasm.mjs
npm run test:browser -- tests/browser/section-outputs.spec.js
```

The new eight native checks pass in 4.86 test seconds. The separate 49-check
native regression passes in 184.86 seconds, covering airflow, aerodynamics,
implicit derivatives, distributed dynamic inertia and the unsteady network.
Together these are 57 distinct targeted native checks. All 24 selected
JavaScript checks pass. The packaged-WASM run repeats all 14 analytical cases,
including the physical time integration, and compares 560 recorded values with
native results; maximum scaled difference is 1.888e-15. The 608-value analytical
count includes the stationary history's additional snapshots, which the helper
checks inside each runtime rather than storing in the comparison vector.

All four offline browser workflows pass: the existing airflow/refinement and
airflow-history workflows, plus the new section-load/history/archive workflow
(61.3 test seconds) and the computed flexible-wing incidence workflow (42.8
seconds). The tests check the separate 15 kg support load and 2.5 kg/m distributed
load, Cm correction, time snapshots, every exported derived value, unavailable
old fields, archive restoration and raw/displayed angle units. Desktop, mobile
and deformed-incidence screenshots were inspected visually.

`section-outputs-checks.json` records terminal outcomes/logs, counts and exact
source, artifact, asset and screenshot fingerprints. The final bundle build is
`openswing-section-outputs-release`; `/tmp/audit-openswing-section-outputs.py`
checks the native/public/dist/HTTP modules, tested assets, study/runtime identities
and exact source/local ZIP contents, CRCs and served bytes. Its result is
`/tmp/openswing-section-outputs-release-audit.json`. No hosted app is updated.

These are targeted checks; full ASWING and experimental validation, exact
midpoint/output parity and equivalent modal/harmonic displays remain open.
