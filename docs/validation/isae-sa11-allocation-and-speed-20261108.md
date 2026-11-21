# SA-11: mesh allocation and an archived compressibility clue

2026-11-08 UTC. Allocating intervals by physical beam length does **not** repair
the pre-stall junction failure. All six predeclared cases converge in
circulation, remain inside their section lift limits, and fail local Mach.
A separate source-only audit finds stronger evidence of differing global
compressibility settings in the archived speed pairs. Neither investigation
changes production equations or the **163/9,184 at 5%** primary comparison.

## Allocation test

The preceding practical-resolution study assigned the same requested interval
count to each logical beam. Here the main wing is 3.147352 m long and each
upper winglet is 0.263456 m long. Define, before solving,

```
n_beam = max(4, ceil(n_main * L_beam / L_main))
```

This gives roughly equal mean interval length, retaining each beam's cosine
clustering, required breakpoints and Glauert midpoint rule. Three main-wing
requests of 64/128/256 give 6/11/22 intervals on each winglet. Mandatory main
breakpoints increase the total counts below.

The [extended manual](../../reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf#page=21)
describes per-beam node/mode controls, but does not establish this allocation
or SA-11's original mesh. The public
[FBHALE SetNodes](https://github.com/facebookarchive/FBHALE/blob/b4673025f664a199322f40db7ba159a5fa3e04aa/ASWing/WriteASWingFile/SetNodes.m)
likewise supplies a configured count for each beam; it does not recover native
defaults. This is an explicitly declared sensitivity test, not a default change.

Use the already disclosed bundled Joint correction and report-derived −4°
upper-winglet twist, alpha 1°, speed 240 m/s, density 1.2256 and speed-dependent
PG. The stall law and local Mach guard remain active. Original files remain
unchanged and these alternatives are not primary reference passes.

| Main request / each winglet | Actual total intervals | Maximum normal Mach, frozen | Maximum normal Mach, current wind |
|---|---:|---:|---:|
| 64 / 6 | 82 | 1.32920 | 1.16718 |
| 128 / 11 | 156 | 5.38165 | 1.87973 |
| 256 / 22 | 306 | 22.32266 | 6.91951 |

Every maximum occurs on the main wing immediately beside its outer junction.
The converged normalized residuals are below 9.04e-14; the smallest margin to a
stall limit is 10.36 transition widths, with **zero stalled strips** in all six
cases. The bound-field norm at these receivers is only 1.40–2.67 m/s, while
the wake-field norm is 347–7,597 m/s. These vector norms are not additive speeds.
The rejected peaks are discrete-model failures, not physical supersonic-flow
predictions.

Independent PG-space Biot–Savart integration reconstructs the worst velocities
within **4.82e-8 m/s**. Doubling the bound quadrature from 96 to 192 points
changes its result by at most 3.14e-10 m/s. Thus this allocation does not remove
the already identified wake interaction, even with many fewer winglet intervals.
No valid integrated-load comparison follows from these rejected states.

![Length allocation and local Mach](../../artifacts/isae/sa11-length-allocation-20261108/length-allocation.png)

[SVG](../../artifacts/isae/sa11-length-allocation-20261108/length-allocation.svg).
The plot was visually checked and follows the application color order.

Evidence: [frozen six-case plan](../../artifacts/isae/sa11-length-allocation-20261108/plan.json),
[results and independent checks](../../artifacts/isae/sa11-length-allocation-20261108/analysis.json),
[serial driver](../../scripts/verify-sa11-length-allocation.py),
[analyzer](../../scripts/analyze-sa11-length-allocation.py).
Each call ran in a separate bounded foreground process with one BLAS thread;
all are terminal. Recorded aerodynamic evaluation time totals 0.73 seconds,
excluding interpreter startup and source verification. No browser timing is claimed.

## Archived speed dependence

The source audit compares every row of the .75/.78 pair (actual speeds
255/266 m/s) for all four configurations. It independently rereads the original
tokens and tests overlap of the last-printed-digit rounding intervals. It also
checks the .70/.80 pairs as controls. No solver output or fitted parameter
enters this calculation.

| Configuration, .75→.78 | CL/CD/CDi/efficiency | Cm | Matching driver commands |
|---|---|---|---|
| Wing alone | All 41 row pairs overlap for each field | All 41 differ | Neither includes `kk`/`mm` |
| Wing extension | All 41 row pairs overlap for each field | All 41 differ | Neither includes `kk`/`mm` |
| Upper winglet | All 41 row pairs overlap for each field | All 41 differ | Neither includes `kk`/`mm` |
| Upper/lower winglets | All 41 row pairs differ for each field | All 41 differ | Both include `kk`/`mm` |

For the first three configurations, maximum changes in those four invariant
channels are below 0.000930%, while maximum Cm changes are 0.107–0.116%.
For upper/lower winglets, maximum CL/CD/CDi changes are 2.83%/2.84%/5.99%.
Every channel changes beyond its rounding intervals in all four .70/.80 pairs;
those eight drivers include `kk`/`mm`.

**Interpretation:** the observed coefficient invariance supports fixed global
PG Mach in the first three .75/.78 pairs, while the upper/lower pair exhibits
speed-dependent loading. This is evidence in addition to the command omissions
documented by the [earlier audit](isae-sa11-command-grouping-20261108.md).
It does **not** establish that fixed PG Mach was zero, authenticate the doubled
commands' parser behavior, or recover the missing startup state.

This pattern is consistent with the published equations. At fixed geometry,
global PG and incidence, circulation and induced velocities scale with speed;
the steady force coefficients can therefore stay fixed. Section pitching
moment still uses local normal Mach, which depends on true speed independently
of global PG. See Drela's steady description equations 64–73, 150–161 and the
[user guide's PG-Mach section](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
retained at [local lines 2413–2434](../../reference/aswing_doc.txt:2413).
The post-stall archived rows are retained in this source comparison; no
post-stall model repair or numerical validation is attempted.

The normalization conflict and original winglet input issues remain unresolved.
The exact original producing geometry and settings must still be established
before promoting an inferred setting to the primary adapter.

Evidence: [all eight speed-pair comparisons](../../artifacts/isae/sa11-speed-signature-20261108/analysis.json)
and [source-only audit](../../scripts/audit-sa11-speed-signature.py).
The original sixteen polars and driver hashes are preserved.

## Next action

Stop varying interval counts as a proposed repair for this junction. Use the
archived speed dependence to constrain the producing compressibility settings,
especially the distinction between global PG and local section-moment PG.
Continue the junction velocity/force investigation with that setup evidence;
do not infer native defaults from a filename or alter a core to obtain a pass.
SA-11 remains the active priority, with SA-2 stall-region work deferred.
