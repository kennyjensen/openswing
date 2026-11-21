# AE-2: memory recovery adopted; handoff to AE-3

Observed 2026-11-11 UTC. The full-Newton path now recovers from a beam-factor
allocation failure by solving the same matrix with exact sparse LU. The usual
beam factor and Drela-style lagged matrix remain the normal routes. The change
does not catch numerical failures, alter an equation, change a physical input,
or relax a residual, rank, line-search or continuation gate.

The recovery scales rows and columns, retains every original matrix entry,
performs iterative refinement and checks the correction against the original
full equations. The failed constructor's exception handler ends before the
replacement is allocated, releasing its traceback's temporary matrices.

## Evidence

| Check | Result |
|---|---|
| Sparse-factor and production recovery tests | **7/7 pass** |
| Existing full-Newton beam regression tests | **9/9 pass** |
| Forced-recovery AE-2 5°/19 m/s fine-grid control | **20/20 physical/parity checks pass** |
| Control maximum normalized coordinate difference | **6.661e−16** |
| Control fresh full residual | **8.61155e−13** |
| Real allocation failure at the next 20 m/s load target | Recovered; child exits zero under unchanged limits |

The actual failure occurred while targeting **93.15185546875% load** from the
previously verified **92.1630859375%** checkpoint. Sparse recovery let the
original algorithm finish that attempt and reject it normally at residual
**1.61617e−4**. It retained the converged coordinates and selected its original
half-size increment. The next target, **92.657470703125%**, failed at residual
**1.05555e−4**. Halving again would cross the existing **1/256** minimum increment,
so the original nonlinear solver stopped. That process had no memory error.

Thus the allocation failure has a tested recovery, but full-load convergence
has not been solved. No failed trial is accepted, no alternative branch is
chosen from reference values, and no native comparison pass is added.

The actual recovery child used **11.37 CPU /16.46 wall seconds**, at
**279,960 KiB peak RSS**. The smaller unsuccessful retry used **6.86 CPU /11.43
wall seconds**. All three diagnostic workers were reaped; every child retained
one BLAS thread and **512 MiB address space /15 CPU seconds /25 wall seconds**.
The earlier isolated factor memory measurements are not an end-to-end speedup.

An initial control was correctly rejected before solving because placing the
inactive prototype inside the kernel changed the checkpoint fingerprint. That
failed attempt and its source copies remain retained. The prototype was moved
outside the kernel, restoring the exact original fingerprint for the diagnostic.
Production adoption subsequently changes the fingerprint intentionally; old
continuation packets are not relabelled or silently accepted by the new kernel.

## Scope of adoption and remaining work

Only the full-Newton factory call in `structured_static.py` changes, and the
new `sparse_newton.py` is byte-identical to the tested candidate. The adoption
audit checks that every other production module is unchanged. Original source
copies are retained so the earlier evidence remains tied to its actual revision.

AE-2's last fully audited native tally is **2,070/2,200 at 5%**, with **22
computed mismatches, 12 unresolved outputs and 96 unavailable reference values**.
That complete sweep precedes this recovery-only source change; it has not been
repeated after adoption. The 5° branch failures have median **267.995%** error
(**227.303–356.743%**); the four 1°/16 m/s failures have median **12.2094%**
(**8.6983–15.7294%**). The family remains open. Browser/build checks remain held.

At the user's request, the active focus moves to **AE-3** after this improvement.
Its first step is a current-code replay and setup audit of the six native
finite-aileron coefficient states on both existing meshes. Jan **Part IV §3.3,
pp. 10–13** separates original ASWING 5.96's fixed polar values from the
Reynolds-dependent ASWING-m modification; those targets must remain distinct.
AE-3's historical **50/725 printed-precision matches** are not a new-code or
5%-tolerance result. Derivative, mass/inertia, free-roll, reversal and unpaired
input scopes remain required and open.

Evidence: [diagnostic audit](../../artifacts/isae/ae2-sparse-fallback-r2-20261111/assessment.json),
[production adoption](../../artifacts/isae/ae2-sparse-fallback-r2-20261111/adoption.json),
[production tests](../../artifacts/isae/ae2-sparse-fallback-r2-20261111/production-tests.xml),
[beam regressions](../../artifacts/isae/ae2-sparse-fallback-r2-20261111/beam-regression.xml),
[prior matrix comparison](isae-ae2-beta5-cold20-fine-20261111.md).
