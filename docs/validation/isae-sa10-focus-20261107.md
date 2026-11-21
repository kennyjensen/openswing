# SA-10: current comparison and faster circulation correction

2026-11-07. Current OpenSwing passes **1,610/2,268 comparisons (71.0%) at 5%**
against the six original archived ASWING configurations. All 324 registered
jobs have outcomes: 269 valid states, one local-flow rejection, and 54 original
attachment-input blockers. There are no solver timeouts in the completed run.
SA-10 is not fully validated.

The displayed increase from 1,256 is entirely the previously authorized
3%→5% allowance change. Rescoring the earlier predictions also gives 1,610.
The solver change below improves runtime, not aerodynamic agreement.

| Original configuration | Passing comparisons at 5% | Remaining issue |
|---|---:|---|
| Straight wing (`wing_alone`) | 358/378 | 18 induced-drag checks; two zero-incidence efficiency checks. |
| Extended wing (`wing_extension`) | 286/378 | 92 failures, mainly induced drag and post-stall loads. |
| Bent tips (`Louvered`) | 277/378 | 101 failures; the lowest passing fraction among executable configurations. |
| Tip sails 60/40/80 | 330/378 | 48 failures, including mesh-sensitive low-angle results. |
| Tip sails 80/60/40 | 359/378 | 12 coefficient/zero-efficiency failures and seven values from one invalid flow state. |
| Tip sails 60/45/30 | 0/378 | All 54 states retain the original opposite-beam attachment conflict. |
| **Total** | **1,610/2,268** | **273 computed mismatches and 385 unavailable values.** |

All seven output channels, both registered meshes, duplicate incidence rows,
source signs and unavailable values remain in the original denominator.
The supplied F toggles retain evolving influences; stall strength remains 40,
width 0.05, and the original core and local-Mach rules remain active. No
alternative model or strength-20 result is mixed into this count.

## Remaining numerical differences

Across failed, finite, nonzero-reference comparisons on both meshes:

| Quantity | Median relative error | Maximum |
|---|---:|---:|
| CL | 5.32% | 8.19% |
| CD | 7.23% | 53.97% |
| Induced CD | 6.53% | 9.37% |
| CM | 5.33% | 10.40% |
| Span efficiency | 7.09% | 16.24% |

Zero-reference comparisons retain their original absolute gates and have no
meaningful percentage error. Induced drag accounts for 108 of the 273 computed
failures. Drag and CD account for another 102; these are dimensional and
nondimensional versions of the same quantity, not independent physics.

For Louvered, failed CD errors have median 7.47% and maximum 10.11%; failed
induced-drag errors have median 7.41% and maximum 9.37%. This is the next
executable discrepancy to investigate using the documented endpoint geometry
and force quadrature, alongside the broader stall-related induced-drag
differences. Earlier source audits and rejected parameter/mesh alternatives
remain linked in the [geometry audit](isae-sa10-geometry-parameter-20261101.md).

The 80/60/40 configuration at 25° on the fine mesh still reaches local normal
Mach **1.086709**, despite a circulation residual of **1.24e-14**. Its leading
contribution comes from a trailing ray only 6.95 micrometres from the receiver.
It remains invalid under the subsonic equations; convergence does not permit
accepting its forces. The original attachment conflict likewise remains open.

## Runtime change and accuracy checks

Profiling the fine 60/40/80 case at 12° reproduced its 60-second timeout and
identified expensive MINPACK corrector factorizations. The continuation path
now first uses a bounded, damped Newton corrector with an analytic Jacobian
and dense LU solves. An unresolved correction falls back to the original
hybrid method from the original prediction. Arclength acceptance, branch
neighborhood checks, the exact physical endpoint solve and all physical
validity gates are unchanged. No approximation to the aerodynamic equations
or reduced circulation basis is introduced.

The previously timed-out case completes in **22.9 seconds** in the fresh run
and passes all seven outputs. A separate comparison in one interpreter on the
64-interval case takes **7.11 seconds before / 2.92 seconds after (2.44×)**.
Circulation differs by at most 3.33e-16 relative; the largest scaled coefficient
difference is 1.56e-15. These are measured timings on this host, not universal
performance guarantees.

The complete valid scope agrees with the saved physical predictions within
**2.93e-14**, scaled by the larger of one and the saved magnitude. Maximum
circulation residual is **8.49e-13**. All 5,226 successful continuation
correctors in these valid states use Newton; no hybrid fallback is needed.
Ninety focused tests pass, including independent roots, folds, multiple-root
branch selection, forced fallback, stalled wings, polishing and seeded solves.
The actual Pyodide/WebAssembly corrector also passes the two-fold endpoint
and 16 independent stall-corner checks, with maximum endpoint error 2.23e-16.
This verifies the changed corrector in WebAssembly; it is not a complete
SA-10 sweep through the browser interface.

Five first attempts exhausted the 768 MiB cap during repeated large-array
allocations. They are preserved. Explicit cyclic collection between independent
solves prevents further allocation failures; all five were also rerun once in
isolated foreground processes under the same cap, using a predeclared selection
regardless of reference agreement. The selected scope contains 270 physical
requests plus those five resource reruns. No background jobs or concurrent
solvers are used.

## Reproduction and evidence

The unchanged registered adapter supplies all jobs. The new script records
source hashes and verifies them before and after each batch; batches contain
at most 12 serial solves and stop starting new solves after 35 seconds. Each
individual solve retains a 60-second limit. Completed outputs are never
overwritten. The independent scalar audit checks all 2,268 target identities
and decisions using exact rational arithmetic for the relative allowance.

- [Frozen current plan](../../artifacts/isae/sa10-newton-20261107/plan.json)
- [Complete independently checked comparison](../../artifacts/isae/sa10-newton-20261107/analysis.json)
- [Same-process performance and circulation comparison](../../artifacts/isae/sa10-newton-20261107/benchmark.json)
- [WebAssembly corrector checks](../../artifacts/isae/sa10-newton-20261107/wasm-smoke.json)
- [Original timeout and profile](../../artifacts/isae/sa10-focus-20261107/profile.txt)
- [Explicit resource-rerun selection](../../artifacts/isae/sa10-newton-20261107/memory-retry-plan.json)

Native startup settings and the exact producing executable remain unavailable.
The comparison targets the archived ASWING outputs, not experimental agreement.
