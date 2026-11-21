# SA-11: section-input differences explain the pre-stall lift bias

2026-11-07. A fixed input diagnostic reduces the baseline wing's pre-stall
CL error from **7.27–7.58% to at most 0.124%** by replacing its section lift
slope with the **6.34/rad already specified in every other SA-11 model**.
CDi then agrees within 0.133% and CM within 0.391% at the four examined states.
No solver equations or original input files were changed.

This is evidence of a likely mismatch between the supplied baseline section
properties and the archived producing configuration. It does **not** establish
which input produced those ASWING tables. The primary comparison remains
**163/4,592 at 5%**; none of the alternative-input matches is added to it.

The subsequent [native AVL comparison](isae-sa11-avl-baseline-20261108.md)
independently reproduces the same bias and its reduction at 240 m/s and 0°/1°.
Using 6.34 brings both native AVL and production OpenSwing lift/CDi within
0.5% of the archived values on a shared diagnostic mesh. All four production
states are pre-stall and below the local Mach guard. This strengthens the
input-mismatch evidence; it does not recover the original producing file.

## Independent source evidence

The public baseline and extension have the same main-wing geometry, twist,
zero-lift angles and section pitching-moment coefficients. They differ in
these airfoil properties after applying the literal ASW multipliers:

| Property | Baseline `wing_alone.asw` | Extension main wing |
|---|---:|---:|
| `dCLda`, per radian | 7.0 | 6.34 |
| `Cdp` | 0.01818 throughout | 0.00133, 0.00158, 0.00146, 0.00246 by span region |
| `Cdf` | 0 throughout | 0.0055, 0.0068, 0.0065, 0.0061 by span region |
| `CLmax` | 3.0 | Default 2.0 |

The upper-winglet, upper/lower-winglet and cant-zero files also specify 6.34
and the same main-wing pressure/friction distributions as the extension.
Their unrelated input/attachment issues remain; this is a text/property
audit, not a successful validation of those configurations.

The report's SA-11 discussion (page 35) says MSES supplied reasonable airfoil
parameters but does not list exact values. Appendix D (pages 65, 67 and 68)
shows Mach contours and geometry, not the numerical `dCLda`, `Cdp`, `Cdf` set.
Both figure pages were rendered and visually inspected. The retained public
history supplies no earlier baseline input, as established in the
[complete refresh](isae-sa11-focus-20261107.md).

## Predeclared diagnostic

Four states were selected before running: incidence 0° and 1°, each at
240 and 272 m/s. Each state used four separate input choices: original,
extension slope only, extension drag properties only, and both transfers.
The values came from the independent extension input; none was fitted.

All sixteen calls retained nominal 64 intervals, the identical generated
mesh, dynamic PG Mach, evolving influences, density, reference values,
geometry, `alpha`, `Cm`, `CLmin`, `CLmax`, stall parameters and local-Mach
guards from the registered comparison. The extension's extra tip geometry
was not copied. Parsed round-trip models and all mesh arrays were checked to
ensure that only the named properties changed. All four original replays
reproduce the saved seven-field predictions within 1e-12 scaled error.

| Input choice | Maximum absolute CL error | Signed CD error range | Maximum absolute CDi error | Maximum absolute CM error | Diagnostic matches at 5% |
|---|---:|---:|---:|---:|---:|
| Original | 7.579% | +19.002% to +25.615% | 14.977% | 7.364% | 4/28 |
| Extension slope only | 0.124% | +14.077% to +22.380% | 0.133% | 0.391% | 20/28 |
| Extension drag only | 7.834% | −1.397% to −0.147% | 14.977% | 7.587% | 12/28 |
| Extension slope and drag | 0.375% | −6.270% to −3.340% | 0.133% | 0.596% | 24/28 |

The seven fields include both forces and their coefficients. These are
alternative diagnostics on four states, not independent additions to the
registered scope. Signed error is `(prediction − reference)/abs(reference)`.

For the combined transfer, the remaining drag discrepancies are:

| Speed | Incidence | CL error | CD error |
|---:|---:|---:|---:|
| 240 m/s | 0° | +0.259% | −3.340% |
| 272 m/s | 0° | +0.273% | −3.978% |
| 240 m/s | 1° | +0.375% | **−5.324%** |
| 272 m/s | 1° | +0.361% | **−6.269%** |

Changing only pressure/friction coefficients leaves circulation and CDi
identical in the saved paired evaluations. The small total-lift differences
come from the profile-force projection. Thus the lift-slope and drag-input
effects have been separated rather than hidden in a fitted total correction.

## Numerical evidence and limitations

All sixteen calls completed their convergence, force reconstruction and
normalization assertions. Fifteen complete raw outputs are retained. Their
maximum circulation residual is 8.23e-16, maximum section-normal Mach is
0.93203, and minimum distance to a stall limit is 40.51 transition widths.
The first original replay's recorder encountered a NumPy-boolean JSON error
after those assertions; its partial file retains all seven predictions.
Those values were recovered without rerunning the physical call. Its full raw
output was not reconstructed, and it is excluded from the three diagnostic
extrema above. The corrected recorder serializes before creating a result file.

This study does not resolve the native producing input, circulation/node
settings, the 0.75/0.78 normalization conflict, or the fine-grid swept-tip
local-flow failures. It does not justify replacing the original baseline or
claiming mesh convergence. The remaining combined-input drag failure at 1°
is pre-stall and should be investigated separately. The original model in
the workbench's example selector remains unchanged.

## Reproduction

- [Frozen plan and source/module hashes](../../artifacts/isae/sa11-section-inputs-20261107/plan.json)
- [All scalar errors and result hashes](../../artifacts/isae/sa11-section-inputs-20261107/analysis.json)
- [Serial driver](../../artifacts/isae/sa11-section-inputs-20261107/run.py)
- [Recorder correction and continuation](../../artifacts/isae/sa11-section-inputs-20261107/continue.py)
- [Independent saved-result assessment](../../artifacts/isae/sa11-section-inputs-20261107/analyze.py)

Four foreground batches, one BLAS thread, at most four solves per batch.
No background solver processes, altered reference values, fitted constants,
relaxed validity gates, or post-stall repairs.
