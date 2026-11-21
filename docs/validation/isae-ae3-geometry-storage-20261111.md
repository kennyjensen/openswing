# AE-3: geometry-buffer lifetime fix adopted

Observed 2026-11-11 UTC. A reference cycle kept temporary dense geometry-column
buffers alive after their last caller finished using them. The solver now
releases those buffers immediately. **Forty geometry/cache regression tests
pass**, and the nominal-160 AE-3 control reproduces every checked state and
load value with **zero difference**. The installed production package matches
the tested candidate; both production lifetime regressions also pass.

The nominal-320 refinement now gets past the previous local-column allocation
failure, but still cannot complete under the existing limits. It fails later
while allocating the final **33.5 MiB** sparse geometry-matrix buffer. That
remaining peak-storage problem is open; no refined solution or native pass
has been added.

## Cause and change

`LocalGeometryMatrix.columns()` previously defined a recursive local decoder.
That function captured the dense `values` array and referred to itself through
a closure cell. When its returned views were discarded, the function/cell
cycle still retained the array until Python's cyclic collector ran. Repeated
geometry batches could therefore accumulate dense buffers independently of
the algorithm's intended per-batch storage limit.

The decoder is now a module-level function with explicit arguments. It returns
the same array views, shapes, ordering and values, without a closure capturing
the buffer. This changes no derivative formula, matrix entry, coefficient,
physical input, rank/residual gate or iteration policy. It does not add forced
garbage collections or depend on changing collection thresholds.

The production change is confined to
[local_geometry_matrix.py](../../openswing/local_geometry_matrix.py).
Two new [regression cases](../../tests/test_local_geometry_matrix.py) disable
automatic cyclic collection, consume several column blocks, discard all returned
views and check the underlying buffer through a weak reference. Both fail on
the original code and pass on the candidate and adopted code.

## Verification

| Check | Result |
|---|---|
| Original buffer-lifetime regressions | Two expected failures retained |
| Candidate buffer-lifetime regressions | Both pass |
| Every local column, spatial rotation representation | Ten cases pass |
| Every local column, absolute rotation representation | Ten cases pass |
| Composed fields, cache ownership/invalidation and storage gates | Eighteen cases pass |
| AE-3 nominal-160 control | Eleven physical checks pass |
| Control state/load/operating parity | Nine checks pass; maximum difference zero |
| Adopted production buffer-lifetime regressions | Both pass |

The geometry regressions cover lifting surfaces, bodies, ground images, joints,
powered wakes, both rotation representations and retained tiny nonzero entries.
The control checks positions, rotations, internal forces/moments, reactions,
circulation, distributed aerodynamic force/moment and operating values. Its
fresh full residual is **2.187e−13**. This supports adopting the storage-lifetime
fix; it does not constitute a new complete ISAE replay or browser benchmark.

## Remaining refinement limit

The original nominal-320 run failed on a **2.01 MiB** allocation in
`LocalGeometryMatrix.columns()`. Releasing the previous Newton matrix/factor
before rebuilding, tested separately in the
[preceding sweep](isae-ae3-roll-sweep-20261111.md), did not resolve that failure
and was not adopted.

With the lifetime fix, all geometry columns are assembled before the next
failure. SciPy's `hstack(columns, format='csc')` then attempts to concatenate
**4,390,870 values** into a **33.5 MiB** data array. The additional allocation
fails under the unchanged **512 MiB address-space cap**. The process exits with
a retained `MemoryError`, using **11.06 CPU /14.81 wall seconds** and
**281,584 KiB peak RSS**. This is neither a timeout nor a computed aerodynamic
disagreement. RSS is not the same as allocated virtual address space.

The refinement was still attempting its first quarter-load stage and returned
no full-load state. No higher resource limit or approximation was substituted.
Next, reduce peak storage when assembling the final sparse matrix—for example,
by releasing completed derivative caches or avoiding simultaneous column/output
copies—while preserving every term and the existing numerical gates.

## Scope and status

The latest complete primary AE-3 replay remains **50/725 at 5%**, with 72
computed values, 22 mismatches and 653 uncomputed targets. That replay precedes
this storage-only source change; only the disclosed finer-grid control was
repeated for parity. The earlier qualified alternative still has rolling errors
of **0.252–1.197%** at the first five speeds and **28.502% /13.009%** near reversal
on nominal 80/160. Its exact historical input and `MM` convention remain open.
No alternative result is merged into the primary count.

All seven candidate-study children and the production-check child are terminal
and reaped. Candidate tests were divided into small serial groups; all children
used one BLAS thread and the unchanged **512 MiB /15 CPU-second /25 wall-second**
limits. The original lifetime failures and all refinement failures are retained.
Browser/build checks remain held, so no browser performance claim is made.

The original kernel is preserved with source hashes before adoption. The
adoption record maps the old changed-module hash to that retained copy;
historical checkpoints are not relabelled with the new kernel identity.

Evidence: [plan](../../artifacts/isae/ae3-geometry-storage-20261111/plan.json),
[assessment](../../artifacts/isae/ae3-geometry-storage-20261111/assessment.json),
[adoption](../../artifacts/isae/ae3-geometry-storage-20261111/adoption.json),
[production verification](../../artifacts/isae/ae3-geometry-storage-20261111/production-verification.json),
[assessment/adoption script](../../scripts/summarize_isae_ae3_geometry_storage.py).
