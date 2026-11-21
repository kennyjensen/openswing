# SA-11: whole-beam sampling explains the matched-grid drag discrepancy

2026-11-08 UTC. Restoring OpenSwing's existing whole-beam Glauert sampling
on the matched AVL endpoint grid reduces formal drag error from **12.63% to
0.043% at 0°**, and from **20.37% to 0.065% at 1°**. Formal lift is within
0.74% of the archived result at both angles. Every vortex endpoint is unchanged.

**Both production states still fail the local-Mach guard.** These force sums
are diagnostics of rejected states, not accepted predictions or new passes.
The result supports the production sampling and force laws; it does not fix
the winglet-root velocity or authenticate the archived producing mesh. No
default switch is needed: production already uses the whole-beam rule. The
earlier native comparison explicitly overrode receivers to match AVL's points.
The primary SA-11 fraction remains **163/9,184 at 5%**.

## Fixed inputs and the controlled change

The [authoritative index](aswing-authoritative-references.md) and its catalog
were consulted; all eight PDF hashes were verified. Drela's steady description,
**Eqs. 150–157, pp. 31–33**, specifies the Glauert-angle midpoint, its weighted
beam position, and distinct force/control receivers. **Eqs. 64–73, pp. 15–17**,
continue to govern velocity, force and section moment.

The two cases were declared before solving, following the
[21-state force budget](isae-sa11-rejected-force-budget-20261108.md). They use
the same report-derived −4° upper-winglet twist, disclosed bundled Joint
correction, original section properties, 240 m/s, density 1.2256, PG Mach
`240/340.21`, frozen influences, and 64 native-grid intervals. The original
ASW files, prescribed wake, zero mutual core, stall law and Mach guard remain
unchanged. Native AVL is not run again.

Only the receiver rule changes from the saved native stations to whole-logical-
beam Glauert sampling. The spanwise chord and other section properties are
sampled at the new stations by the existing production code. Source endpoints
agree **exactly** between the two constructions. Maximum force/control-point
movement is **18.639/17.527 mm**. Circulation is then solved afresh rather than
assuming that moving the control points leaves it unchanged.

The subsequent [receiver-location and moment audit](isae-sa11-root-moment-envelope-20261108.md)
locates this movement on the main wing. Winglet-root receiver positions remain
fixed to rounding; their velocity change comes from the re-solved circulation.
Native AVL's cosine receivers use angle midpoints within each section interval,
not generally arithmetic endpoint midpoints. The production ASWING rule uses
the whole logical beam's angle domain.

## Results

| Alpha | Archived CD | Native-receiver formal CD | Whole-beam formal CD | CD error, before → after | Whole-beam CL error | Maximum local Mach, before → after |
|---:|---:|---:|---:|---:|---:|---:|
| 0° | 0.00893824 | 0.01006747 | 0.00894208 | +12.63% → +0.043% | −0.730% | 1.25161 → 1.22339 |
| 1° | 0.01035910 | 0.01246918 | 0.01036583 | +20.37% → +0.065% | −0.692% | 1.57365 → 1.53418 |

Both solves converge below **5.09e−15** normalized residual and remain at
least **25.40 stall-transition widths** inside their lift limits. Each has
two Mach-rejected receivers, at the winglet roots. The maximum is on beam 2
at parameter **1.242731095816342**, with body force-point position
`[1.0576448468, 1.2427310958, 0.1530592318]` m.

The maximum relative circulation change is **3.13%/3.27%**. The force change
is mostly in near-field vortex drag, with smaller changes in profile drag:

| Alpha | Vortex CD, before → after | Profile CD, before → after |
|---:|---:|---:|
| 0° | 0.00280212 → 0.00170987 | 0.00726535 → 0.00723221 |
| 1° | 0.00519112 → 0.00312868 | 0.00727807 → 0.00723715 |

These are not replacements for Trefftz CDi. No section PG moment is evaluated
at the invalid receivers, and no clipped or partial moment is reported.

![Receiver sampling and the remaining Mach rejection](../../artifacts/isae/sa11-winglet-receivers-review-20261108/winglet-receivers.png)

[Standalone SVG](../../artifacts/isae/sa11-winglet-receivers-review-20261108/winglet-receivers.svg).
The figure was visually checked and uses the application palette order.

## Separating receiver and circulation effects

For each angle, four field replays cross old/new receiver rules with old/new circulation.
For a force functional `F(R,G)`, the exact symmetric difference assigns

```text
receiver contribution = 0.5 * [F(Rnew,Gold) - F(Rold,Gold)
                              + F(Rnew,Gnew) - F(Rold,Gnew)]
circulation contribution = total change - receiver contribution.
```

Under this decomposition, receiver changes account for **94.68%/94.52%** of
the drag change. This includes section resampling and assigns the interaction
equally between the two factors. The crossed fields are not equilibria. Their
nonzero tangency terms remain in the formal force law; they are not interpreted
as physical post-stall solutions. The actual solved states have negligible
stall drag. This decomposition is an accounting identity, not proof that
circulation could remain fixed during a physical receiver change.

## Verification and next constraint

An independent reconstruction uses straight-piece physical arc lengths to
evaluate Eqs. 151–157 without the mesh generator. It reproduces beam, force
and control positions within **4.45e−16, 8.89e−16 and 2.23e−15 m**, respectively.
Separate scalar force calculations and compensated reductions agree within
**5.56e−17 in coefficient units**. Saved/native field replays agree within
3.34e−10 m/s; the new production velocities reproduce exactly in the replay.
Source pins, artifacts and the exact two-factor decomposition are checked.

The two physical calls took **0.444 seconds combined**, excluding interpreter
startup, source verification and postprocessing. Each ran separately with one
BLAS thread and a 15-second call limit. Both jobs and the independent review
terminated normally. No production equation or original reference value changes.

The prior native-grid drag mismatch should no longer motivate changing the
published force law. Its receiver override was a material part of that
diagnostic discrepancy. The remaining task is the **local winglet-root velocity
and its use in the section-moment PG correction**, together with recovery of
the native producing setup. Preserve the root rejection and use the now-close
integrated forces as an additional constraint on any proposed explanation.
Agreement at two angles is not a full-polar validation.

The subsequent [0–5° sweep](isae-sa11-whole-beam-polar-20261108.md) now checks
all 21 archived rows in that range. Formal CD error stays within 0.241% and CL
within 0.731%, but every state still rejects at exactly two winglet roots.
The remaining archived 5.25–10° rows and original primary targets stay unchanged.

- [Serial driver](../../scripts/verify-sa11-winglet-receivers.py)
- [Predeclared plan](../../artifacts/isae/sa11-winglet-receivers-20261108/plan.json)
- [Two production outcomes and eight field replays](../../artifacts/isae/sa11-winglet-receivers-20261108/analysis.json)
- [Independent reviewer and plotter](../../scripts/analyze-sa11-winglet-receivers.py)
- [Verification receipt](../../artifacts/isae/sa11-winglet-receivers-review-20261108/verification.json)
