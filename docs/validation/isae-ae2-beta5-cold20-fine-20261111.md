# AE-2: fine-grid 5°/20 m/s convergence and factor memory

Observed 2026-11-11 UTC. The primary comparison remains **2,070/2,200 at 5%**.
The original negative-coupling 5°/20 m/s, nominal-160 condition now reaches a
verified **92.1630859375% load**, but does not reach full equilibrium. Its next
attempt fails with `MemoryError` in the full-Newton beam-elimination fallback.
No new native comparison passes are claimed. Production code, equations,
source inputs, defaults and convergence gates are unchanged.

## Original cold continuation

The same-mesh 5°/15 m/s control and four prior checkpoint-hook controls were
reused after checking their sources and saved evidence. The physical control's
entire equilibrium state and sensors match the ordinary cold solve exactly.
No control rerun or intermediate checkpoint adds votes.

An initial accepted-boundary job hit its 15-second CPU limit. Splitting later
jobs at **completed rejected attempts**, as well as accepted load steps,
allowed the unchanged production continuation to advance further. A rejected
attempt saves only the preceding converged coordinates and the production
algorithm's reduced increment. Failed trial coordinates are never used as seeds.

Accepted load fractions are **25%, 37.5%, 46.875%, 60.9375%, 82.03125%,
88.28125%, 90.625%, 91.50390625%, and 92.1630859375%**. The final accepted
checkpoint has physical residual **8.08747e−13**, below the unchanged **1e−12**
gate. Seventeen successful jobs retain **458 Newton iterations** in their saved
logs; this excludes work in the two failed processes and is not a speedup claim.

![Original cold continuation](../../artifacts/isae/ae2-beta5-cold20-fine-20261111/cold-path.png)

The plot includes successful saved boundaries and completed rejected attempts.
The two failed processes have no accepted result and are retained separately.
All nineteen continuation processes were reaped: seventeen exited zero, one
hit the hard CPU limit, and one exited with `MemoryError`. Successful jobs used
at most **12.36 CPU /17.44 wall seconds**. The memory-error process used
**10.66 CPU /14.43 wall seconds**, with **266,008 KiB peak RSS**.

Every numerical child retains **one BLAS thread, 15 CPU seconds, 25 wall seconds
and 512 MiB address space**. Address space includes more than resident memory;
an allocation failure below 512 MiB RSS is consistent with that cap. No larger
limit was used. The chain audit checks **562 source/evidence files**, exact
requests and checkpoint transitions, and retains the original failed receipts.

## Isolating the memory failure

A bounded replay captured the exact matrix immediately before the failing
`NewtonBeamFactor` construction, at Newton iteration **25**, target load
**93.15185546875%**, starting from the 92.1631% checkpoint. The captured trial's
residual is **1.61617e−4**: it is not a converged equilibrium or reference output.
Capture stops before factorization and changes no preceding calculation.

The matrix is **2,105 × 2,105**, with **217,237 nonzeros**, occupying
**2,615,268 bytes** in sparse storage. Two new, isolated processes solved exactly
that matrix and right-hand side:

| Exact linear solve | Peak process RSS | Factor-and-solve CPU | Maximum original-equation residual |
|---|---:|---:|---:|
| Current beam elimination | 173,336 KiB | 0.3813 s | 2.249e−16 |
| Direct sparse LU | 85,848 KiB | 0.06824 s | 7.532e−15 |

Their correction vectors agree to **6.176e−14 relative norm**, with maximum
absolute difference **4.463e−14**. Both preserve every equation and matrix entry.
The current reduction retains roughly **60.0 MB** of additional factor data;
the direct method's LU factors occupy **6.50 MB** (these storage totals cover
different objects; peak process RSS is the comparable overall measurement).

The current beam factor succeeds in a fresh process, so this evidence does
**not** establish that the captured matrix is singular or inherently too large.
It identifies avoidable memory growth in the elimination route as a concrete
candidate for improving the fallback during the larger nonlinear calculation.
The isolated CPU measurements describe this one matrix, not an overall solver
benchmark. All three capture/factor jobs completed under the same limits and
were reaped; their complete source and operator audit passes.

**Next:** test an exact sparse fallback inside the nonlinear continuation, check
unchanged-equation residuals and control parity, then decide whether to adopt
it. No production substitution has been made. Numerical convergence near the
stall transition and the archived opposite-deflection branch discrepancy
remain separate issues; this diagnostic proves neither stability nor uniqueness.

## Primary status and authority

The [latest accepted comparison](isae-ae2-beta5-cold19-fine-20261111.md) remains
**523 accepted states /2,092 computed values**, with **22 mismatches**, **12
unresolved execution outputs** and **96 unavailable reference values** retained
in the denominator. All **9,414 physical checks and 261 mesh pairs** pass. The
eighteen computed 5° failures have median error **267.995%**, range
**227.303–356.743%**; the four 1°/16 m/s failures have median **12.2094%**, range
**8.6983–15.7294%**. This incomplete 20 m/s condition adds no measured mismatch.

The unresolved conditions remain negative coupling at **1°/18 m/s on mesh160**
and **5°/20 m/s on both meshes**. Jan's **Part IV §3.2, pp. 8–12**, the original
models/scripts and the [authoritative reference catalog](aswing-authoritative-references.md)
govern the setup. No stiffness, incidence, stall setting or reference-selected
branch was fitted. Historical startup/executable provenance and two unpaired
input variants remain open. Browser/build checks remain held.

Evidence: [execution summary](../../artifacts/isae/ae2-beta5-cold20-fine-20261111/execution-summary.json),
[checkpoint audit](../../artifacts/isae/ae2-beta5-cold20-fine-20261111/attempts/assessment.json),
[matrix/factor audit](../../artifacts/isae/ae2-beta5-cold20-fine-20261111/factor-memory/assessment.json),
[SVG plot](../../artifacts/isae/ae2-beta5-cold20-fine-20261111/cold-path.svg).
