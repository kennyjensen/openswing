# Complex section loads and elastic incidence

The common dynamic output recovery now includes `cm`, `f_aero`, `f_reac` and
`da_eff` for eigenmodes, harmonic transfers and one-sided initial-state spectra.
Their physical definitions are unchanged from the
[steady/time section outputs](section-outputs.md). Each value has `real` and
`imag` components; it is a perturbation about the loaded base, rather than the
base value or the magnitude of the total load.

Recovery differentiates the complete instantaneous quantity, including the
current section normal, current-length normalization, relative flow, local Mach,
distributed inertia and apparent mass. Direct input and rate terms use the same
stencil as the other dynamic outputs. The physical residual, dynamic pencil,
load laws and eigenvector normalization are unchanged.

A quantity absent or undefined at the base remains unavailable. In particular,
zero relative flow does not define an elastic-incidence tangent, even if all
four perturbed snapshots have nonzero flow. Nonlifting body strips have null
values for these lifting-section quantities. An existing body strip before a
lifting strip no longer prevents the Bode selector from discovering the
lifting-only fields at later stations.

## Units and browser use

Choose **Coupled eigenmodes**, then select the lifting beam and one of the new
**Modal quantity** options. Curves and mode CSV show real and imaginary values
per saved eigenvector amplitude. The animation's display scale does not change
these numbers.

For **Frequency response**, select **Aerodynamic strips**, a quantity and its
station. Bode plots, comparison curves and CSV use the stated input unit; an
initial-state spectrum includes one additional input time unit. Complex
incidence uses **radians** in these plots, CSV and JSON, matching the dynamic
rotation outputs. The steady/time Span loading view continues to display
incidence in degrees and store it in radians. The phase of a complex response
is a separate quantity and is displayed in degrees.

The unit of `cm` is dimensionless, and both force densities use input F/L.
`f_reac` excludes point masses and support reactions. The selected-field note
and exported definitions retain the included/excluded loads. Missing values in
older archives remain unavailable; no recomputation or zero substitution is
performed.

This increment does not add section channels to reduced-order output matrices
or establish original-ASWING modal/harmonic sampling parity.

## Independent verification

`scripts/verify-dynamic-section-outputs.py` uses three references:

- **Loaded-state output tangents.** A straight wing has prescribed stretch and
  positive/negative rotation about y, a finite body rotation rate, a gust, two
  eccentric distributed masses and a separate point mass. Complex directions
  vary section rotation, stretch, distributed acceleration, circulation,
  circulation rate and flap pitching moment. Analytical differentiation of the
  scalar force, incidence and Mach-correction expressions provides the expected
  values. The induced velocity direction uses the closed Glauert sine-series
  identity at a straight bound line. Cases include K/F, disabled K/L, changed
  difference step and two alternative L/T/F systems. These prescribed states
  are intentionally not equilibrium solutions.
- **Solved rigid-wing transfers and initial spectra.** An independent matrix
  of closed horseshoe integrals at the control points determines circulation.
  With the chord equal to one metre, the circulation mass matrix is
  `D = 2 I / (pi U)` when lag is enabled and zero otherwise. Harmonic circulation
  satisfies `(i omega D - W) Gamma = gust`; an initial disturbance satisfies
  `(i omega D - W) Gamma = D Gamma0`. The reference normal load is
  `rho [U Gamma + Gamma_dot]`, with the rate term omitted when K/L is disabled.
  For an initial spectrum, `Gamma_dot = i omega Gamma - Gamma0`. This checks
  the boundary term rather than treating the spectrum as a harmonic transfer.
  Flap Cm feedthrough is checked independently against its Mach correction.
- **Computed heave/pitch eigenmode outputs.** For the original sprung-wing
  example, independent linear load identities check every returned mode at two
  meshes and with lag disabled. Incidence is the pitch perturbation, circulatory
  force density is `rho (U + lambda) Gamma` with lag, and the normal apparent
  force is `rho pi/4 [-lambda^2 h + 0.1 lambda^2 theta + U lambda theta]`.
  All real mass in this example is concentrated, so it must not enter the
  distributed inertial density. These identities use computed mode coordinates;
  they verify output recovery, not independent eigenvalue accuracy.

Native boundary tests also cover undefined incidence at stagnation, repeated
output recovery, nonlifting strips and vacuum. The native 13-case study checks 1,360 complex values with maximum scaled
reference error 1.808e-10. Its modal comparison across native/WASM runtimes
first matches eigenvalues and then aligns arbitrary eigenvector phase; it
never rescales magnitude. Conjugate ordering and tied
largest state components can otherwise select different ordering or opposite
normalization signs.
The initial replay retained that sign mismatch as a failed comparison. Each
runtime independently checks its own physical output identities before any
cross-runtime phase alignment.

JavaScript and actual offline
browser workflows check units, raw complex CSV values, initial spectra, mixed
body/lifting selection, unchanged saved results and mobile layout.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-dynamic-section-outputs.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_dynamic_section_outputs.py
node --test tests/frequency-comparison.test.mjs
npm run build
node scripts/test-dynamic-section-outputs-wasm.mjs
npm run test:browser -- tests/browser/dynamic-section-outputs.spec.js
```

The new native batch recorded seven passes and one failure: its modal reference
incorrectly read circulation from the nonlifting support strip. The corrected
modal-only check passed separately. The 77-check native regression also passed,
covering modes, frequency response, initial spectra and reduced models. Thus
85 distinct targeted native checks pass across the recorded batches; this is
not a fresh full-project regression. All 37 selected JavaScript checks pass.

Two initial offline browser workflows passed. Visual review found repeated
Bode tick labels for a narrow response range. The plot now uses range-aware
precision and minimum relative padding. The affected section/spectrum workflow
and the existing forced-oscillator workflow then passed on the updated assets:
three distinct workflows, four passing runs. They check physical complex CSV,
missing body values, direct/rate terms, raw radians, unchanged results, distinct
ticks and mobile layout. Desktop/mobile screenshots were inspected.

The initial packaged-WASM comparison failed on raw modal vectors after each
runtime's independent physical checks passed. Phase-only alignment also failed.
The final replay matches eigenvalues before aligning phase, without rescaling
amplitude or relaxing the 2e-8 comparison tolerance. It passes all 13 cases:
2,720 section real/imaginary components plus 48 eigenvalue components, maximum
scaled native/WASM difference 5.921e-10. The records retain raw values,
mode assignments, phase factors, pre-alignment differences and both failed logs.
Conjugate ordering is not a physical discrepancy; phase and ordering changes
must not be mistaken for amplitude or load agreement without these checks.

`dynamic-section-outputs-checks.json` records terminal job outcomes and exact
source, asset, study/runtime and screenshot fingerprints. The release job is
`openswing-dynamic-sections-release-final`. Its final source/local archives are checked
by `/tmp/audit-openswing-dynamic-sections.py`, including ZIP contents/CRCs and
served bytes; the result is `/tmp/openswing-dynamic-sections-release-audit.json`.
No hosted app is updated. Full ASWING interoperability, original sampling,
section ROM channels and aircraft/experimental validation remain open.
