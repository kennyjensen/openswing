# SA-11: the remaining error extends beyond the moment rejection

2026-11-08 UTC. Replaying the 21 saved, report-minus4 upper-winglet states
shows that their **formal lift sums are within 0.60%** of the archive, but
their **formal total drag is 12.63–44.13% high**. Only two receivers exceed
Mach one. Those strips account for about **0.055% of sampled lifting area**
and **0.147–0.350% of formal profile drag**. Making the pitching-moment
correction finite would therefore leave a substantial drag discrepancy.

These are algebraic diagnostics of **rejected states**, not accepted loads or
new reference passes. No Mach clipping, source omission, force substitution,
input change or new equilibrium solve is used. SA-11 stays **163/9,184 at 5%**.

## Conditions and independent checks

The [authoritative index](aswing-authoritative-references.md) and source catalog
were consulted and all eight catalogued PDF hashes verified. Drela's steady
description, **Eqs. 64–70, pp. 15–16**, uses total bound-location velocity in
the lift and profile-force laws. Equation 73's section-moment correction is
undefined at these rejected receivers and is deliberately not evaluated.

The [earlier polar comparison](isae-sa11-winglet-polar-20261108.md) supplies
all 21 states from 0° through 5°, in 0.25° steps. They retain the report's −4°
upper-winglet twist, the disclosed bundled Joint correction, 240 m/s, density
1.2256, PG Mach `240/340.21`, frozen body-x influences, and **the matched native
AVL endpoint/receiver grid**. These are not OpenSwing's default whole-beam
receiver locations or authenticated archived ASWING settings. No angle is
chosen according to the resulting error. All states are pre-stall, with at
least 10.54 transition widths of margin, and all remain rejected.

The replay verifies each saved report and its artifact hashes. Current geometry
reproduces the saved source endpoints and receivers. Reconstructed local
velocities agree within **6.56e−10 m/s**. Independently written scalar cross
products, span projections and speed calculations reproduce the force terms
within **1.39e−17 in coefficient units**. Native AVL's integrated force is
reconstructed separately from its own circulation, velocity and bound-segment
vectors, agreeing within **3.34e−16**. Existing diagnostic/worker and status/scope
changes since the old snapshots are disclosed; aerodynamic modules are unchanged.

## Force budget

The lift force is `rho * Gamma * cross(V, span) * ds`. Friction and pressure
drag use the two corresponding terms of Eq. 70; its tangency/stall term is
retained too. All terms are projected onto the same freestream drag axis and
normalized with the supplied reference area. No strip is dropped.

| Alpha | Archived CD | Formal total CD | Error | Formal vortex CD | Native AVL near-field CD | Native AVL Trefftz CDi | Formal profile CD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0° | 0.00893824 | 0.01006747 | +12.63% | 0.00280212 | 0.00279978 | 0.00246264 | 0.00726535 |
| 1° | 0.01035910 | 0.01246918 | +20.37% | 0.00519112 | 0.00518370 | 0.00444069 | 0.00727807 |
| 5° | 0.02071910 | 0.02986162 | +44.13% | 0.02253609 | 0.02244694 | 0.01813393 | 0.00732553 |

Profile CD here includes friction, pressure and the stall term. The stall
contribution is at most **8.73e−13**, so it does not explain this discrepancy.
The archived `CD-CDi` is not assumed to equal profile drag: near-field and
Trefftz contributions must remain distinct in interpreting that subtraction.

OpenSwing's formal vortex drag differs from native AVL's near-field drag by
only **0.00000235–0.0000892**. Both are appreciably above the independently
computed native Trefftz value on this grid. Thus close Trefftz agreement with
the archive does not establish agreement of the total force calculation.
The retained output also separates using the actual bound-segment vector from
using the ASW beam tangent, so that conversion convention is not hidden.

The two rejected receivers contribute a small positive profile drag but
negative vortex drag. Simply omitting their forces would increase formal total
drag. That observation is an accounting check, not a proposed deletion or
evidence that their local velocity is physical.

## Consequence

The failure is not explained solely by an overly restrictive moment check or
by profile drag concentrated at two bad receivers. Keep the published force
law and Mach guard. The next controlled comparison should isolate **receiver
placement on the actual upper-winglet geometry**, holding source endpoints and
section inputs fixed, as the
[baseline moment study](isae-sa11-moment-speed-20261108.md) already did for the
wing alone. This can distinguish the diagnostic native-grid force bias from
the production sampling issue without changing the wake or fitting parameters.
The [two-angle follow-up](isae-sa11-winglet-receivers-20261108.md) now completes
that check: whole-beam sampling reduces formal CD errors to 0.043%/0.065%,
while both local-Mach rejections remain. It supplies no new primary passes.

- [Replay driver](../../scripts/audit-sa11-rejected-force-budget.py)
- [Predeclared scope and source pins](../../artifacts/isae/sa11-rejected-force-budget-20261108/plan.json)
- [All 21 budgets and verification errors](../../artifacts/isae/sa11-rejected-force-budget-20261108/analysis.json)

The bounded replay ran serially with one BLAS thread and terminated normally.
There are no new solver calls or progress observations from this diagnostic.
