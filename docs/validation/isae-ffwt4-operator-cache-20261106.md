# Exact aerodynamic operator reuse — 2026-11-06

Unchanged aerodynamic queries now reuse their complete immutable vortex
operator within one tangent. The previous cache reused coefficient arrays
but rebuilt endpoint groups, incidence arrays and core columns. This removes
640 of 1,797 operator constructions (35.6%) in a four-step FFWT-4 continuation.
The complete output is identical to the saved pre-change result. Whole-solver
timings remain inconclusive; this is not evidence of a reliable browser or
full-history speedup.

The implementation is in `openswing/tangent_influences.py`. Keys include
coordinates, source order, direction, PG transform, effective core inputs,
bound exclusions, and active ground-image inputs. Shape, dtype, signed zero
and strides are retained. Changed geometry rebuilds its own endpoint groups
and still evaluates every changed vortex pair. Only the first state for each
query is retained, within the existing shared 64 MiB tangent budget. Storage
accounting conservatively includes coefficients also held by the pair cache.
No aerodynamic equation, Newton acceptance tolerance or physical input changes.

An additional check found that equal-valued arrays with different layouts can
produce different last bits in BLAS operations. The pair cache in
`openswing/factored_influence.py` now also invalidates on relevant layout
changes. A non-diagonal PG transform exposed differences around 1e-16 in the
old behavior. The new tests require exact agreement with fresh evaluation
for Fortran, strided and negative-stride inputs, including ground images.

## Saved-response comparison

`scripts/benchmark-isae-ffwt4-influence-cache-v2.py` authenticates the retained
request, complete reference output, source inputs, and all 138 kernel files.
Its baseline loads the archived versions of both changed modules before any
solver imports. All other production modules must match the archive exactly.
The pre-change kernel is preserved with a hash manifest in
`.reference/solver-snapshots/ffwt4-before-operator-cache-20261106/`.

The continuation uses the existing quarter-step checkpoint at step 400 and
runs through step 404: t=1.4900 to 1.5049 s, dt=0.003725 s. Every run accepts
four steps, rejects none, builds one Newton matrix and takes four Newton
iterations. Maximum residual is 2.5791782217484817e-9, below the unchanged
1e-8 acceptance gate. All fields, including all five snapshots and restart
records, match the old result exactly after JSON whitespace/key-order
normalization. No output fields or small values are excluded.

| Final run, in execution order | Dispatch seconds | Operators built | Tangent queries |
|---|---:|---:|---:|
| Current 1 | 10.611 | 1,157 | 896 |
| Archived baseline 1 | 11.184 | 1,797 | 896 |
| Archived baseline 2 | 11.054 | 1,797 | 896 |
| Current 2 | 12.335 | 1,157 | 896 |

Imports and evidence serialization are outside the timed region; checkpoint
restoration and validation are inside. These are small serial CPython jobs
on this host, with one BLAS thread and unchanged physical settings. The
variation exceeds the apparent timing improvement in the first pair. Do not
interpret the reduction in construction count as a 35.6% solve-time reduction.

Evidence is under `artifacts/isae/ffwt4-operator-cache-20261106/`:
`final-current-{1,2}` and `final-baseline-{1,2}` contain plans and reports.
The original prototype, its benchmark helper and its measurements are retained;
the v2 helper and `final-*` runs identify the final implementation.

## Validation scope

All 126 selected CPython checks pass: 67 coefficient checks, 54 tangent
checks and five frequency-map checks. These cover independent vortex controls,
input changes, memory layouts, ownership, cache exhaustion, shared endpoint
cancellation, complete coupled Jacobians and elastic-motion tangents. They
ran in small serial batches; the final coupled cases ran two at a time.
The same 67 coefficient cases and three independent physical-field controls
also pass in the local Pyodide WebAssembly runtime. XML and WASM JSON reports
are retained in the evidence folder.

The earlier failed layout assertions and capped test attempts are retained;
the layout failures are resolved without relaxing tolerances. All final
selected batches finish with exit 0.

This work adds no native ISAE target. FFWT-4 remains **200/1,600** across the
eight fixed histories, based on the pinned full-history study. Its adjacent
time-refinement gate remains **1/2**: the gust increment changes 0.113%, above
0.1%. The full history has not been rerun with this optimization. Further
time/mesh accuracy, the other 1,400 fixed-history values, hinged models and
shared registration remain open. Historical helpers deliberately retain their
old kernel pins; a new continuation must explicitly attribute its new kernel
instead of rewriting the previous evidence.
