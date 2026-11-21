# SA-1 / SA-5: separating the remaining induced-drag differences

The ten remaining modified-mesh CDi failures are consistent with low
circulation-based lift. Lower span efficiency **partly offsets** those drag
deficits. This saved-data decomposition identifies no shared physical cause
and changes no solver, reference, tolerance or acceptance count.

For fixed reference aspect ratio, ASWING's Technical Description §8.1,
Eqs. 207–211 defines
`e = (CLi² + CYi²)/(π AR CDi)`. Writing current/native ratios as `rD`, `rE`
and `rL²` gives `rD = rL²/rE`. The exact ordered percentage-point split is:

`100(rD−1) = 100(rL²−1) + 100*rL²*(1/rE−1)`.

The first term is the squared-lift contribution; the second is the efficiency
contribution. It is algebraic accounting, not independent causal attribution.

| Case and incidence | Intervals | CDi error | Lift² contribution | Efficiency contribution |
|---|---:|---:|---:|---:|
| SA-1, 18.091° | 200 | −4.660279% | −5.268265 pp | +0.607986 pp |
| SA-1, 18.091° | 400 | −4.671269% | −5.253209 pp | +0.581939 pp |
| SA-5, 18° | 200 | −3.306204% | −3.741449 pp | +0.435245 pp |
| SA-5, 18° | 400 | −3.350115% | −3.702167 pp | +0.352053 pp |

The [complete ten-row table](../../artifacts/isae/sa1-sa5-drag-decomposition-20261030/report.md)
also includes SA-1 at 14.097°, 15.095° and 16.006° on both meshes. Across
those eight SA-1 failures, inferred CLi is 1.757–2.670% low; the two SA-5
values are 1.869–1.889% low. This uses Trefftz CLi, not total near-field CL.

Native CLi is inferred from printed native efficiency and CDi under the
documented coefficient convention and symmetric zero-side-force assumption.
It is not an independent native circulation measurement, nor evidence that
the entire circulation distribution differs by a uniform multiplier. Saved
SA-1 CYi is zero; saved SA-5 CYi is below 3.6e−15 in magnitude. Conditional
half-last-print-unit sensitivity is below 0.912 ppm in inferred native CLi,
holding literal reference dimensions fixed. These numerical bounds do not
change the printed targets or constitute a rigorous interval acceptance test.

The [earlier SA-5 review](isae-sa5-root-loading-20261029.md) already describes
the shared low-loading pattern, and the
[SA-1 load review](sa1-differences-20261027.md) already infers circulation lift
from efficiency/CDi and moment. The exact ten-row split adds quantitative
accounting; it does not establish a new stall-law, wake, or discretization
defect. Efficiency can reflect both loading shape and numerical quadrature.

All **80 saved-data identity/provenance checks pass**, with no production
imports or flow calls. SA-1 remains **146/154** and modified SA-5 **166/168**.
The inputs are the retained original modified-mesh SA-1 results and the
fresh SA-5 zero-efficiency rerun; no new current-kernel flow comparison is claimed.

- [Script](../../artifacts/isae/sa1-sa5-drag-decomposition-20261030/analyze.py),
  [protocol and 56 input hashes](../../artifacts/isae/sa1-sa5-drag-decomposition-20261030/protocol.json).
- [Complete values, printing sensitivity and checks](../../artifacts/isae/sa1-sa5-drag-decomposition-20261030/report.json),
  [terminal receipt](../../artifacts/isae/sa1-sa5-drag-decomposition-20261030/terminal-receipt.json).
