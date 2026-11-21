# AE-3 original source catalog

Source extraction only. No solver, production module, or upstream MATLAB/shell
script was executed. All 44 original family files match the immutable upstream
manifest. The catalog retains all 636 native export lines, 576 output cells,
102 echoed setup cells, and 113 embedded postprocessor values. This is coverage
evidence, not numerical or historical validation.

| Native output category | Cells across six exports |
| --- | ---: |
| base_coefficient | 36 |
| centroid | 54 |
| control_derivative | 36 |
| mass_inertia | 198 |
| normalized_rate | 36 |
| stability_derivative | 216 |

The six `Straight_20O.fmat_001` through `_006` files pair by basename and speed
sequence with `Straight_20O.asw` and `Roll_rate.sh`. The driver builds six points
at 27.0934, 38.5020, 43.0429, 47.2340, 50.9245, and 59.4556 m/s, then applies `!!F1 1.0`
to every point. The pinned ASWING manual explicitly documents that `!!` applies
a parameter to all current stack points (lines 2192–2204). These are finite
F1=+1 file-control states. The manual permits arbitrary flap units; degree
calibration is supported by the report/postprocessor rather than intrinsically
encoded in the native format. No numeric unit conversion is applied. Their
base rolling coefficient differs from the local flap derivative; neither is
a zero-control result.

Each export gives Mach 0, PG factor 1, rho/rhoSL 1, alpha negative zero, beta 0,
and all body and normalized rates 0. The literal model specifies rhoSL 1.2256,
gravity 9.81, Sref 0.185, Cref 0.15, Bref 1.2192, and moment origin (0, 0, 0). Dynamic
pressure and speed printed intervals agree with that density. The force frame
is explicitly stability axes, x forward and z down: CX=Fx/qS, CY=Fy/qS, CL=-Fz/qS;
Cl=Mx/qSb, Cm=My/qSc, Cn=Mz/qSb. Derivative headings retain their original
u/V, alpha, beta, p, q, r, and dFlap1 labels without an inferred unit conversion.

The exact legacy reconstruction remains qualified: the export title is
`Mowe_temp`, whereas the literal model title is
`Ailereons_Reversal_Straight_wing`; no executable/build or serialized state
proves their identity. The driver has no NODE instruction, and the archived
node arrays are absent. Its `% / 4 23 / P / d` constraint commands are retained
without inventing unseen table defaults. Any new grids and numerical settings
must be declared reconstruction choices.

All six literal models remain in the inventory, including Roll and the five
straight-wing control spans. Duplicate control knots and both raw Weight rows
are preserved. The Weight Mg scale is exactly 0, so both physical weights are
zero without editing the original records. Literal control scales differ:
20O uses 0.0581/-0.0102, 40O uses 0.0686/-0.0107, and 60O/80O/95O use
0.0686/-0.0102; Roll uses zero control slopes. The primary report's prose
0.0581/-0.0107 does not replace any literal model values.

The complete `Post_analysis.m` arrays contain 43 ASWING-labelled locked values,
43 modified ASWING-m locked values, and 27 modified roll values. The locked
counts are 8/8/9/9/9 across 20O/40O/60O/80O/95O; the plots select only 18 rows
from each 43-value set. Every unplotted row, including negative reversal-branch
values, is retained. `Post_analysis.asv` provides duplicate numeric witnesses,
not additional independent target slots, plus a separate seven-value q vector
and literal annotations V_reversal=61.468 and err_V=0.89408. Those annotations
are not independently exported native ASWING scalars.
Native 576 + original 43 + modified 43 + modified roll 27 = 689 unique output
targets before any deliberate mesh expansion. The 102 native setup values,
speed arrays, experimental digitizations and XFOIL outputs are separate
source evidence and do not inflate that denominator.

The embedded arrays are blocked pending independent generating setups. Their
20O speed grid differs from the six native exports, and postprocessing uses
rho 1.292 instead of literal/native 1.2256. The plot's dCl/d(delta_A) label does
not establish equivalence to the native signed dF1 derivative. Modified roll
values lack independently recovered angular units, control/mount setup, and
producer; their speed formulas use experimental CSV pressures, while `b` has
no assignment after `clear all`. The 95O experimental fit uses q80O. These
issues are preserved rather than executed or repaired. No reversal speed is
invented by fitting or interpolating a sign change.

`temp_analysis.sh` creates nine 60O speeds and changes only the current point
with single `!F1 1.0`; it does not supply the native driver's `!!F1` evidence.
`Roll_analysis.sh` prescribes seven nonzero roll rates at 50.9314 m/s for Roll;
it has no retained native export and is not paired to the modified free-roll
arrays. All five CSV tables (including empty cells), four XFOIL polar tables,
airfoil coordinate rows, shell scripts, original model blocks, EPS and PNG
inventory are retained or pinned, with experimental/section-input provenance
distinct from native ASWING output. Swept-wing experimental data have no
paired swept model/export here.

Numeric fields retain original raw lines, tokens, signs of zero, line numbers,
whitespace-column and character positions, and Decimal half-last-place
precision. Unit multipliers, heading identifiers, and syntax numbers remain
in the raw numeric ledger without being labelled output targets. Extraction
verification checks every native and literal-array token position and the
complete category counts. No widened tolerances or fitted inputs are used.

Regenerate with `.venv/bin/python scripts/extract-isae-ae3-reference.py`;
verify the frozen output with the same command plus `--check`.
