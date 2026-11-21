# Straight-wing SA-1 comparison

This study compares OpenSwing with the archived ASWING 5.96 polar and the
experimental coefficient series published in the
[ISAE ASWING validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation).
The experimental series is ISAE's digitization/integration attributed to
[Applin, NASA TM-110148 (1995)](https://ntrs.nasa.gov/citations/19960001217).
It is not an independent reduction of the original pressure measurements.

The exact external files are pinned at repository revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`, with byte counts, SHA-256 and Git
blob hashes in [sa1-sources.json](sa1-sources.json). Original model, script,
data and report files are fetched into `.reference/isae-sa1`, which is excluded
from the source and local-app archives. The downloaded shell script is inspected
as evidence and never executed by these tools.

## Reproduce

```sh
.venv/bin/python scripts/fetch-sa1.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-sa1.py
.venv/bin/python scripts/plot-sa1.py --preview /tmp/sa1-comparison.png
npm run build
node scripts/test-sa1-wasm.mjs
npm run test:browser -- tests/browser/sa1.spec.js
```

The native study is [sa1.json](sa1.json); its browser-runtime comparison is
[sa1-wasm.json](sa1-wasm.json). Standalone [SVG](sa1.svg) and [PDF](sa1.pdf)
figures show predictions and experimental differences. Source and runtime
hashes identify the versions tested. Rerun the build after creating reports to
include them in the downloadable source archive.

## Setup and unresolved source differences

The archived `.asw` is used unchanged: a rigid rectangular mirrored wing of
span 5.9 m, chord 1 m, reference area 5.9 m², section lift slope 6.2832/rad,
zero twist and section moment, and lift limits ±1.2. The drag coefficients
are Cdf = 0.00352562 and Cdp = 0.00771413. Speed is 47.9 m/s and density is
1.2256 kg/m³. The empirical stall parameters retain OpenSwing's published-theory
defaults, Ks = 40 and Δcl = 0.05; none of these parameters is fitted to the data.

The accompanying 2024 report, *Experimental validation of ASWING. Part I:
Aerodynamics*, by Romain Jan, gives different prose settings on page 25:
limits ±1.5, Cdf = 0, Cdp = 0.01 and 40 circulation nodes. The archived
script instead requests 200 nodes. This study reproduces the archived input
and identifies that conflict; it does not claim to reproduce both setups.

The script specifies speed but not its Prandtl–Glauert Mach mode. OpenSwing
therefore reports two separate cases: fixed PG Mach 0 and PG Mach V/a
(approximately 0.140795). Neither is asserted to be the recovered original
setting. The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
documents both modes and the independent local-Mach section-moment correction.

The first two columns of each experimental CSV are used. The additional
`Lifting_Line` column pair is a separate numerical series and is excluded.
Lift and drag have different incidence samples; each coefficient is computed
at its own recorded angles without interpolation or alignment. The archived
ASWING force/coefficient normalization is checked against the printed values'
individual rounding intervals.

## Recorded results

The native study records 171 cases. Across the archived incidence grid, the
largest 200-to-400-interval change is 3.41e-6 in CL and 2.81e-7 in CD.
The model/reference discrepancies below are much larger than these mesh changes.

| PG setting | CL RMSE vs experiment | CD RMSE vs experiment | Max CL difference vs ASWING | Max CD difference vs ASWING |
|---|---:|---:|---:|---:|
| Fixed zero | 0.039854 | 0.020949 | 0.028796 | 0.000981 |
| V/a | 0.040885 | 0.020523 | 0.027574 | 0.001404 |

Near 18.091° the experimental CD is 0.15. At that experimental angle,
OpenSwing gives 0.0966812 for fixed-zero PG and 0.0976170 for V/a. The archived
ASWING row at its independently rounded 18.091° gives 0.0962122. Neither
numerical convergence nor the alternate PG choice closes the experimental
drag deficit. The unmodified ASWING comparison also retains a lift difference
near stall; exact original settings and version behavior remain unresolved.

## What the checks establish

Both PG choices are evaluated at 24, 48, 96, 200 and 400 cosine-spaced intervals
over the full wing. Experimental comparisons use 400 intervals. The study
records every finite-mesh difference, signed reference discrepancy, RMSE and
maximum absolute error. Its numerical-resolution gates apply only to mesh
changes; there is no assertion that forces an experimental or ASWING comparison
to pass.

Additional checks integrate reported strip forces/moments, check coefficient
normalization and span, verify the analytical zero-incidence drag
Cdf + Cdp = 0.01123975, test positive/negative incidence symmetry, and verify
dynamic-pressure scaling. The packaged WASM replay repeats selected mesh,
Mach, symmetry and measured-angle cases, including spatial circulation samples.
The browser workflow imports the actual external input and exercises mesh
changes, both Mach choices and result export with networking disabled.

The 30° and 60° symmetry probes have no experimental reference here. At 60°,
the speed-derived PG case exposes different low-residual roots for separately
solved positive and negative incidence. Reflecting the positive root provides
another valid negative-incidence residual solution: the problem is branch
selection, not evidence that the asymmetric result is physically correct.
The failed symmetry diagnostic is retained in the report. The separate 90°
probe records an explicit solver failure if one occurs; it is not silently
omitted or substituted into the measured polar. Numerical convergence,
small residuals and native/WASM agreement are separate from physical validation.
Exact ASWING settings and executable parity, independent pressure reduction,
measurement/digitization uncertainty, deep-stall robustness and broader aircraft
and experimental coverage remain open.

The completed packaged replay covers 18 cases and 756 physical values, with
maximum scaled native/WASM difference 5.91e-9. Both final offline browser
workflows pass. That workflow exposed and verified a UI correction: incidence
and sideslip now accept arbitrary decimal values instead of requiring
half-degree increments. The original 18.091° input is preserved.

Later source audit, 2026-10-06: the pinned SA-1 script also toggles K/F once.
The public guide prints fast=T as the default, which suggests current/slow
influences only if startup settings retained that default. The historical study
used current influences; the original startup state is not recovered. Its
numerical results and hashes remain historical and unchanged. The subsequent
[SA-2 study](sa2.md) explicitly compares both K/F choices.
