# Frozen aerodynamic influences (K/F)

The [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
K/F, defines fast mode using undeformed geometry and zero alpha/beta for the
vortex influence matrices. K/M requires recalculation when PG Mach changes.
The [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
§4.6, includes both vortex and volume influence functions in the simplest
precomputed model. Equation 177 separately retains Earth position and attitude
in ground-effect influences. These are the published basis for this option;
exact behavior of the original executable has not been compared.

`FlightCondition.freeze_influences` is a strict boolean. Since 2026-11-07,
new Python requests and browser analyses default to **true**, matching the
fast default shown in ASWING's menu. Explicit false remains supported. Older
saved cases, equilibria and checkpoints without the field retain false;
saved explicit choices are restored unchanged. Flow surveys and steady
continuation requests use the new default when starting a new analysis.
The browser exposes the option in Circulation representation and records it in
requests, cases, saved equilibria and time checkpoints. A saved time launch uses
the saved choice, which the equilibrium panel reports even if the current setup
checkbox differs.

With the option enabled, the original ASW geometry is reconstructed on the exact
material mesh. Vortex endpoints, attached influence receivers, width-limited
cores and volume sources/doublets use that geometry and the x-directed wind.
The vector velocity coefficients are fixed; their projection onto current
section normals is not. Circulation, physical section frames and lengths,
kinematics, gust sampling, propulsive jets, local apparent mass and conservative
load transfer retain the current state. Current control/force-point offsets
also use the selected zero-angle influence direction in equations 155–157.

Mach, core ratio and the current physical ground plane invalidate the owned
coefficient cache. Speed changes at a fixed specified PG Mach only scale volume
flow and the physical freestream; automatic Mach changes rebuild coefficients.
The cache belongs to one model/material mesh, is bounded, and is rebuilt from
ASW geometry on restart rather than serialized as authoritative numerical state.

Attached engines, point objects, body quadrature/shoulders and sensors use their
corresponding jig receiver locations for induced coefficients. Their reported
positions and motion/gust/jet sampling remain current. Arbitrary external survey
points sample the frozen source field at the requested spatial coordinates.
Consequently a probe placed at a moved sensor is not generally equivalent to
that sensor's frozen attached coefficient. Reports expose this distinction.

The Trefftz diagnostic follows the same jig geometry and x-directed wake;
its transverse force and drag axes are the frozen influence axes. Total
near-field coefficients still use actual flight axes. No resolved shed-wake
history is introduced. This approximation is intended for benign conditions;
it omits influence changes due to deformation and wake alignment.

## Verification results

The studies below predate the default change and retain their original source
identities. The [SA-6 default adoption](isae-sa6-focus-20261107.md) records the
new registered comparison and its checks separately.

`scripts/verify-frozen-influences.py` independently integrates finite and
semi-infinite vortex lines, solves current-normal tangency and integrates current
frame forces. It covers three meshes, rotated/stretched/translated surfaces,
nonzero signed alpha/beta, PG Mach, solid/free-surface images and alternative
length/time/force units. The reference uses neither the production mesher nor
the production vortex kernels, circulation solver or influence cache.

Native tests additionally check an adaptive source-volume integral and analytic
point singularities, current-position gusts, cache invalidation, rigid dynamic
lag poles, harmonic gust/rate-lift response and saved-state/time continuation.
`scripts/test-frozen-influences-wasm.mjs` replays the native study with the
packaged kernel and checks source/runtime identity. Browser workflows cover
offline analysis, old-case defaults, saved launches and flow inspection.

The independent native and packaged-WASM studies passed all 11 cases and 516
physical comparisons. The maximum scaled native/reference difference is
2.213e-14; the maximum native/WASM difference is 1.531e-15. The immutable source
hashes and computed/reference values are in `frozen-influences.json` and
`frozen-influences-wasm.json`.

The targeted native batch ended with 162 passes and one failure because the
new volume fixture lacked its required Unit block. After adding L/T/F declarations,
that one test passed (2.76 test seconds). No production code changed. The failed
batch remains recorded as failed; the two terminal runs cover 163 distinct
passing checks. These are targeted regressions, not a fresh full native suite.

All 45 JavaScript checks and ten offline browser workflows passed. The two new
workflows cover K/F loads against the independent reference, invalidation of old
displays, case restoration, saved-equilibrium time launch, flow inspection and
old-case defaults. Eight existing lag/core/time workflows also passed. The
control and saved-launch screenshots were visually inspected on desktop/mobile.
`frozen-influences-checks.json` records outcomes, final source identities, the
original fixture hash and screenshot hashes.

The final source/local archives are rebuilt after these records. The release
audit verifies matching source/public/dist/HTTP kernels and served assets,
unchanged tested production files, native/WASM study provenance, both native
outcomes, the ten successful browser workflows and exact ZIP contents.
This feature does not close the broader ASWING or experimental aircraft-validation
requirements.
