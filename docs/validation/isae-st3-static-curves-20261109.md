# ST-3: fresh comparison of all published static curves

**84/86 static comparisons pass at 5%. All 84 readable ASWING ordinates
match on both meshes.** Two script-defined points are clipped out of the
archived figures and remain unavailable in the denominator. Fine-grid
nonzero errors have median **0.08725%** and maximum **0.43472%**; maximum
coarse/fine change is **0.00743%**, below the predeclared 0.1% gate.

Together with the existing [9/9 modal comparison](isae-st3-modal-current-20261109.md),
the prospective [mechanics scope](isae-st3-mechanics-scope.json) contains
**93/95 primary matches**. The historical **930/1,080** static snapshot stays
separate and unchanged. This explicitly changes the primary scope to the
published mechanical responses; it does not add the two overlapping scopes.
Full-family compatibility and exact historical run reproduction remain open.

| Published response, all three layups | Passing / required | Fine median error | Fine maximum error |
|---|---:|---:|---:|
| Deflection under force, Z(F) | 16/16 | 0.19961% | 0.43472% |
| Twist under force, T(F) | 15/16 | 0.05306% | 0.14035% |
| Twist under torque, T(M) | 27/27 | 0.08725% | 0.41754% |
| Deflection under torque, Z(M) | 26/27 | 0.05957% | 0.30584% |

The missing points are uncoupled T(F) at 4.905 N, beyond the saved 4 N
axis limit, and negative-coupling Z(M) at script coordinate 0.5528751856,
beyond its 0.55 limit. Their physical states were computed and refined;
neither receives a reference pass. Relative statistics exclude values inside
the declared plot-coordinate uncertainty around zero.

![Current OpenSwing and original ASWING static curves](../../artifacts/isae/st3-static-curves-20261109/replay/comparison.png)

[Vector plot](../../artifacts/isae/st3-static-curves-20261109/replay/comparison.svg).
Squares are original ASWING markers, lines are current OpenSwing, and crosses
are computed points whose source ordinates are unavailable.

## Source and physical conventions

The authoritative sources are Jan Part III, §4.3, pp. 35 and 37, Figure 25
on p. 39, and the original ST-3 `Analysis.m`, `change_mass.m`, force/moment
drivers, shell commands, three static `.asw` files and four EPS exports.
Their upstream manifest hashes and the authoritative report/theory catalog
were checked. The [plan](../../artifacts/isae/st3-static-curves-20261109/replay/plan.json)
pins all 183 source/helper files, including 141 production modules.

The original horizontal models have zero distributed weight/inertia.
All material properties, geometry, clamp, point locations and scale rows
are retained. Only the two Weight rows vary as the original driver specifies.
Equal positive masses apply vertical force; opposite signed masses apply
a couple through the rotating ±0.07 m chord arms. The public structural
JSON API handles these signed static forces directly.

The moment driver passes the CSV torque abscissa directly as a mass in each
Weight row, retaining the original 9.81 multiplier. Consequently the physical
undeformed torque is **9.81 × 0.14 = 1.3734 times the plotted abscissa**,
despite that axis being labelled N m. This source convention is reproduced
explicitly. It is not a parameter fitted to the ASWING curve or a calibrated
torque comparison with the experiment. Part III p. 37 describes signed tip
loads; the actual scripts implement the two opposed weights. Their signs
and each subplot's displacement/twist sign are preserved.

Five-significant-digit scalar mass formatting agrees with the final Weight
rows in all three archived models. The exact MATLAB version and intermediate
decks are unavailable. Only the nonnegative branch shown in Figure 25 is in
this scope; the scripts' additional negative moment branch is not claimed
as validated. CSV abscissae define loads, while experimental and Dunn FEM
ordinates are never ASWING targets.

## Extraction and verification

The new EPS reader uses filled data-marker centers. The historical reader
used polyline vertices, which omit samples on flat curves and can include
artificial intersections with clipping boundaries. The reviewed grid/tick
calibration is retained. A 0.01 plot-unit coordinate envelope was declared
before solving; maximum marker-to-stroke distance is only 0.003202. This is
a rendering-coordinate bound, not native output precision or experimental
uncertainty. All 14 focused source, sign and marker-extraction tests pass.

All **80 states**—40 distinct loads on nominal 64/128 cosine meshes—complete
serially without failure in the corrected replay. Property-break insertion
gives 66/130 nodes. Every state passes equilibrium, clamp and independently
assembled gravity force/moment checks; their maximum residual is 5.80e−12
in the respective checked units. All 86 paired output checks satisfy the
mesh gate, including the two unavailable reference values.

The initial zero-load solve converged, but its reporting check incorrectly
expected a dynamic launch state. This steady-section operator intentionally
has no dynamic inertia or launch packet at any load. The corrected runner
changes only that assertion. The first attempt, its plan and physical result
are retained; the repeated zero-load physical output is identical. Preparation
also exposed a legacy symlink-path mismatch and a collision between marker
shape and load-kind metadata; both were corrected before the execution plan
was frozen. No target, material property, physical solver or tolerance changed.

The corrected replay took **61.32 s of solver time** and **557.93 s including
serial process startup and checking**. Peak RSS was **100,356 KiB**. Each job
used one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall seconds.
All terminal receipts and complete request/result artifacts were authenticated.
No browser/build job was run; browser compatibility is not established here.

## Reproduction and remaining work

Use a fresh output directory with
`scripts/verify_st3_static_curves_current.py prepare --output DIRECTORY`, then
`run --output DIRECTORY --index N` for each of the 80 jobs, serially with all
three BLAS thread variables set to 1. Finally run `summarize --output DIRECTORY`.
The [bounded replay wrapper](../../artifacts/isae/st3-static-curves-20261109/run-replay.py)
retains individual terminal receipts and stops on any failure.

Native startup, exact historical meshes, disputed modal labels, the incompatible
`test.asw`/`test.txt` torsion pair and the broader legacy-output scope remain
open. Regular suite-catalog integration of this new static scope is also pending.
The present evidence supports moving the structural sequence to ST-4 without
declaring the whole ST-3 family complete.

Evidence: [complete summary](../../artifacts/isae/st3-static-curves-20261109/replay/summary.json),
[closing audit](../../artifacts/isae/st3-static-curves-20261109/replay/closing-audit.json),
[source tests](../../artifacts/isae/st3-static-curves-20261109/source-tests.xml),
[current runner](../../scripts/verify_st3_static_curves_current.py),
[marker decoder](../../scripts/isae_st3_curve_markers.py).
