# SA-1: discrete balance and geometry audit

SA-1 remains **19/154 registered native-output checks**, with all 22 baseline
jobs completed. This follow-up checks specific possible explanations left by the
[paper/history review](sa1-history-followup-20261027.md). No confirmed SA-1 kernel
defect or source-supported numerical correction was found.

## Consequences of the documented balances

For the literal straight, rigid SA-1 beam, `x=z=0` and `y=t`. Material arc
increments, physical arc increments, absolute span increments and segment-vector
lengths are therefore identical. Changing between these measures cannot explain
its force discrepancy. Current integration uses the material interval length in
`geometry.py`, `frozen_influence.py` and `aero.py`; Fourier `delta_theta` weights
belong to the circulation residual, not the force integral.

A duplicated ground station represents a **zero-length interval**. Drela's
[1999 paper](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf), printed p9
(PDF p10), places quasi-static force/moment constraints across that interval.
With `delta_s=delta_r=0`, it adds no distributed aerodynamic force or moment.
It does not justify subtracting a finite root strip or halving adjacent loads.
The actual surrounding historical station locations remain unrecovered.

The [unsteady description](../../.reference/asw_uns_theory.pdf), p39,
Eqs265–266 derives the global interval moment from **separate** arithmetic
averages:

```text
(m_bar + r_bar cross f_bar) delta_s.
```

Eq267 instead prints the average of the complete moment density. Taken literally
with the stated endpoint averaging convention, that expression differs by

```text
(delta_s / 4) (delta_r cross delta_f).
```

This is a notation/algebra inconsistency in the source, not an implementation
instruction. It cannot change total force. For SA-1, `delta_r` lies along y,
so the additional couple also has exactly zero y component: it cannot explain
the pitching-moment discrepancy.

Current [lifting-load transfer](../../openswing/source_coupled.py#L48) preserves
its declared strip wrench. It splits force P equally and assigns each endpoint
half of `C + (r_theta-r_bar) cross P`; the resulting global moment is exactly
`C + r_theta cross P`. Moreover, the registered SA-1 adapter uses the rigid
aerodynamic route, without structural reaction aggregation.

These identities exclude an arc-measure change, a ground-interval load correction
and a moment-arm correction as explanations for the SA-1 CL/Cm mismatch. They do
not establish how the historical executable recovered aerodynamic endpoint loads
from its circulation samples. In particular, interval-constant pointwise
circulation does not specify the sided velocity/force traces needed by an
endpoint-average rule.

## Mesh-source limits

The guide's KBREAK description (lines1338–1346) specifies zero-length interval
insertion at doubled breakpoints. The v5.67 revision notes (lines591–598) specify
automatic increases of insufficient NODE/I requests to the breakpoint minimum.
The v5.33 notes distinguish fuselage and lifting-beam symmetry allocation.
These are concrete allocation rules, but none supplies the background spacing
or smoothing formula.

A bounded public-source check found no underlying Fortran mesh routine in the
inspected repositories or wrappers. Published AVL blending and XFOIL curvature
paneling algorithms have no recovered link to ASWING's NODE implementation.
They are not adopted as substitutes. The SCN records remain qualified by their
missing display increment and unresolved model/output pairing.

## Conditional check of the recovered native distributions

The [metric diagnostic](sa1-scn-load-audit-20261027/metric-report.md) evaluates
the published rigid box-geometry rule at the three retained elliptical meshes.
It uses the literal CASEI model, declared natural cubic splines, and independent
arc integration. There is no aerodynamic or structural equilibrium solve.

| Printed interval count | Maximum predicted/native y difference | Positive stations within 0.00005 m, using central printed t |
|---:|---:|---:|
| 6 | 0.00454689 m | 1/3 |
| 12 | 0.00194816 m | 3/6 |
| 96 | 0.00009871 m | 44/48 |

The rule predicts the direction and much of the coarse tip contraction, but
does not establish exact historical geometry. The agreement counts do not
propagate uncertainty in the printed t coordinates. Natural spline boundary
conditions and the model/output pairing remain conditional. Tightening arc
integration changes the half-arc length by only 3.7e−14 m; numerical quadrature
error does not explain the remaining coordinate differences.

The literal CASEI model is planar and rigid, with zero prescribed profile drag,
mass and twist. Under that pairing, several native `Fn/f_aero` ratios imply an
interval length **shorter than its minimum printed spanwise displacement**.
For the first positive N6 interval, the implied length is at most 0.400724 m,
while the displacement is at least 0.40290 m. Thus replacing delta-t by true arc
length alone cannot reconcile the displayed scalar with the force decrement.
This is a rejection of that single-product interpretation, not a solver defect:
the exact native diagnostic projection and load recovery remain unresolved.

The registered inputs, solver, precision gates and denominator remain unchanged.
Exact historical node placement and circulation-to-load recovery are still the
missing evidence needed to turn this discrepancy into a justified implementation
change.
