# AE-3: complete native finite-control batch

All six archived `Straight_20O` finite-control states now have completed
coefficient comparisons on both declared meshes. The batch finished all **50
jobs in 66.68 seconds**: 12 computed states and 38 explicit blocked/inventory
records. Every computed state passes all 29 physical checks; none matches all
six archived coefficients. AE-3 and the full ISAE collection remain unfinished.

The [source catalog](isae-ae3-reference.md) accounts for all 44 original files,
six models, 576 native output cells and 113 separately qualified values embedded
in the original postprocessors. All unplotted script rows remain included.
The [default registry](isae-suite.md) now has 14 adapters, 3,992 jobs and 65,786
required scalar slots across selected scopes in 24 of 41 families; 17 families
still lack adapters. Registration is separate from execution and agreement.

| Scope | Distinct original scalar targets | Required mesh slots | Computed slots |
|---|---:|---:|---:|
| Six finite-control coefficients at six native states | 36 | 72 | 72 |
| Stability and control derivatives | 252 | 252 | 0 |
| Real/apparent mass, inertia and centroids | 252 | 252 | 0 |
| Normalized-rate report outputs | 36 | 36 | 0 |
| Embedded original ASWING locked-control arrays | 43 | 43 | 0 |
| Embedded modified-ASWING locked-control arrays | 43 | 43 | 0 |
| Embedded modified-ASWING roll arrays | 27 | 27 | 0 |
| **Total** | **689** | **725** | **72** |

Five other original models remain explicit inventory jobs with zero invented
targets. The 102 native setup echoes, experimental curves and duplicate backup
witnesses are separate source evidence. Modified-code arrays are not promoted
to native ASWING outputs. Unsupported values remain unavailable, never zero-filled.

The 72 computed slots contain **50 printed-precision matches**, representing
25 distinct source cells: 24 zero-reference cells and the final CX value.
There is no complete six-coefficient state match. The rolling coefficients
show substantial differences throughout the six-speed sequence:

| Speed (m/s) | Archived Cl | OpenSwing, 80 intervals | OpenSwing, 160 intervals |
|---:|---:|---:|---:|
| 27.0934 | -0.002056 | -0.001562894 | -0.001575255 |
| 38.5020 | -0.001957 | -0.001238636 | -0.001252539 |
| 43.0429 | -0.001878 | -0.001020419 | -0.001035107 |
| 47.2340 | -0.001759 | -0.000737837 | -0.000753259 |
| 50.9245 | -0.001578 | -0.000386569 | -0.000402473 |
| 59.4556 | 0.000450 | 0.001272751 | 0.001260742 |

[All six coefficients and both meshes](isae-ae3-native-coefficients-20261027.png)
are plotted with the original print-precision error bars. The complete
[CSV](isae-ae3-native-coefficients-20261027.csv) preserves all 36 reference
cells and 72 predictions. The grids give similar curves, while the archived
rolling coefficient and most CX values differ. This does not establish mesh
convergence or identify the discrepancy's cause. No reversal speed is inferred
by fitting or interpolating these points.

The replay preserves the literal `.asw` bytes, stiffnesses, aerodynamic slopes,
zero-scaled Weight records and reference area 0.185, chord 0.15 and span 1.2192.
`Roll_rate.sh` names the model and six speeds; `!!F1 1.0` applies F1=+1 to every
stack point. These finite coefficients differ from the local derivatives.
Native flap units remain file-defined. The exported `Mowe_temp` title differs
from the retained model title, so exact historical model identity is qualified.

The current solve uses the source structural operator, literal density 1.2256,
zero rates, Mach 0, updated influences and mounted equilibrium. Treating driver
IAS as TAS, identity pose, gravity, core ratio 0.25, startup constraints and
continuation are declared reconstruction choices. Original node arrays are
unknown. Prospective 80/160 nominal cosine grids produce 82/162 actual intervals
because root and flap breakpoints remain mandatory. Neither grid was selected
after seeing reference agreement.

All 12 worker processes were reaped. Each made one cold solve and one fresh
residual evaluation after restoring the saved state, with no retries. All 348
physical checks passed, including residual, force/moment balance, clamp,
source/setup identity, independent wrench normalization and restoration parity.
Original half-last-place reference gates are unchanged. The runner exits 1
because reference differences and unsupported scopes remain.

Validation includes 318 existing suite tests, 41 adapter tests and nine distinct
new integration tests. One initial integration assertion expected a later guard
but was correctly rejected earlier; its corrected source-speed mutation test
passes. The initial failed assertion and correction logs are retained in the
[evidence directory](isae-suite-ae3-20261027/). There are also 16 source extraction
checks and 14 construction-only checks. The 123-module numerical kernel remains
unchanged; this batch makes no new browser execution claim.

The [machine report](isae-suite-ae3-20261027.json),
[independent summary](../../artifacts/isae/ae3-summary-20261027/summary.json),
[full run](../../artifacts/isae/ae3-20261027/report.json) and
[independent audit](isae-suite-ae3-20261027/independent-audit.json) preserve all
results and source identities. Missing-family coverage remains the development
priority. The [ST-1 audit](isae-st1-readiness-20261027/report.md) now accounts for
197 native structural scalars and identifies a position-only sensor capability
needed for its first unchanged input. Within AE-3, analytic derivatives of the
same source equations, inertia/report outputs, free-roll/reversal settings and
unpaired variants remain explicit implementation work.
