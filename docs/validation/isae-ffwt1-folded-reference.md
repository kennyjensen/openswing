# Independent folded wing comparison

Updated 2026-10-15. An independent aerodynamic implementation reproduces
OpenSwing's nonlinear circulation, forces and moments at three computed FFWT-1
folded poses. Independent mechanical checks also satisfy the hinge balances at
those poses. The archived high-incidence Lift discrepancy remains unresolved;
no implementation mismatch was found under the shared model assumptions.
ISAE coverage remains **17 partial / 24 pending / 0 fully validated**.

## Model and independent calculation

The comparison uses the reconstructed Flare30 model, 22 m/s, density
1.2256 kg/m³, Mach 0.06466594 and the declared frozen-influence option.
The 100/40/40 requested mesh realizes 102/41/41 panels. The native material
sample coordinates are reused; a separate literal-input reader reconstructs
the centerlines, hinge rotations, section frames, vortex points and moment arms.
Geometry agrees with the native implementation within 2.23e−16 m or the
corresponding dimensionless frame tolerance.

The implementation independently evaluates the zero-core Biot–Savart law and
Prandtl–Glauert transformation. All three beams share physical index 1, so
their mutual core radii are zero. In the frozen approximation, source and
attached receiver positions remain at jig geometry; freestream velocity,
section directions and load transfer remain live. The material quarter-chord
moment arm is distinct from the wind-directed vortex-point offset.
These choices follow [Drela's steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 67–72, 146–160 and section 4.6.

Each pose starts from its own independently assembled linear circulation
solution. The nonlinear residual uses the source section slope 5.7897/rad,
the asymmetric section limits, `K_s = 40` and `delta_cl = 0.05`.
No native circulation, Jacobian or continuation helper initializes the solve.
All three finite-difference solves converge without a corrective Newton step.

## Results

| Scripted incidence | Independent Lift | Archived Lift | Independent minus archive |
| --- | ---: | ---: | ---: |
| 8.779176° | 14.41512035 N | 14.40550000 N | +0.00962035 N |
| 11.923603° | 17.71454154 N | 17.95210000 N | −0.23755846 N |
| 30.263890° | 19.90208138 N | 20.75340000 N | −0.85131862 N |

Against the original OpenSwing states, maximum circulation difference is
3.61e−13 m²/s, force-component difference 4.52e−13 N and moment-component
difference 1.67e−14 N m. Replaying the independent circulation through the
current native source gives force components within 3.56e−15 N of the
independent calculation. All six native evaluations use supplied circulation;
they do not launch another circulation or hinge solve.

The maximum independent normalized circulation residual is 6.37e−13,
below the unchanged 1e−12 FFWT comparison requirement. Dimensional residuals
are reported separately: 1.05e−13, 1.18e−11 and 1.40e−11 m/s. This study does
not supersede the earlier flat-model control, whose additional 1e−12 m/s
dimensional requirement remains unfulfilled at high incidence.

Independent force, gravity and literal spring-law calculations give a maximum
hinge imbalance of 5.65e−16 N m, below 1e−12 N m. Both root bending moments
agree with the earlier saved values within 2.10e−14 N m. The fold poses were
supplied from the prior computed roots; these checks verify their balances
without independently locating an equilibrium branch.

The three independent solves on the host, including tensor assembly and
recording, take 4.90 seconds. The six supplied-circulation native comparisons take
1.27 seconds. These are fixed-pose diagnostic timings, not coupled structural
or browser performance benchmarks.

## Browser runtime replay

Actual Chromium/Pyodide replays all three independent circulation states
without correction. All 104 current source modules are checked, and the local
run makes no external requests. Maximum normalized circulation residual is
6.38e−13 and maximum hinge imbalance is 5.58e−16 N m, meeting the same 1e−12
requirements. Total force components agree with the independent calculation
within 3.56e−15 N; strip forces and section moments also pass.

The complete browser check takes 42.05 seconds, including runtime loading,
source verification and output export. The individual supplied-state evaluations
take 0.12–0.24 seconds after initialization. This checks the WASM kernel at the
three supplied poses; it does not time a coupled solve or test the UI workflow.

## Evidence and remaining work

The [recorded-result index](isae-ffwt1-folded-reference.json),
[selected evidence](isae-ffwt1-folded-reference-evidence.zip) and
[extraction verification](isae-ffwt1-folded-reference-evidence.json) retain
the declared conditions, source versions, independent arrays and reviews.
All 821 recorded residual evaluations and 36 native comparison checks pass
saved-array review. The kernel also passes analytic, high-precision and
coordinate-transformation controls. Retained preflight failures concern native
record padding and a missing test dependency; neither reached an aerodynamic
solve.

This establishes agreement for the reconstructed rigid model with frozen
influences. It does not identify the original executable's unrecorded settings
or establish the physical accuracy of that approximation at large folds.
Producing model and operating assumptions, flexible-fixture and spatial-flow
matching, updated-influence branch limitations and dynamic response remain
open. Production solver source and defaults are unchanged.
