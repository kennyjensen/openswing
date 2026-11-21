# Force-point airflow and swept-line refinement diagnostics

The solver now reports the relative fluid velocity, its sample position,
section-normal speed and local section-normal Mach for each lifting strip.
`lifting_airflow` records the maximum and explains the coordinates, units and
K/F receiver convention. These are derived from the velocities already used by
the published load and stall equations; they do not enter a new force law.

The browser's **Span loading** selector adds local normal Mach, normal speed,
and the three relative-velocity components. They are available in steady plots,
computed time histories, sampled envelopes, CSV and saved solutions. The solver
report identifies the maximum's beam, parameter and body force-point position.
The existing subsonic rejection now supplies the same location and speeds in its
message, with structured `AnalysisError.details` for native callers. Rejected
calculations still cannot be exported as valid results.

These quantities apply to lifting force points. Body-only strips have no
invented surface-airflow values. Historical solution records without the new
fields display gaps; they are not silently recomputed or interpreted as zero.
Velocities use input L/T, positions use input L, and Mach is dimensionless.
Local Mach uses atmospheric sound speed even when PG Mach is fixed to zero.
Under K/F, current motion/gust/jet sampling and the jig-induced coefficient
locations remain distinct, as in the existing approximation.

## Why the swept-wing failure is retained

The [ASWING steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 64–73 and 150–161, evaluates lift/profile forces using velocity at the
bound-vortex point. Its wake legs align with the freestream; self-surface
influences have no finite core. The prior [SA-2 study](sa2.md) reproduced growing
tip velocities with independent line integration of computed circulation.

The new reference isolates the geometry using a straight bound line
`x = y tan(Λ), z = 0` and prescribed elliptic circulation. With wind along x,
the bound-line principal-value velocity is zero. Let `y_j` be each wake origin,
`ω_j` its circulation jump, and `y` a force point. Direct integration of the
semi-infinite rays gives

\[
w(y)=\frac{1}{4\pi}\sum_j\omega_j
\left[\frac{1}{y-y_j}+\frac{\sin\Lambda}{|y-y_j|}\right].
\]

The first term has the ordinary unswept cancellation. The second term has an
absolute denominator and changes sign with sweep. It persists even when the
circulation is prescribed analytically, separating this effect from the
nonlinear circulation solver, empirical stall closure and experimental inputs.

For cosine-spaced endpoints and Glauert midpoint samples of
`Γ = Γ₀ sin θ`, the first term is spatially constant:

\[
w_0=-\frac{\Gamma_0 N\sin(\pi/(2N))}{2\pi b},
\]

where `b` is projected semispan. It approaches `−Γ₀/(4b)`. The swept term at the
last force point grows with refinement. The reference uses stable trigonometric
differences for near-coincident cosine nodes; subtracting those cosine values
directly loses precision at fine tip spacing.

The cases use ±35° and zero sweep, 32/64/128/256/512 intervals, two alternative
L/T/F unit systems and K/F. Their circulation is prescribed; **these are field
verification cases, not converged wing operating points**. The production field
is compared with the separate closed-form expression over every strip. Plots in
`section-airflow.svg` and `section-airflow.pdf` show the retained growth.

Later [Reid/Hunsaker research](https://digitalcommons.usu.edu/researchweek/ResearchWeek2020/All2020/8/)
addresses general lifting-line singularities by modifying local bound-line and
wake geometry. That supports further investigation, but it is not an exact
validation of ASWING's downstream circulation closure. Applying a different wake
law here would require a separately specified and validated model extension.
This increment preserves the documented equations and makes their evaluated
flow inspectable. Local Mach below one alone proves neither physical accuracy
nor mesh convergence.

## Verification and reproduction

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-section-airflow.py
python3 scripts/fetch-sa2.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-section-airflow-regression.py
.venv/bin/python scripts/plot-section-airflow.py
npm run build
node scripts/test-section-airflow-wasm.mjs
node --test tests/loading-data.test.mjs tests/distribution-history.test.mjs
npm run test:browser -- tests/browser/section-airflow.spec.js
```

The separate regression record replays all historical SA-2 cases on the updated
kernel, without overwriting the historical study. All 104 computed cases retain
their 4,784 compared physical values exactly; all ten rejected cases remain
rejected. Only the additional error location text differs. Source/runtime
fingerprints distinguish old evidence from the current implementation.

Native checks also cover moving force-point locations, body angular rates,
gusts, actual versus PG Mach, alternative units, absence of surface fields on
bodies, and saved steady-state launches into physical time snapshots. Browser
checks cover the actual SA-2 refinement behavior, plots/CSV, archive restoration
and missing-field gaps, sampled time envelopes, rejection messages and mobile
layout. This is targeted verification, not a new full-project regression.

The final closed-form study checks 25,873 physical values across 17 cases.
Maximum absolute errors are 1.596e-9 m/s in velocity, 4.697e-14 m in position,
1.475e-9 m/s in normal speed and 4.335e-12 in Mach. The packaged-WASM replay
compares 1,241 selected physical values in the same 17 cases with maximum scaled
native/WASM difference 2.271e-14. All 23 selected JavaScript checks pass.

The first native batch ended with 75 passes and three failures in the new
closed-form fixtures: their condition had retained the default five-degree
incidence while the reference assumed zero. The fixture now explicitly uses
zero incidence. At the finest mesh, subtracting nearly equal cosine node
coordinates then exposed reference roundoff; stable trigonometric differences
remove that loss without relaxing the tolerance. The final three targeted
fixture checks pass separately (9.48 test seconds). Together these are 78
distinct passing checks across runs, not a relabelled successful original batch.
No production equations changed during these fixture corrections.

The first browser batch passed four workflows and failed the time-history
workflow on an ambiguous selector matching the envelope curve and four markers.
The first targeted correction then failed on Playwright's visibility heuristic
for a horizontal path with a zero-height bounding box. Both runs had completed
the actual time integration and its physical checks. The final test checks the
path geometry, visible markers and each exported velocity/position/Mach value,
plus the numerical sampled extrema. Original failed outcomes are retained.

The final two-workflow browser run passes: 75.0 test seconds for steady plots,
archives, rejection and mobile layout; 54.0 seconds for the actual computed
three-snapshot history, envelope and complete airflow CSV checks. Together with
the three distinct existing SA-2/K/F regressions in the initial batch, five
distinct workflows pass on unchanged production sources. The desktop airflow,
mobile error and time-envelope screenshots were inspected visually. The
horizontal envelope and its markers are visible; no rendering change was needed.

`section-airflow-checks.json` retains exact terminal job statuses, logs, numerical
counts, source/build fingerprints and screenshot hashes. The final source/local
bundle build is `openswing-airflow-release`; `/tmp/audit-openswing-airflow.py`
checks the tested assets, all 56 native/public/dist/HTTP modules, numerical
runtime, study provenance and both ZIPs' exact contents, CRCs and served bytes.
Its output is `/tmp/openswing-airflow-release-audit.json`. This release process
does not update the old hosted deployment or close the broader requirements.
