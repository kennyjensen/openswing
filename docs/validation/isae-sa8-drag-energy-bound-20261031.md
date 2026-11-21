# SA-8: a circulation-independent drag bound

2026-10-31. At the isolated fore wing's −4° operating point, the native total
drag cannot be reached by changing only the circulation distribution on the
three tested cosine meshes while preserving the documented force formulas
and matching native induced drag and span efficiency. This remains true when
both reference quantities are allowed their provisional 3% errors.

The bound does not use a stall strength or require circulation equilibrium.
It therefore also excludes a standalone change of stall strength as a remedy
at this point, under the stated geometry, force and output conventions. It
does not authenticate those conventions in the historical executable.

| Requested intervals | CD upper bound, printed CDi/efficiency | CD upper bound, 3% CDi/efficiency |
|---:|---:|---:|
| 40 | 0.010370898 | 0.010387618 |
| 64 | 0.010391054 | 0.010424227 |
| 128 | 0.010463465 | 0.010564099 |

Native CD is **0.0120774**, with a 3% lower acceptance limit of **0.011715078**.
Even the loosest ceiling is **12.53% below** the native value. Both signs of
circulation lift are included, and no particular circulation shape is assumed.
The original SA-8 count remains **373/504**. The separate strength-20 result
remains **432/504**; its failed fore-wing CD errors retain median **11.29%**
and maximum **15.66%**. These bounds add no acceptance checks or passes.

## Assumptions and derivation

The literal isolated model has one straight untwisted wing, constant chord
0.129 m, span 2.1805 m, zero section moment, no body/point/engine loads and
constant `Cdf+Cdp=0.020`. The calculation uses uniform stationary flow,
zero PG Mach, current wind-aligned vortex geometry and the published
Glauert-angle midpoint sampling. Reference area/span are 0.544767 m² and
2.04250 m. The meshes have 40, 64 and 128 intervals, with the center node
retained; 40 is a documented-size diagnostic, not a recovered native grid.

The [steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 67, 70 and 207–211, supplies the force and Trefftz definitions.
For this straight wing let `x = Gamma/U`, and let `w = A x` be induced
normal velocity divided by U. Direct integration of the filaments gives

```
CDi = xᵀ Q x
Q = −[diag(ds) A + Aᵀ diag(ds)] / Sref
CLi = ellᵀ x,  ell = 2 ds / Sref
CLi² = (pi Bref² / Sref) CDi efficiency
```

Near-field and Trefftz induced drag coincide for this particular straight
lifting line and shared circulation quadrature. `Q` is positive definite
on each tested grid. Native CDi and efficiency intervals consequently bound
an entire ellipsoid of possible circulations, not just the converged solution.

At the control points, normalized flow tangency is `t = t0 + B x`, where
`t0 = sin(−4° + 3.9°)`. With `k_i = chord ds_i` and `C = Cdf+Cdp`, the total
profile contribution is

```
CDprofile = (C/Sref) sum[k_i sqrt(1+w_i²)]
            + (4/Sref) sum[k_i t_i² / sqrt(1+w_i²)]
```

The first term is bounded above by the concavity of the square root. The
second is bounded above by replacing its denominator with one. Weighted
velocity and tangency norms are then bounded over the circulation ellipsoid.
Its center is the minimum-induced-drag circulation at a specified `CLi`;
the remaining energy and the full native `CLi` interval bound the distance
from that center. Both signs of `CLi` are checked.

The closure equations are deliberately absent. Thus these ceilings allow
circulations that no stall model would actually produce, making the exclusion
more conservative. A different physical influence operator, force definition,
profile law, geometry or output reference can invalidate these assumptions;
those possibilities remain open.

## Independent checks

The producer and verifier import no OpenSwing modules. The verifier separately
reconstructs the filament fields, reads the original native tokens with exact
rational rounding intervals, and checks the operator-norm bounds through
positive-definite matrix inequalities. Their margins exceed the estimated
floating-point rounding scale by more than 100 times; a relative `1e-6`
guard is retained in the upper bounds. These are verified numerical bounds,
not a formal interval-arithmetic proof.

There are six bounds: three meshes times two acceptance policies. All exclude
the native CD interval. An additional 216 manufactured circulations satisfy
the permitted lift/induced-drag constraints and obey the ceilings. They are
checks of the relaxed mathematical set, not new equilibrium solutions.

The independent formulas also reproduce the two previously saved physical
solutions: maximum CD difference `1.74e-18`, CDi difference `1.12e-21`, and
CLi difference `8.68e-19`. No nonlinear solver, browser or parallel worker is
started. The native matrix audit and independent verifier both exit normally.

Evidence: [declared plan](../../artifacts/isae/sa8-drag-energy-bound-20261031/plan.json),
[bounds and saved-field replay](../../artifacts/isae/sa8-drag-energy-bound-20261031/analysis.json),
[independent verification](../../artifacts/isae/sa8-drag-energy-bound-20261031/verification.json),
[receipt](../../artifacts/isae/sa8-drag-energy-bound-20261031/receipt.json).

Production equations, native targets, tolerances and registered counts stay
unchanged. This narrows the source of the SA-8 discrepancy to assumptions
beyond circulation alone within the tested discretizations. The complete
ASWING implementation and the SA-6–SA-10 comparisons remain unfinished.
