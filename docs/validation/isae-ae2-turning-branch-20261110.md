# AE-2: two verified equilibria at identical incidence

The current equations admit **two distinct positive-deflection equilibria at
beta = 2.71439534152791°, IAS 17 m/s**, on the same nominal 160 / actual 161
interval mesh. Both pass the original full physical residual and fixed-incidence
tangent rank gates. Their complete requests differ only in the initial guess.

This is stronger evidence than a stalled iteration: the computed equilibrium
relation turns back in incidence over the sampled points. It explains why
continuing solely by increasing incidence can be difficult. It does **not**
locate an exact fold, prove stability or uniqueness, establish mesh convergence
of that turn, or identify historical ASWING's branch. The original 5° comparison
remains unresolved and the primary score stays **708/2,200 at 5%**.

![Verified branch and extended-search diagnostic](../../artifacts/isae/ae2-turning-branch-audit-20261110/turning-branch.png)

## Verified physical states

| Calculation | Beta (degrees) | Sensor Earth Y (m) | Heading (degrees) | Sensor flow angle (degrees) | Full residual |
|---|---:|---:|---:|---:|---:|
| Earlier verified starting state | 2.687500000 | 0.197020303 | 15.1095508 | −13.4738098 | 9.000e−15 |
| Ordinary fixed-incidence warm solve | **2.714395342** | **0.199273112** | 15.2769772 | −13.6276879 | 3.224e−13 |
| Prescribed Y = 0.202 m | 2.737030302 | 0.202000000 | 15.4789338 | −13.8210730 | 7.830e−13 |
| Prescribed Y = 0.210 m | **2.714395342** | **0.210000000** | 16.0656332 | −14.4515115 | 9.897e−15 |

The paired states differ in sensor Y by **0.0107268885 m**, many orders of
magnitude above the residual/measurement checks. The saved-only audit compares
the entire requests after removing `initial_state`; model, mesh, operating
conditions, numerical policy and tolerances are identical. The lower-deflection
state comes from the existing warm Newton solver, with the previously checked
centered tangent option, starting at the earlier 2.6875° equilibrium.

For the two deflection-controlled points, beta becomes one extra unknown and
the sensor-Y equation becomes one extra constraint. Every original coupled
equation remains. Two solves of the complete physical matrix eliminate its
unknowns exactly from the additional scalar equation. The complete augmented
linear residual is checked on every Newton step. No stiffness, stall strength,
force law or archived operating point is adjusted.

The 0.202 m and 0.210 m solves take **three and four Newton steps**, respectively,
with full steps accepted throughout. Their numerical solve stages use **4.907
and 6.461 CPU seconds**. These are local diagnostic timings, not browser or
whole-family performance claims. Both states receive freshly assembled physical
and augmented matrices, and both matrices must pass the unchanged rank gate.
Independent restores then apply the original 19 physical checks plus the sensor
target and augmented-rank checks. The ordinary fixed-beta solve passes its
original 19 checks: **61 verification checks pass across the three new states**.

All three points are intermediate diagnostic conditions without paired archived
native rows. They add **zero reference votes**. The authoritative 5° ASWING
point remains Y = 0.191155 m and heading 14.8018°; it cannot be replaced by a
similar output at another incidence.

## Why more backtracking was insufficient

The [previous investigation](isae-ae2-centered-geometry-20261110.md) identified
a one-sided geometry derivative error. This follow-up captures the *later*
centered stall, starting from the verified 2.6875° state and requesting 2.75°.
The capture matches the original failed iteration history exactly and stops
before dense allocation. Its full residual is **1.4866577e−4**; it remains
explicitly unconverged and is never an accepted continuation seed.

A fresh centered matrix at this trial passes independent physical directional
differences. Relative derivative error is **0.0001262% at perturbation 1e−5**
and **0.0025146% at 1e−6**, below the declared 0.01% gate. Assembly takes
1.045 CPU seconds and 74 residual calls. Thus the earlier derivative defect is
not a sufficient explanation for this later stall.

The original search ends at 1/256. Its next physical trial, **1/512**, does
decrease the residual. A separately declared experiment permits up to twenty
halvings and rebuilds the entire centered matrix before each of four further
steps, retaining the original physical-residual Armijo criterion:

| Additional step | Newton direction norm | Accepted fraction | Residual after step |
|---:|---:|---:|---:|
| 1 | 2.2335 | 1/512 | 1.4862745e−4 |
| 2 | 2.9693 | 1/1,024 | 1.4859395e−4 |
| 3 | 5.3939 | 1/4,096 | 1.4858066e−4 |
| 4 | 19.4194 | 1/65,536 | 1.4857956e−4 |

The total residual reduction is only **0.05799%**, versus the unchanged required
residual ≤1e−12. Each fresh direction retains a small independent derivative
error and a small full linear-system defect. More backtracking avoids the
immediate dense fallback but does not demonstrate a practical convergence fix.
These diagnostic iterations are not accepted states or native passes.

## Evidence, limitations and next work

All **14 supervised numerical children** are terminal and reaped: thirteen
successful and one failed. The failure was the first deflection helper applying
Python `abs` to a list-valued attitude, before any Newton matrix was built.
Its source and failure receipt remain intact; the succeeding runner uses
array-safe checks. Every numerical job remained serial with one BLAS thread,
512 MiB address space, 15 CPU seconds and a 25-second supervisor deadline.
Production sources and defaults are unchanged. Browser/build tests remain held.

The next useful branch study is deflection-controlled continuation around the
sampled turn, with a mesh check and a search for roots at the original archived
conditions. Repeated fixed-incidence retries at 2.75° alone are unlikely to
resolve that question. The centered tangent and continuation mechanism still
need focused regression work before production promotion. The remaining original
AE-2 sweeps and unresolved executions also remain required.

Primary accounting is unchanged: **708 passes, 12 computed mismatches, 40
unresolved execution outputs, 1,344 finite unrun values and 96 unavailable
reference values**. The twelve 5° opposite-branch mismatches have median error
249.161%, range 227.303–356.704%. These diagnostics remain separate from the
primary 3,240 physical checks and 87 passing mesh pairs.

The [authoritative reference index](aswing-authoritative-references.md) governs
the setup. Jan Part IV §3.2, pp. 8–12 and Figure 3 distinguish the three laminates,
four incidence sweeps and ASWING 5.96 results. Its negative-coupling/stall
discussion does not establish the historical equilibrium branch. Drela's steady
§3.8 describes exact beam-variable elimination from the coupled Newton system;
the diagnostic retains every equation. Neither source establishes our chosen
sensor-deflection continuation sequence as a historical ASWING default.

[Saved-only audit](../../artifacts/isae/ae2-turning-branch-audit-20261110/assessment.json) ·
[Later derivative check](../../artifacts/isae/ae2-later-centered-20261110/assessment.json) ·
[Extended backtracking](../../artifacts/isae/ae2-extended-search-20261110/assessment.json) ·
[Deflection runner](../../scripts/probe_isae_ae2_deflection_trace.py) ·
[Full bordered equations](../../scripts/probe_isae_ae2_deflection_branch.py) ·
[Fixed-incidence second-root plan](../../artifacts/isae/ae2-double-root-20261110/plan.json) ·
[Audit/plot script](../../scripts/summarize_isae_ae2_turning_branch.py)
