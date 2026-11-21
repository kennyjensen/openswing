# SA-1 driver-to-adapter mapping review

The literal driver, model and native operating table reveal no numerical setup correction that explains the current SA-1 discrepancy. In particular, interpreting `!V` as indicated airspeed does not supply a free density or speed adjustment: the native dimensional forces and coefficients already fix their dynamic-pressure product. This review changes no model, setting, tolerance or acceptance count. The existing native comparison remains 19/154.

The adjacent [machine-readable receipt](sa1-script-mapping-review-20261027.json) pins the original inputs, primary documentation, inspected implementation and the exact rational normalization calculation. This is a source and arithmetic review, with zero production imports or root solves.

## Driver and literal model

The pinned `Aswing_Simulation_V5_96_Only/SA_1.sh`, lines 15–18, enters `%`, `a`, `d`, then `!V 47.9`. The [Drela guide](../../.reference/aswing_doc.txt) identifies `A` as Anchored defaults, `D` as DONE, and `%` as the keyboard version of the constraint editor (lines 1940–2002). The [extended manual](../../.reference/ASWING_Extended_User_Manual.txt), printed page 13, lines 696–704, describes Anchored as fixing the aircraft reference point to ground. This supports a mounted prescribed-flow interpretation, not free-flight zero resultant force and moment. It does not recover every historical untouched constraint value or disabled-variable flag.

The same driver specifies all eleven incidences with `!A`, in original table order. Decimal parsing confirms all eleven command values exactly equal the printed alpha centers. The adapter retains those tokens and uses the table centers; [isae_suite_polars.py](../../scripts/isae_suite_polars.py), lines 126–162 and 203–228, reads the literal model/output association, speed, node request and alpha declarations. It does not represent the anchored preset or the IAS name in its parsed fields. Its execution selects `solve_rigid` (lines 297–305), a route distinction assessed below rather than silently assumed to have been tested.

The model constants and geometry are:

| Original lines in `SA_1.asw` | Literal meaning |
|---|---|
| 12–14 | `g=9.8100`, `rhoSL=1.2256`, `VsoSL=340.21`, SI input units |
| 17–28 | `Sref=5.9`, `Cref=1`, `Bref=5.9`; moment, acceleration and velocity reference positions all zero |
| 32–35 | `Ground 1 0 0`: translation and rotation restrained at beam 1, station 0 |
| 40–42 | Straight half-wing, `x=z=0`, `y=t`, span coordinate 0 to 2.95, chord 1 |
| 50–52 | `Xax=0`: the beam axis is at the leading edge, not at the default half chord |
| 60–77 | Zero stiffness tokens in the rigid directions; zero distributed mass and inertia |
| 80–87 | Zero twist, zero section zero-lift angle and `Cm`; `dCLda=6.2832`, `CLmin=-1.2`, `CLmax=1.2`, `Cdf=.00352562`, `Cdp=.00771413` |
| 89–91 | Zero flap lift/moment derivatives; no point weights, engines or bodies elsewhere in the file |

Zero rigid-direction stiffness means infinity in the guide, lines 1200–1203, and is implemented by [asw.py](../../openswing/asw.py), lines 23–29 and 201–206. The missing `GKn` has the same infinite default; the zero coupling entries remain zero. The half-wing is mirrored because its chord distribution starts at zero (guide lines 1096–1116; parser lines 195–199), giving the literal full span 5.9. There is no compliant displacement or gravity deformation to omit in this model.

The Ground record is a structural support, not an aerodynamic image switch: guide lines 930–958 define its types, whereas lines 2634–2649 describe the separate OPER/G image flag and its documented zero default. The driver never issues OPER/G. At zero prescribed rates and accelerations, apparent-mass force and moment vanish directly in [inertia.py](../../openswing/inertia.py), lines 189–201. Real mass is zero, and no body uses the body-added-mass factor. With images and gusts absent, Earth attitude affects neither these aerodynamic outputs nor the zero gravity load. The stationary motion remains a disclosed reconstruction; the source review does not authenticate all numerical startup constraint values.

## Native force normalization and IAS identity

`!V` changes indicated airspeed, explicitly documented at guide lines 2021–2033. The current `FlightCondition.speed` is true speed; the adapter supplies 47.9 together with the model sea-level density. That is semantically an IAS-to-TAS assumption at sea level, not evidence that the original run's altitude was recovered.

From the literal settings,

\[
q=\tfrac12(1.2256)(47.9)^2=1406.0144480,\qquad qS=8295.48524320.
\]

For each of the eleven native rows, independently form the Lift/CL and Drag/CD ratio interval using each printed token's exact half-last-place interval. All 22 contain this literal `qS`. Their joint intersection, rounded outward here, is

\[
8295.4840726627904\ \le qS\le\ 8295.4882799688666.
\]

Relative to the literal product, the exact-rational endpoints are approximately −1.4110533323e−7 and +3.6607489224e−7. This is only −0.141 to +0.366 ppm, versus approximately 576 ppm in the pre-stall CL discrepancy. The receipt retains the exact fraction endpoints, their decimal outward enclosures and the individual 22 interval checks; the rounded display above is not a new acceptance tolerance.

More strongly, write `Gamma = U g`. With fixed geometry, PG Mach zero, fixed section laws and stationary motion, all local velocities scale with `U`; `cl = 2 Gamma/(c |Vperp|)` and the normalized circulation equation are independent of `U` and density. This is visible directly in [aero.py](../../openswing/aero.py), lines 460–476. Circulatory lift, both profile terms and the leakage-drag term scale with `rho U²` (lines 553–563). The section `Cm` is identically zero, so its independent local Mach correction adds no load within the subsonic validity domain (lines 564–590). Moment arms are fixed. Trefftz coefficients and efficiency have the same scaling cancellation. Thus any speed/density reinterpretation preserving the native dynamic pressure leaves all seven compared quantities unchanged. This is a mathematical identity for the declared setup, not a claim that every ASWING setup is altitude independent.

The code's wind vector and lift projection also have the documented signs: [theory](../../.reference/asw_theory.txt), page 4, Eq. 1, lines 143–152, and page 38, Eq. 185, lines 1908–1916, match [aero.py](../../openswing/aero.py), lines 153–158 and 727–732. All reference offsets are zero, so reference-point velocity and moment translations introduce no ambiguity here.

## Is the full anchored route already compared?

No such retained comparison was found in the bounded search of the existing `artifacts/isae/sa1*` diagnostic runners, protocols and summaries, excluding copied kernel code. The focused 22-job baseline uses the polar adapter's rigid route. The frozen/spacing/historical-model drivers also call `solve_rigid`; the basis study varies the circulation representation; the alpha-path and 800/1600 studies use the independently replayed straight-wing reduction. Inverse/rounding/exporter studies are conditional reconstructions, not mounted equilibrium solves. This negative finding is limited to the inspected retained artifacts, not an assertion about every past transient process.

The smallest controlled route comparison uses the literal model with `natural-v1` interpolation and compares `solve_rigid` to `solve_static` with prescribed `FlightCondition`, empty operating constraints and loads, and explicit `[0,0,-9.81]` gravity. The parent subsequently authorized the two original states 1.9971° and 18.091° at nominal 200 intervals; their separate prospective protocol and outcomes belong under `artifacts/isae/sa1-anchored-equivalence-20261027`. They are not outcomes of this source review.

The mounted path adds nodal geometry, internal force/moment and support-reaction unknowns, and a coupled equilibrium corrector. Zero compliance removes internal-load feedback into compatibility ([network.py](../../openswing/network.py), lines 455–463), while the rigid mount fixes the remaining rigid-body freedom (lines 514–524). Both routes call the same aerodynamic evaluator (network lines 343–350; aero lines 912–916), and the network includes that evaluator's circulation residual in the full system (network lines 559–560). Exact arithmetic therefore predicts the same aerodynamic root on identical geometry, with additional internal loads and reactions, not a new physical lift law.

Two numerical distinctions must be measured: the coupled corrector and its load continuation can follow a different numerical path; and `deformed_meshes` reconstructs the same material sample positions through stored endpoint fractions (network lines 103–109 and 261–279), allowing tiny floating-point differences even at zero displacement. Compare actual nodes, frames, `tm`, lengths and force-point coordinates before attributing any discrepancy to anchoring. Switching to `drela-steady-coupled-v1` simultaneously requires `drela-segspl-v1` under [numerical_policy.py](../../openswing/numerical_policy.py), lines 34–42, and changes endpoint force/couple transfer; that would be a separate policy comparison rather than the minimal test of the adapter route.
