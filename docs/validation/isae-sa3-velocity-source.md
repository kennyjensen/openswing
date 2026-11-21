# SA-3 force-point velocity source review — 2026-10-25

No source-supported production correction has been established. The target remains reproduction of the tested archived ASWING outputs; experimental agreement is not required.

ASWING separates the velocity used for force (equation 67 at the bound force point) from circulation tangency (equations 200/203 at the downstream control point). Current source preserves this separation. Equations 154–158 prescribe the relevant interpolation, positions and normal. The same-surface core is zero; changing W cannot fix this single-surface case. The inspected ASWING documents do not resolve the curved-bound self convention. See the [steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) and [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt).

The [JVL 2.20 theory](https://web.mit.edu/drela/Public/web/jvl/jvl.pdf), pages 36–38, gives a positive-Gamma curvature self velocity for a shallow curved vortex-sheet patch. A is the patch area, not an airfoil cross-section; no thickness data are needed. The two-endpoint closure is unspecified. This is adjacent-method evidence, not documented historical ASWING policy. The [official JVL page](https://web.mit.edu/drela/Public/web/jvl/) offers 2.16 after discontinuing 2.20 for jet-force behavior. Its inspected VVOR code uses a small same-component core and diagonal bound omission, so paper and downloadable implementation must be distinguished.

The parent's fixed-Gamma analogue, using A=chord*ds at 398 interior elements, increases CD by 0.000004447570048 overall and 0.0000001599397975 in the inner 90% span. It therefore does not explain the positive near/far excess of 0.0006945512600. At the tips, maximum curvature-times-length is 1.619 and force-point offset/length is 0.2044, violating the shallow local premise. The analogue changes only the Kutta–Joukowsky contribution; it is not a new converged solution. The two endpoint corrections remain undefined.

The previously proposed independent reconstruction of equations 154–158 was
completed by the later geometry and accurate-arc audits. The
[2026-10-28 continuity review](../../artifacts/isae/sa3-collocation-audit-20261028/summary.json)
confirms that seven relevant code blocks remain identical. Corrected candidate
force/control-point differences are at most 3.47e−15/1.18e−14 m. The actual
corrected run retains its force points but not complete control-point/normal
arrays; the receipt distinguishes those evidence scopes. Repeating this check
is not a pending task, and it establishes no new geometry correction.

Historical NODE I100 arrays, circulation representation and spline endpoint
conditions remain unestablished. The manual specifies cubic splines; the current
default uses natural splines. Do not move tangency to the force point or project
the force point onto a segment merely because a result becomes closer. Those
changes require independent source support.

`review.json` contains the formula, exact assumptions, saved report values and bounded next-test contract. `source-pins.json` supplies primary locators and continuity pins. This task made zero production imports, physics calls, solves, tests or repository edits. All newly downloaded third-party documents, renders and source files under `primary-local-only/` are excluded from the evidence archive; retain their hashes and URLs only.
