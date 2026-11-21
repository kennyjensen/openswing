# SA-6 steady state derivatives

Updated 2026-10-28. SA-1 remains paused; this work extends the comparison of
SA-2 and later steady-aerodynamics cases. The target is the archived ASWING
output, with its original printed precision.

`openswing.rigid_derivatives.rigid_state_derivatives` now computes all six
steady flight-state columns using one base aerodynamic solve and one
circulation-Jacobian factorization. The columns are fractional speed, incidence
and sideslip in radians, and normalized roll, pitch and yaw rates in the base
stability axes. Output axes, dynamic pressure and reference lengths remain
fixed at the base state, following the documented coefficient convention.
The single base solve can contain multiple nonlinear iterations.

The derivative includes wind-dependent lifting-point locations, bound and wake
vortices, both Prandtl–Glauert transformations, body and shoulder flows, ground
images, local section forces and moments, and circulation response. Explicit
Mach and speed-derived Mach retain their different definitions. The selected
frozen-influence setting retains its zero-angle influence geometry. Prescribed
rigid geometry is the scope: the new API does not add a structural, free-frame,
trim or controller response. Engine records and inadmissible wall-root state
directions raise explicit errors. This API is available in the shipped kernel;
it is not a new browser UI action.

The [source audit](../../artifacts/isae/sa6-state-tangent-20261028/source-audit.json)
retains every one of the 1,584 original state-derivative cells, including 234
negative-zero tokens. The 44 archived operating points cover four aileron-chord
variants and 11 deflections each. Each point has six coefficients differentiated
with respect to six state variables. Comparison on two meshes therefore has
3,168 required slots, not 3,168 independent archived targets.

The original inputs have infinite stiffness under the documented zero-stiffness
convention, so elastic shape response cannot explain their fixed-state
differences. Historical producer, startup and discretization remain unverified.
In particular, Technical Description §4.6 permits lagging induced-flow influence
coefficients, while §8.3 constructs derivatives from the Newton Jacobian. The
archive does not establish whether its producer restored current-wind influence
partials for derivative output. The new API differentiates the complete current
steady operator; that historical convention is an explicit remaining question.

The [final native checks](../../artifacts/isae/sa6-state-tangent-20261028/native-verification.json)
pass 115 distinct tests: 58 integration/regression cases, 19 vortex-field cases
and 38 volume-flow cases. They cover the new state path and existing
control/circulation derivatives, moving vortices, cancellation, ground images
and bounded working storage. Fresh nonlinear perturbations at two step sizes
check the analytic state columns, including stall, Fourier circulation, bodies,
nonzero rates and frozen influences. These checks validate implementation
derivatives; they do not establish agreement with ASWING.

Four [offline native/WASM cases](../../artifacts/isae/sa6-state-tangent-20261028/wasm/execution-receipt.json)
pass all 48 physical checks and agree across 7,026 numeric values within
6.92e-13 scaled error, against a 1e-9 gate. All 129 native and public kernel
modules match. This exercises the locally distributed Pyodide WASM runtime
under Node with network access blocked, rather than browser UI interaction.

The [completed state comparison](../../artifacts/isae/sa6-state-tangent-20261028/state-comparison-r2/report.json)
computes all 88 analytic cases and all 24 independent perturbation workers in
532.54 seconds. All 112 workers exit successfully and are reaped. The run uses
88 base calls, 96 perturbed cold solves and 88 derivative factorizations, with
no retries or unknown call counts. All 3,168 values are finite and numerically
valid; **528/3,168 match, exclusively the six side-force derivative channels**.
Those matches represent 264 distinct native zero cells. No nonzero derivative
or complete 36-value state matches printed precision.

All six columns pass independent coefficient and circulation checks at both
steps in all four selected physical states. Maximum coefficient-derivative
error is 2.55e-8 and circulation-derivative error is 2.08e-7. Maximum base
residual is 4.03e-13, maximum reported tangent residual 4.40e-14, and minimum
scaled reciprocal condition 0.0169. These demonstrate consistent derivatives
of the current steady equations; the archived nonzero differences remain open.

The [independent saved-data analysis](../../artifacts/isae/sa6-state-tangent-20261028/analysis/summary.json)
replays all comparisons and perturbation stencils, verifies 765 evidence pins,
and retains every channel in CSV/JSON. The
[comparison figure](../../artifacts/isae/sa6-state-tangent-20261028/analysis/selected-state-channels.svg)
shows four declared channels with every original state and both meshes.
Maximum relative errors on the finer mesh are:

| Aileron chord | Lift / incidence | Pitch moment / incidence | Roll moment / roll rate | Yaw moment / yaw rate |
|---|---:|---:|---:|---:|
| 15% | 8.13% | 10.41% | 4.31% | 23.73% |
| 20% | 8.18% | 10.42% | 4.17% | 25.40% |
| 30% | 8.17% | 10.40% | 4.57% | 28.28% |
| 35% | 14.79% | 18.23% | 4.02% | 29.29% |

State derivatives have material mesh sensitivity in some channels. The largest
absolute change is yaw moment / sideslip at 15% chord and 4-degree control:
0.0397278 on 64 intervals versus 0.0466169 on 128, a 14.78% difference relative
to the larger magnitude. The largest relative change is axial force / sideslip
at 20% chord and 40-degree control: 0.000141237 versus 0.00181270, or 92.21%.
These descriptive two-mesh differences do not establish convergence.

Every archived sideslip derivative is zero. OpenSWING returns nonzero values
in the five channels other than side force. This makes the documented lagging
of induced-flow influence coefficients a concrete convention to investigate:
holding those coefficients fixed can remove this first-order response for the
literal straight, planar wing. The source archive does not establish its
historical derivative linearization; the current calculation includes the
full wind dependence and passes the independent perturbation checks.

The first comparison attempt is preserved separately. Its checker applied
`abs` to a JSON-style list: 18 workers returned the analytic API before that
error and two were interrupted with physical completion unknown. All 20
started workers were reaped. The corrected batch changes only the checker
conversion and early API checkpoint, preserving the original numerical kernel,
jobs, targets and gates. Its synthetic checker regression and independent
source review are retained beside both attempts.

A separate [native-output consistency audit](../../artifacts/isae/sa6-state-tangent-20261028/native-speed-homogeneity-audit.json)
checks the conditional identity that speed derivatives equal twice the base
coefficients. The literal inputs support quadratic load scaling: fixed zero
PG Mach, zero rotation, no Reynolds law and zero local pitching-moment terms.
Of 264 original token pairs, 214 satisfy the identity within combined printed
rounding bounds and 50 do not. The largest absolute gap is 1.24e-4; among the
incompatible pairs, the largest relative gap is 0.01695%. Historical convergence
and derivative conventions remain unknown. This ancillary audit changes no
reference target or acceptance gate.
The current speed derivatives satisfy twice their base coefficients within
3.11e-15 over all 88 computed states. The original-data scaling gaps are much
smaller than the main nonzero comparison differences.

The state ledger remains separate from the registered static score of
**88/528**, whose passes are all zero side force. The earlier full F1
control-derivative comparison also has **88/528** matches, all zero side-force
derivatives. F1 is now available through `--comparison-scope sa6-f1-rigid` in
the standard suite runner; a fresh single-job integration check verifies that
route. The subsequent state registration adds `--comparison-scope sa6-state-rigid`
with separate state counts; the full comparison above retains its original
kernel and execution record. Registration does not rerun that full batch.
The 1,452 mass/inertia entries, unpaired spanwise models and unresolved nonzero
output differences remain required work before SA-6 can pass as a whole.

The [consolidated verification](../../artifacts/isae/sa6-state-tangent-20261028/verification.json)
records the final kernel, focused tests, runtime witnesses, both comparison
attempts, independent analysis and documentation hashes. Whole-family
acceptance remains **0/41**.
