# AE-2: verified positive branch through 2.5°

The negative-coupling wing at IAS 17 m/s now has independently verified
positive-branch states at **1°, 2°, 2.25° and 2.5°**, all on nominal 160 / actual
161 intervals. All **78 physical/control checks** pass; the maximum full residual
is **6.040e−13**. The 1° control reproduces the original accepted output.
The continuation has not reached 5° and does not yet resolve the native mismatch.

The primary score remains **708/2,200 at 5%**. The 1° state was already counted;
there are no archived 2°, 2.25° or 2.5° reference rows in this comparison.
These diagnostics add **zero native votes**, and all original missing, unrun
and failed comparisons remain required. Production sources/defaults are unchanged.

| Commanded beta | Sensor Earth Y (m) | Heading (degrees) | Sensor speed (m/s) | Sensor flow angle (degrees) | Full residual |
|---|---:|---:|---:|---:|---:|
| 1° control | +0.101170432 | +7.83928684 | 16.9982798 | −7.28590647 | 2.053e−13 |
| 2° | +0.163242777 | +12.5695609 | 16.9942544 | −11.3751429 | 6.040e−13 |
| 2.25° | +0.174938142 | +13.4527372 | 16.9930549 | −12.0929363 | 4.560e−15 |
| 2.5° | +0.186472992 | +14.3207523 | 16.9918029 | −12.7982527 | 4.214e−14 |
| Archived ASWING at **5°** | +0.191155 | +14.8018 | 16.9703 | −11.6441 | Not available |

The 2.5° deflection and heading are near the archived 5° values, but these are
different commanded conditions. That observation is not a reference pass or a
reason to substitute an incidence. The original OpenSwing cold start at 5°
remains on its opposite branch, with Y = −0.248455748 m and heading −18.8430885°.

![Verified branch, native points and original cold result](../../artifacts/isae/ae2-incidence-staged-audit-20261110/incidence.png)

## What changed in execution

The [previous investigation](isae-ae2-incidence-trace-20261110.md) established
agreement between two complete tangent assemblies and approximately six times
less assembly CPU for the existing moving-geometry decomposition at one state.
It also retained failures from combining convergence, final tangent assembly
and rank checking in one bounded process.

The new runner separates three stages:

1. Production warm Newton and line search, using that checked complete assembly
   for iteration matrices, stop at a **pending** converged-state checkpoint.
2. A separate process builds every column of the **original final stencil
   tangent** at the exact stored normalized state.
3. A separate process applies the unchanged full-matrix rank gate, recovers the
   output, then independently restores the state for the original physical checks.

Pending states cannot seed subsequent steps. Every preceding phase must have a
successful, reaped process receipt with source and artifact hashes bound to the
plan. Eight focused receipt tests pass, including rejection of failed, timed-out,
unreaped, unverified, altered and missing evidence. The saved-only full trace
audit verifies the case inputs, accepted states, source hashes and original
native/cold references without another solve.

Single-thread numerical libraries load in the parent before a supervised fork.
No model or residual is evaluated during that preload. Each numerical child
still has **one BLAS thread, 512 MiB address space, 15 CPU seconds and a 25-second
supervisor deadline**. All work is serial. Import/hash time is separate from
the reported numerical-child times, so these timings are not browser benchmarks.

The 2° Newton stage takes **2.402 CPU seconds / 2.662 elapsed seconds**, with ten
iterations and two tangent builds. All successful numerical stages use less
than 7.3 CPU seconds. The new runs have **14 terminal, reaped children: twelve
normal completions and two failures**. No background solver remains running.

## What remains unresolved

The direct 2°→3° step reduces its full residual from 0.01744 to about 0.01401,
then the line search stalls. Its dense fallback cannot allocate a 33.8 MiB
matrix within the address-space cap. After two successful quarter-degree steps,
2.5°→2.75° reaches a much smaller residual, **1.159e−4**, but also stalls and
fails in the dense fallback allocation. Both receipts and traces are retained;
neither produces an accepted candidate. The refined 3° and original 4°/5° steps
remain unstarted.

This narrows the difficult interval; it does **not** establish a physical fold,
branch termination, stability or the historical ASWING iteration sequence.
At the accepted 2.5° state, the largest absolute reported section CL is 0.86038,
and none of the 161 strips exceeds the declared ±1.1 limits. The smooth stall
leakage law still acts below those limits, so this is not proof of either a
stall cause or its absence. [Saved section data](../../artifacts/isae/ae2-incidence-staged-audit-20261110/section-state.json).

Next: capture the stalled 2.75° trial before its dense fallback allocation and
compare the complete iteration direction against the original full stencil
there. Agreement at the earlier 2° seed does not establish agreement at this
more difficult trial. That comparison will distinguish tangent error from
nonlinear line-search/branch behavior before more continuation attempts.
Remaining original AE-2 sweeps and unresolved executions still need completion.
Browser/build tests remain held.

The setup remains governed by the [authoritative index](aswing-authoritative-references.md)
and checksummed Jan Part IV §3.2, pp. 8–12, Figure 3, together with the original
scripts and outputs. Geometry, stiffness, airfoil law, sensor, atmospheric and
frozen-influence settings are unchanged. No comparison with experiment is
substituted for the documented native ASWING target.

[Assessment](../../artifacts/isae/ae2-incidence-staged-audit-20261110/assessment.json) ·
[Initial staged plan](../../artifacts/isae/ae2-incidence-staged-20261110/plan.json) ·
[Refined plan](../../artifacts/isae/ae2-incidence-refined-20261110/plan.json) ·
[Runner](../../scripts/probe_isae_ae2_incidence_stages.py) ·
[Receipt tests](../../tests/test_isae_ae2_incidence_stages.py) ·
[Audit/plot script](../../scripts/summarize_isae_ae2_incidence_trace.py)
