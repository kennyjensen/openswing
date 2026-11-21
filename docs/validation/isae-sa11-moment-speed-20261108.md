# SA-11: speed-dependent moment separates velocity sampling from total loads

2026-11-08 UTC. The archived 255/266 m/s pitching-moment difference provides
a useful additional check on section velocity. For the baseline's independently
sourced slope-6.34 hypothesis, using the documented whole-beam receiver rule
instead of native AVL receivers reduces the difference error from **7.11–23.15%
to 1.17–2.18%**, with unchanged vortex endpoints. The curved-extension fields
reproduce the difference within **0.624%** in three valid comparisons; the fourth
crosses the local Mach limit at the higher speed and yields no moment.

This supports the current published section-moment law and isolates a sampling
effect. It does not recover the archived input or repair the winglet junction.
Production equations, original inputs and primary comparisons are unchanged.
**SA-11 remains 163/9,184 at 5%.** SA-2 stall work remains deferred.

## Why the speed pair is informative

The [earlier speed-signature audit](isae-sa11-allocation-and-speed-20261108.md)
found CL, CD, CDi and span efficiency invariant within printed precision for
the baseline, extension and upper-winglet .75/.78 pairs, while Cm changes.
The archived speeds are **255 and 266 m/s**, not values inferred from filenames.
The same original tokens and their rounding intervals are checked again here.

The [authoritative index](aswing-authoritative-references.md) and catalog were
consulted. Drela's steady description, **Eqs. 64–73, pp. 15–17**, defines lift
and section moment from the full relative velocity at the bound force point.
The [user guide's PG-Mach section](../../reference/aswing_doc.txt:2413) explicitly
keeps the local normal-Mach correction to section Cm independent of global PG.
**Eqs. 150–156, pp. 31–32**, define the Glauert-angle sampling for each beam.

For these unforced rigid states at fixed global PG, geometry and incidence,
circulation and velocity scale with true speed U. Force coefficients and their
moment arms are therefore invariant. The only changing pitching-moment term is
the section coefficient's local PG factor. Set `eta_i = |V_perp,i| / U` and
`G_i = chord_i² * cm0_i * span_y,i * ds_i / (Sref * Cref)`. The published law gives

```text
Delta Cm = sum_i G_i * eta_i² * [
    1 / sqrt(1 - (266 * eta_i / sound_speed)²)
  - 1 / sqrt(1 - (255 * eta_i / sound_speed)²)
]
```

Density cancels. A fixed moment-reference translation also cancels when the
force coefficients are invariant. This makes the difference more informative
about section velocity than the much larger total pitching moment. It still
depends on section Cm, geometry and reference dimensions; it cannot authenticate
unknown inputs by itself. A local Mach at or above one makes the replay invalid,
without a clipped denominator or an absolute-value square root.

## Retained conditions and controlled receiver change

Eight completed low-speed fields are reused: baseline slopes 7.0 and 6.34 at
0°/1°, and the curved extension at 0°/1° on 70/134 actual strips. All are the
previously declared zero-global-PG/alternative-normalization diagnostics, with
frozen body-x influences. Reference dimensions and the donor slope come from
the separate original cant0 input, as documented in the
[fixed-PG study](isae-sa11-fixed-pg-candidate-20261108.md). No value is fitted
to the moment difference. Controls, frame motion, gusts and propulsion are absent.

Four baseline 266 m/s outputs were already saved. The independent moment replay
reproduces their full Cm changes to **2.78e-16**, checking the derivation against
actual completed evaluations. Extension higher-speed moments are replays, not
new accepted aerodynamic solves.

Two new baseline solves keep the slope-6.34 input and the native 64-strip endpoint
grid. Only the control/force receivers change to the normal whole-logical-beam
Glauert rule. Source endpoints agree within **2.23e-16 m**. Maximum receiver
displacement is **4.992 mm** for force points and **4.694 mm** for control points.
Circulation is solved again with the existing stall law and Mach guard.
Both states converge, with at least **41.66 stall transition widths** of margin.

| Configuration | Alpha | Archived Delta Cm | Native receivers: error in Delta Cm | Whole-beam receivers: error in Delta Cm |
|---|---:|---:|---:|---:|
| Baseline, slope 6.34, 64 strips | 0° | −0.000292 | +7.107% | +1.172% |
| Baseline, slope 6.34, 64 strips | 1° | −0.000291 | +23.145% | +2.177% |

An exact symmetric decomposition separates changes in geometric section weights
from changes in the velocity-dependent dynamic-pressure/PG factor. The velocity
factor accounts for approximately **98–99%** of the receiver-induced change.
This includes the circulation's response to the new control points; it is not
a claim that circulation was held fixed in these two solves.

The original slope-7.0 control gives difference errors of **9.47% and 38.08%**
with native receivers. Both source alternatives remain recorded. Total-Cm
agreement alone was misleading: the slope-6.34/native-receiver result was within
0.2% in total Cm while its speed increment was up to 23.15% high.

| Curved extension | Alpha | Archived Delta Cm | Predicted Delta Cm | Difference error |
|---|---:|---:|---:|---:|
| 70 strips | 0° | −0.000310 | −0.000308067 | −0.624% |
| 134 strips | 0° | −0.000310 | −0.000310015 | +0.0047% |
| 70 strips | 1° | −0.000309 | −0.000307299 | −0.550% |
| 134 strips | 1° | −0.000309 | Unavailable: local Mach 1.005887 at 266 m/s | Unavailable |

Each observed difference has a rounding interval of ±0.000001 under the retained
half-last-digit assumption. Only the fine, zero-degree extension replay lies
inside that interval; close agreement is not exact agreement. The rejected
extension field is retained, with no substitute moment or deleted comparison.

![SA-11 moment speed dependence](../../artifacts/isae/sa11-moment-speed-review-20261108/moment-speed.png)

[Standalone SVG](../../artifacts/isae/sa11-moment-speed-review-20261108/moment-speed.svg).

## Implication and verification

The new evidence does not support globally replacing full bound-point velocity
with freestream velocity in the moment law. It supports retaining the documented
whole-beam sampling rule in production and declaring native AVL receiver overrides
as a distinct diagnostic setup. The curved extension gives a useful check of the
local-Mach dependence before its tip-field guard fails.

The upper-winglet junction remains unresolved. Its invalid local flow cannot be
accepted merely because integrated circulation agrees with native AVL. Historical
inputs/mesh settings and the near-field representation still need reconciliation.
Even the two new baseline states retain total-CD errors of approximately 32–34%
with their unchanged baseline profile inputs; this audit is not a complete-polar
validation or a new primary pass.

The two physical calls took **0.144 seconds combined**, excluding imports and
artifact verification. They ran serially with one BLAS thread and terminated.
An independent 50-digit Decimal replay checks nine valid moment differences;
the tenth retains its high-speed rejection. Source and saved-output hashes,
original reference tokens, force/moment bookkeeping and the exact receiver
decomposition are checked. The intervening bridge-only diagnostic transport
change and status notes are disclosed against the prior snapshots; aerodynamic
modules are unchanged.

- [Saved-field audit](../../scripts/audit-sa11-moment-speed.py) and [eight-case evidence](../../artifacts/isae/sa11-moment-speed-20261108/analysis.json)
- [Two-case driver](../../scripts/verify-sa11-moment-receivers.py) and [predeclared plan](../../artifacts/isae/sa11-moment-receivers-20261108/plan.json)
- [Independent replay/plotter](../../scripts/analyze-sa11-moment-speed.py) and [verified analysis](../../artifacts/isae/sa11-moment-speed-review-20261108/analysis.json)
