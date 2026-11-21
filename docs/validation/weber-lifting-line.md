# Tabulated swept-wing aerodynamic-coordinate study

This study turns the [primary planform reconstruction](sa2.md#evidence-needed-for-a-matched-experimental-reconstruction)
into an original, importable [ASW input](../../examples/weber-tabulated.asw).
It verifies the aerodynamic coordinate conversion and an independent vortex
calculation. It does **not** establish a matched experimental wing or resolve
the swept-line refinement problem. The production kernel and web UI are unchanged.

## Coordinate construction

Let `c_s(y) = x_TE(y) - x_LE(y)` be streamwise chord from the tabulated outline.
The beam axis follows `x_q(y) = x_LE(y) + c_s(y)/4`, with `Xax = 1/4` and
normal chord `c_n = c_s dy/ds` on each straight segment. Doubled stations retain
the separate linear segments and their one-sided normal chords. The last two
constant-span table entries describe the tip edge; they are not additional
span stations. The limiting streamwise tip chord is two inches.

With `dCLda = 2π`, the [steady ASWING formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 155–157, places zero-wind force points at `x_LE + c_s/4` and control
points at `x_LE + 3c_s/4`. Also, `∫c_n ds = ∫c_s dy`. Six separate mesh and
lossless/canonical serialization checks verify these identities: maximum
coordinate/frame difference is 4.22e-15 and area difference is 4.29e-14 m².
The requested 24/48/96/192/384/512 intervals become 70/94/142/238/430/558 after
mandatory table stations are included.

These are aerodynamic-coordinate and integrated-area identities. The normal
strips drawn by the beam model do not reproduce the measured outline near the
root and curved tip. The standalone figure explicitly overlays both outlines.
That difference must not be hidden by calling this an exact geometric model.

## Independent calculation and refinement outcomes

Four references use adaptive Biot–Savart integration along the finite bound
segments and separately integrated straight wake rays. A separate dense linear
system determines circulation; the reference then recovers force-point velocity
and Kutta–Joukowski forces and moments. The production vortex kernel is not used
by that calculation. Known straight-line principal values are handled by the
table segment identities. The comparisons cover both current and frozen
influences at 70 and 94 actual intervals and 2.1° incidence, with PG Mach zero.
Across 1,336 compared physical components, the maximum scaled difference is
1.15724e-11. This verifies the implemented discrete model, not its experimental
accuracy or continuum limit.

The refinement matrix contains **126 recorded cases: 30 computed and 96
rejected**. It uses the six meshes, five positive incidence angles, both K/F
choices and fixed-zero/speed-derived PG choices, plus six zero-incidence cases.
Speed is 49.6824 m/s and nominal density is 1.2256 kg/m³. Stall is disabled;
section moment and profile drag are zero. These are explicit inviscid inputs,
not fitted RAE 101 properties. Zero-incidence loads vanish as expected.

At 2.1°, current influences/PG zero give CL = 0.119614, 0.118025 and 0.117238
at 70, 94 and 142 actual intervals. The next three meshes are rejected:
maximum local normal Mach reaches 1.10787, 2.22988 and 2.97512. Frozen-influence
cases have the same qualitative problem. Small changes in integrated CL do
not override these local failures. Rejected cases retain the failing location
and velocity rather than valid-looking aerodynamic coefficients. Near-field
drag and far-wake induced drag retain their separate definitions.

The preliminary `/tmp` probe used stall limiting and is retained separately;
its results are not mixed with this inviscid study.

## Browser portability and reproduction

Sixteen packaged-WASM replays pass: four computed cases compare 272 physical
components, and twelve matched rejections compare 120 diagnostic components.
Maximum scaled native/WASM difference is 2.28176e-13. Two WASM geometry checks
and one independently integrated reference also pass.

The dedicated offline browser workflow passes with the literal input, stall
explicitly disabled, five computed cases and their exports, and the
512-requested-interval rejection. It checks the current/frozen selection and
healthy WebGL2 rendering. Inspected geometry, desktop loading and mobile
rejection captures are retained alongside the numerical records. This host uses
the documented Mesa test configuration in the README; physical-GPU and
cross-browser coverage remain separate work.

The first browser run failed when its redundant mesh-field fill invalidated
the mesh without a following change event. The corrected test skips filling an
unchanged mesh value, as the existing SA-2 workflow does. It retains the same
physical tolerances and adds current/frozen-mode assertions. The initial failure,
test source and error state remain in the checks record. Production code did not
change. The standalone plot's overlapping logarithmic minor tick labels were
also corrected without changing its data.

```sh
.venv/bin/python scripts/reconstruct-weber-planform.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-weber-lifting-line.py
.venv/bin/python scripts/plot-weber-lifting-line.py
npm run build
node scripts/test-weber-lifting-line-wasm.mjs
OPENSWING_WEBGL_DRIVER=mesa npm run test:browser -- tests/browser/weber-lifting-line.spec.js
```

Results, source fingerprints and figures are retained as `weber-lifting-line.json`,
`weber-lifting-line-wasm.json`, `weber-lifting-line-checks.json`, and
`weber-lifting-line.svg`/`.pdf`/`.png`. The original full native collection launched
before this example was added and stopped without a final report. Its incomplete
record is retained separately. The new fixture's targeted format check passes
(one test); the new complete native collection includes this example. Neither
the study nor its browser workflow establishes a full-suite pass.

Manufactured-section thickness, viscous section inputs, tunnel corrections,
pressure-tube configuration, the published moment-reference discrepancy and a
physically justified refinement treatment remain open. No experimental polar
is fitted or relabeled as a passing comparison. All broad requirements remain Partial.
