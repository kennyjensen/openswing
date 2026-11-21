# Unchanged influence-cache preparation

Updated 2026-10-15. This is a numerical equivalence and performance study;
ISAE experimental validation remains incomplete.

`TangentInfluences.vortex` now checks for an unchanged cached geometry before
allocating and transforming the complete relative-coordinate arrays. It returns
an independent copy of the stored coefficients. Changed source or receiver
geometry still uses the same complete-array transforms and physical kernels,
including PG, ground images, wake cores and bound-segment exclusions. Retaining
the complete-array arithmetic matters because a differently shaped matrix
product can round differently. This change does not reuse a Jacobian across
different states or alter the convergence threshold.

Only `tangent_influences.py` changes from the released relative-PG kernel.
The [composition](influence-cache-evidence/composition.json) pins all 103 modules.
The [selected report manifest](influence-cache-evidence/manifest.json) identifies
the native, actual Chromium/Pyodide, test and independent-review records.

## Results

Both implementations assemble one full 2,428-by-2,428 Jacobian at the retained
original-mesh FFWT-1 30-degree terminal state, on separate fresh networks.
Within each runtime, the matrices, residuals, input states and hinge chart
centers match byte for byte. No equilibrium solve or state correction is run.
Native residual remains 8.526109111657703e-13; browser residual remains
8.403379002753685e-13. Both satisfy the existing 1e-12 gate. Equality between
native and browser matrices is not asserted.

| Measurement | Released kernel | Cache shortcut |
| --- | ---: | ---: |
| Native full matrix, with cProfile | 28.315 s | 26.840 s |
| Browser full matrix | 55.291 s | 47.740 s |
| Native relative-coordinate transform calls | 9,149 | 7,517 |
| Browser unchanged collocation query, median | 2.586 ms | 0.240 ms |
| Browser unchanged force-point query, median | 2.852 ms | 0.344 ms |

These are observed timings, not a universal speedup. There is one full matrix
sample per implementation in each runtime, with baseline first; profiler,
machine, cache and JIT effects are not isolated. The small browser queries use
three bounded timing batches. Changed-query timings remain about 3–4.5 ms and
some are slightly slower. All timings are retained in the reports. The native
transform helper saves about 0.446 seconds of measured self time; the remaining
wall-time difference cannot be assigned to this patch.

Coordinate preparation was about 9.5% of the native profiled assembly.
Residual evaluation, geometry/rotation work and array contractions remain
substantial. The earlier 516-second browser cold solve belongs to the previous
kernel; this study does not supply a replacement end-to-end solve time.

## Checks and limits

The candidate passes 82 targeted tests: 65 cache/precision checks and 17
frequency-map/time-frame checks. The nine added cache regressions require
unchanged queries to skip coordinate preparation while retaining output
ownership, with ground flags 0, +1 and -1 and both narrow and 184-square shapes.
An independent review compares 330 arrays exactly. Browser controls compare
retained 184-square coefficient arrays and induced velocities, changed
source/receiver/core/mask/global states, ground images and narrow shapes.
The exact production manifest is used in the browser. This is not a fresh
full-repository test suite or a full UI equilibrium run.

The shortcut preserves the existing cache's numeric comparison semantics.
For repeated invalid nonfinite geometry, it can skip a warning or strict NumPy
`errstate` exception formerly emitted by otherwise unused preparation; the
returned values remain the same nonfinite values. Parser and condition checks
reject nonfinite inputs, but the solver does not universally precheck trial
geometry. This boundary and inherited signed-zero/mask-type behavior are
recorded in the [independent review](influence-cache-evidence/review.json).

The [selected experiment archive](influence-cache-evidence.zip) retains the
source snapshots, matrix/profile evidence, browser controls, tests and original
pre-assembly harness failure. Its manifest verifier checks archived bytes;
reproducing a solver calculation additionally requires the stated Python or
browser runtime. This archive does not complete packaging of the larger FFWT
validation study.

ISAE coverage stays **17 partial / 24 pending / 0 fully validated**, and literal
imports stay **177 accepted / 102 rejected**. Matched physical setup, measured
curves, branch/stability checks, mesh refinement and the existing physical
discrepancies remain unresolved.
