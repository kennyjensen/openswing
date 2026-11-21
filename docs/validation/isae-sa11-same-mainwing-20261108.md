# SA-11: isolate the winglets with an identical main wing

2026-11-08 UTC. **The same-main-wing control exposes a substantial near-field
drag sensitivity to the main-wing mesh, even with the winglet mesh unchanged.**
At CL = 0.5 and 240 m/s, the 62-interval main-wing trial reproduces ASWING's
Trefftz induced-drag reduction within **0.115%**, but total drag reduction is
still **18.22% too weak**. The 32-interval pair instead overstates total drag
reduction by **37.03%**. This is a diagnosis, not a solver correction or proof
of mesh convergence. No refinement criterion was added to primary acceptance.

The **21/48 paper-focused primary score** and **1,060/9,184 original archive
score** are unchanged. These explicitly alternative controls are not added to
either total. All missing/rejected cases remain required in their scopes.

The new [control page](../../public/isae-sa11-paper/same-mainwing.html) is served
at `/isae-sa11-paper/same-mainwing.html`. It includes the comparison plot,
force decomposition, verification and downloadable control ASW/mesh files.

## A controlled removal, with no airfoil fitting

The prior [aligned comparison](isae-sa11-paper-aligned-20261108.md) showed that
the original baseline changes main-wing airfoil properties as well as removing
winglets. To isolate the device effect, this study starts from the verified,
report-derived upper-winglet model and removes **only its Joint block and
Beam 2 / Beam 3 blocks**, with two explanatory comment lines added.

The complete Beam 1 text and all reference rows remain unchanged. Preflight
and saved-result checks establish exact equality of the main-wing node and
frame arrays, material intervals, source endpoints, receivers and sampled
section data between the two models. The main wing retains **32 explicit
intervals**, and the upper model retains **16 intervals on each winglet** under
the existing 0.0164659927127284 m minimum. This is not the original archived
bare-wing file; its section data and mesh differ from that original.

The [authoritative index](aswing-authoritative-references.md) and catalog were
consulted and the ISAE Part I and Drela steady PDF/text hashes authenticated.
Jan **p.35 / Figure 22 p.39** motivates comparing a common aircraft with wingtip
devices; **Appendix D** supplies the geometry context. The inherited report
−4° upper-winglet twist and Joint correction remain explicit. Drela's steady
load equations and documented frozen-influence setting remain unchanged.
The producing native input and mesh have not been recovered.

Fifty new states were prescribed before running: **0°–6° in quarter-degree
steps at 240 and 272 m/s**. The extension to 6° supplies the bare-wing CL = 0.7
bracket. Frozen influences, density 1.2256, PG Mach V/340.21, original stall
law and zero shared-surface core remain fixed. The 43 already verified
upper-winglet states are reused without additional physical calls.

All 50 new states are valid, with maximum local normal Mach **0.70410** and
at least **11.36 stall-transition widths** of lift-limit margin. This control
requires no post-stall repair or bypass of the local-Mach guard.

## Absolute bare-wing agreement and the winglet effect

The control passes **6/12 diagnostic paper samples**: all six CL checks at
1°, 3°, 5° pass, with errors **1.23–1.38% low**. All six equal-lift CD checks
at CL 0.3, 0.5, 0.7 fail, with errors **5.52–11.54% high** (median **9.17%**).
These are an alternative-input result, not new primary passes. The smaller
lift error does not by itself resolve the drag discrepancy.

Both members of this OpenSwing pair have identical main-wing data and nodes,
so their difference now isolates adding the winglets within the declared
model. The historical ASWING pair remains qualified by its unknown generating
setup. At equal lift, the 32-interval control gives:

| Mach label | CL | Archived ASWING ΔCD | Shared-main-wing OpenSwing ΔCD | Overstatement of reduction magnitude |
|---|---:|---:|---:|---:|
| 0.70 | 0.3 | −0.00083175 | −0.00123534 | 48.52% |
| 0.70 | 0.5 | −0.00276893 | −0.00379425 | 37.03% |
| 0.70 | 0.7 | −0.00551965 | −0.00745423 | 35.05% |
| 0.80 | 0.3 | −0.00087421 | −0.00128278 | 46.74% |
| 0.80 | 0.5 | −0.00288372 | −0.00392566 | 36.13% |
| 0.80 | 0.7 | −0.00574363 | −0.00770180 | 34.09% |

The winglet-induced CL increase at 1°, 3°, 5° is also **13.92–15.94% larger**
than the archived increment. A small absolute error on each configuration can
therefore hide a larger error in the device effect. These derived increments
are diagnostic constraints and are not counted again in primary completion.

## Change the main-wing mesh, leave the winglets unchanged

The follow-up prescribed **six solves at 240 m/s**: bare-wing angles
3°, 3.25°, 3.5° and upper-winglet angles 2.5°, 2.75°, 3°. These bracket CL = 0.5.
Only the main-wing mesh changes from the existing explicit 32 intervals to
cosine-64 with the same minimum, giving **62 actual intervals**. Both models
have exactly the same new main mesh. The upper-winglet source endpoints,
receivers and geometry remain **identical** at 16 + 16 intervals.

All six states are valid, with maximum normal Mach **0.63170** and minimum
stall margin **17.87 transition widths**. No winglet refinement or additional
minimum-spacing adjustment was used.

| At 240 m/s, common CL = 0.5 | Archived ASWING | Main 32 / winglets 16 | Main 62 / winglets 16 |
|---|---:|---:|---:|
| Total ΔCD | −0.002768932 | −0.003794251 | −0.002264526 |
| Separate Trefftz ΔCDi | −0.002633414 | −0.002856068 | −0.002636424 |
| Total drag-benefit error | — | 37.03% too strong | 18.22% too weak |
| Trefftz benefit magnitude error | — | 8.45% high | 0.115% high |

At 3° incidence, the lift increment changes from **0.03142177** to
**0.02831651**, against native **0.02750100**: the finer-main result is within
**2.97%**. These are useful loading/induced-drag checks at this sampled point,
not evidence that every circulation distribution or SA-11 case is validated.

The drag-change budget isolates the numerical sensitivity:

| Contribution to upper-minus-bare ΔCD at CL = 0.5 | Main 32 | Main 62 | Change |
|---|---:|---:|---:|
| Main-wing vortex force | +0.00004908 | +0.00117840 | +0.00112932 |
| Winglet vortex force | −0.00420504 | −0.00379635 | +0.00040869 |
| Main-wing other strip forces | +0.00000631 | +0.00000073 | −0.00000558 |
| Winglet other strip forces | +0.00035540 | +0.00035269 | −0.00000271 |
| **Total** | **−0.00379425** | **−0.00226453** | **+0.00152973** |

“Other” is the remaining profile/leakage strip force after independently
subtracting the Eq.67 circulation force. There are no body, engine, apparent
or circulation-rate drag terms in these states. The reconstructed partitions
sum to the actual force-projected CD. Main-wing and winglet vortex terms
account for about **74% and 27%** of the change, with the other forces offsetting
about 0.5%. Although the winglet sampling points did not move, the changed
main-wing discretization changes their flow and circulation.

Trefftz CDi remains a separate quantity. **Native CD − CDi is not labelled
native profile drag**, and no Trefftz-plus-profile replacement for the
documented near-field force law is proposed. These results narrow the next
investigation to how near-field loads are sampled and accumulated on the main
mesh, while preserving the documented force/receiver construction as the
control. They do not establish an algorithmic defect or a converged value from
two meshes, and they do not require previously passing winglets to use 64
intervals.

![Same-main-wing comparison](../../artifacts/isae/sa11-same-mainwing-20261108/same-mainwing.svg)

## Verification and retained evidence

The 50 control calls ran in 17 foreground batches, at most three serial calls
per process. The six mesh controls ran in two more batches. Every process used
one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall seconds.
No new rejection, timeout or interrupted solve occurred. The control's maximum
recorded batch work was **6.73 seconds**, total **59.94 seconds**, peak RSS
**292.05 MiB**; the six-call follow-up peaked at **285.10 MiB**. These are local
Python observations, not browser performance measurements.

Independent zero-core vortex calculations agree with all 56 saved velocities
within **5.93e−16 of freestream**. Maximum new circulation residual is
**3.97e−16**. Saved force/moment reductions, source-table identities and the
exact model/mesh edits pass their checks. Force-budget closure is within
**3.65e−17** in CD. A separate Decimal reduction checks all baseline samples,
lift/drag increments and the mesh comparison, authenticating **502 pins**;
its maximum numeric difference is **1.43e−13**, including percentage values.

Preparation initially used a text regex that included whitespace following
the main-beam End line; it was corrected before the plan was written or any
solve ran. No physical result was discarded or rerun. The plot was visually
inspected. No production equation, default, tolerance or primary scope changed.
Browser, Vite, build and background solver tests remain unstarted.

- [Control plan and exact removed blocks](../../artifacts/isae/sa11-same-mainwing-20261108/plan.json),
  [control ASW](../../artifacts/isae/sa11-same-mainwing-20261108/model.asw),
  [importable mesh](../../artifacts/isae/sa11-same-mainwing-20261108/mesh-import.json).
- [All control results and force budget](../../artifacts/isae/sa11-same-mainwing-20261108/analysis.json),
  [independent field check](../../artifacts/isae/sa11-same-mainwing-20261108/verification-wing_alone.json),
  [Decimal/source verification](../../artifacts/isae/sa11-same-mainwing-20261108/comparison-verification.json).
- [Six-call mesh plan](../../artifacts/isae/sa11-same-mainwing-mesh-20261108/plan.json),
  [verified comparison](../../artifacts/isae/sa11-same-mainwing-mesh-20261108/analysis.json).
- Drivers: [control](../../scripts/verify_sa11_same_mainwing.py),
  [mesh follow-up](../../scripts/verify_sa11_same_mainwing_mesh.py),
  [control reduction](../../scripts/analyze_sa11_same_mainwing.py),
  [mesh reduction](../../scripts/analyze_sa11_same_mainwing_mesh.py),
  [independent score check](../../scripts/check_sa11_same_mainwing_scores.py),
  [plot/page generator](../../scripts/plot_sa11_same_mainwing.py).
