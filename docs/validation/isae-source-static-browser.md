# Static ASWING comparison in the browser

Updated 2026-10-26. The acceptance target remains archived **ASWING results
with unchanged inputs**, not experimental agreement. This increment completes
browser selection, section/sensor reporting and project preservation for the
bounded static formulation. It does not complete the full ASWING implementation
or turn the remaining reference differences into passes.

In **Settings → Structural static → Structural equations**, select
**ASWING static · zero offsets · experimental**. Existing midpoint equations remain
the default. The alternative supports lifting-surface beams with zero section
and distributed-CG offsets, rigid shear and rigid joints, including coupled
bending/torsion, finite axial stiffness and rotating concentrated-weight pylons.
Unsupported section laws, body charts, struts, engines, airflow and dynamics
are rejected. Selecting another analysis restores the existing equations and
reinspects the model.

The exact browser-tested [ST-5 project](../../examples/isae-st5-source-static-project.json)
is included in the examples and downloadable app. Use Open project, then Open
solution to inspect its saved result, or Run analysis to repeat the calculation.

Every inspection, edit and solve carries the paired interpolation/operator
selection. Saved cases and solutions retain it, and saved equilibrium identities
must agree. Old projects without this field retain their original semantics and
sealed solution checksums. These numerical settings do not alter literal `.asw`
text. The bridge accepts only complete supported policy pairs; it rejects
unimplemented settings rather than ignoring them.

## Section and sensor outputs

Interval forces and strains now follow the selected source constitutive law.
The averaged endpoint transform is generally nonorthogonal and is kept separate
from the physical frame used to draw the beam. Interval shell recovery uses
averaged endpoint shell properties and is labeled an estimate, not a point
sample. Each element also reports both conservative endpoint resultants using
the actual one-sided frames and section properties. Sensor strains use the
sensor anchor rather than a neighboring interval midpoint. CSV retains endpoint
sections separately, and reported shell maxima include both endpoint traces
and interval estimates. Exact historical ASWING exporter sampling is still
unverified.

## Verification

The offline built UI solves the unchanged original ST-5 model on the archived
70-interval grid in **3.68 s**. Measured startup is **40.94 s**, including verifier
preflight and browser/runtime initialization; it is separate from the solve.
The matching native bridge solve takes **0.77 s**, with residual
1.08×10⁻¹⁴. All **16,605** checked numerical values agree under the predeclared
2×10⁻⁸ absolute plus relative gate. The maximum absolute difference is
8.11×10⁻¹¹. Only the evaluation counter is excluded; no physical output is
excluded. The timing is one run on this host, not a speed guarantee.

The new project reopens its result byte-for-byte without another solve. A
historical ST-5 project also reopens with its exact original result, numerical
policy and sealed solution records. Leaving structural analysis clears the
incompatible result and reinspects with the default policy. The run makes no
HTTP requests after startup, has no page/network errors, and verifies desktop
and mobile layouts. Both screenshots were visually inspected.

Separate checks pass:

- 73 bridge/policy/regression tests, plus four unchanged default JSON outputs.
- 21 project, solution and UI-policy tests, including old checksum preservation.
- Eight independent recovery tests covering fully coupled stiffness, sided
  property/load jumps, rigid limits, rotating weights and sensor kinematics.
- The earlier 50 source-static, recovery and sensor regressions passed before
  the final endpoint-section cache/reporting cleanup; the final eight tests
  and reference restorations cover that cleanup.

Six previous ST-3/ST-5 states were restored without solving again. All physical
arrays and residuals are bit-for-bit unchanged. All 240 ST-5 archived-row
endpoint reports and 616 ST-3 endpoint traces match the prior independent
recovery exactly. The audit passes **7,893/7,893** checks. New interval/sensor
reporting differences are recorded separately and do not change equilibrium
or the archived endpoint comparisons.

| Original static case | Strict structural matches retained | Mesh checks retained |
|---|---|---|
| ST-3, 44 / 88 / 176 intervals | 220 / 270 at printed coordinate centers on each grid | 10 / 10 |
| ST-5, 70 / 140 / 280 intervals | 403 / 129 / 120 of 1,120 | 0 / 14, then 4 / 14 |

ST-5 remains close on the archived finite grid: forward/rear tip-deflection
differences are 0.00084% / 0.0086% and twist differences about 0.013%. Refinement
moves it away from the archived finite-grid result. No precision or mesh gate
was widened. At this stage the ST-3 coordinate-rounding witness had only been
checked for the midpoint formulation. The subsequent
[section follow-up](isae-source-section.md) independently checks the saved source
states and establishes the same 269/270 count on all three grids, using the
previously frozen shared coordinates. The tiny archived tip residual remains.

## Reproduction and remaining work

The [machine-readable report](isae-source-static-browser.json) identifies the
evidence bundle, retained failure and source pins. The one failed native harness
attempt stopped at the initial progress callback before Newton iteration; its
callback signature was corrected without a physics change. The successful
native and browser runs each perform one cold solve.

```sh
# First restore the prior integration evidence at its recorded /tmp path.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-source-static-browser.py prepare /tmp/my-static-native
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-source-static-browser.py run /tmp/my-static-native
npm run build
OPENSWING_CHROMIUM_EXECUTABLE=/path/to/chromium \
  node scripts/test-source-static-browser.mjs /tmp/my-static-browser /tmp/my-static-native
```

The [section follow-up](isae-source-section.md) adds a distinct general-section
static option with offsets, finite shear and distributed-CG gravity, preserving
the formulation described here. Remaining work includes other joint/load laws, consistent
aerodynamic and dynamic equations, and unresolved archived-output conventions
and numerical differences. EA averaging, unloaded arc for unsubscripted ds,
and exact historical use of the candidate spline remain declared assumptions.
See the [reference status](isae-aswing-reference-status.md) and preceding
[static integration study](isae-source-discrete-integration.md).
