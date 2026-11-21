# Wake-core radius / chord

The ASWING K/W setting is exposed under **Circulation representation** as
**Wake core radius / chord**. Its dimensionless value defaults to 0.25.
The [public user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
and steady formulation equation 161 specify

`source radius = max(ratio × local chord, current interval length)`.

The interval-width floor remains active even at ratio zero. Reducing the ratio
below that floor cannot sharpen the wake without refining the mesh. Interactions
within the same physical lifting beam use zero core, including across logical
beam boundaries. Other physical beams and external sensor, body, engine,
point-object and flow-survey samples use the configured source radii. Ground
images inherit the core selected for that source/target pair. This preserves
the existing image convention; it is not new evidence for oblique compressible
wall parity. The ideal far-wake Trefftz diagnostic retains its own formulation.

The common instantaneous residual computes the radii on current geometry, so
equilibrium, time response and linearized analyses share the setting. Reports
include the ratio, minimum/maximum source radius and number of intervals limited
by spacing; lifting-strip exports include each source radius in input length
units. These are source radii, not the zero-core same-surface influence values.
Nonfinite, negative, nonnumeric and boolean ratios are rejected. Overflowing
effective radii are diagnosed without imposing an arbitrary dimensionless cap.

OpenSwing cases, saved equilibria and time checkpoints preserve the setting.
Older records missing it use 0.25. A saved time launch uses its stored setup even
if the live controls differ. A steady solve instead corrects a saved physical
guess under the current requested settings. These files do not implement legacy
ASWING `.set` interoperability.

## Independent reference

The original `examples/wake-interaction.asw` contains two rigid rectangular
surfaces. The upstream surface has span 2 m, chord 2 m and incidence 3 degrees;
the downstream surface has span 1.5 m, chord 0.6 m and incidence 1 degree. Their
quarter-chord axes are at (x,z) = (0,1) and (3,1.05) m. The freestream is along
positive x at 30 m/s. A sensor sits close to the downstream wake encounter.

`scripts/verify-wake-core.py` constructs cosine-spaced endpoints and Glauert
midpoints analytically, independently of the production mesh. It integrates
`dl × r / (4π (r² + radius²)^(3/2))` adaptively along each bound segment and each
semi-infinite wake. It then solves the independent flow-tangency matrix and
computes force-point velocities and circulation forces. Separate line integrals
predict three external velocity samples, including the sensor location.
The reference uses neither production vortex kernels nor the circulation solver.

The [native study](wake-core.json) covers **15 cases**: 4, 8 and 16 intervals per
surface at ratios 0, 0.25 and 1; Mach 0.6 with solid and free-surface images at
ratios 0.25 and 1; and two alternative consistent length/time/force systems.
It checks circulation, forces, external velocities and source radii against the
reference, with source hashes verified at both ends of the run. The packaged
WebAssembly replay checks the same quantities against both native results and
the independent references. Source/runtime hashes accompany both artifacts. The maximum scaled native
reference error is **6.329e-15**. The [WASM replay](wake-core-wasm.json) passes
**708 physical comparisons**, with maximum scaled native difference
**7.772e-16** and independent-reference error **6.384e-15**.

All **three offline browser workflows** pass, including the existing Fourier
workflow and the new control/case/flow/time-launch and legacy-case/default/error
workflows. Six JavaScript project-data checks also pass. Desktop/mobile controls
and the exported figure were visually inspected. The targeted native regression passes **141 tests**, including all **17 new
wake-core tests** for validation, independent line integrals, the physical-beam
exemption, spacing/current-geometry radii, saved launch/restart and corrected
steady reuse. This is not a fresh full-repository regression. Final archive
gates are recorded in the latest STATUS entry.

The [SVG](wake-core.svg) and [PDF](wake-core.pdf) show the surface circulations
and upstream source radii. Changing the core can materially change downstream
lift in this deliberately close encounter. Agreement with the line integrals
verifies the specified regularized model, not the physical accuracy of an
impinging real wake or exact ASWING executable parity. The spacing-floor cases
do not constitute a zero-core continuum convergence study.

Reproduce with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-wake-core.py
npm run build
node scripts/test-wake-core-wasm.mjs
.venv/bin/python -m pytest -q tests/test_wake_core.py
npm run test:browser -- tests/browser/wake-core.spec.js
.venv/bin/python scripts/plot-wake-core.py
```
