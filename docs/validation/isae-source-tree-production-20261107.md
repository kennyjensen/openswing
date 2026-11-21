# Source-beam tree startup certificate

Startup now implements the [verified source-beam nullspace argument](source-flexible-tree-rank-20261107.md)
for grounded forests with finite compliance. The new path avoids a dense
mechanical SVD when its exact scope applies. It retains the actual Newton
matrix, independent circulation rank check, and all physical residual and
finite-rotation acceptance checks. The implementation passes **181 focused
and regression tests** and **29 built-browser checks**. The two measured
211-node Python startup jobs are 1.90–2.25 times faster than retained previous
OpenSwing runs, with bit-for-bit identical saved state vectors.

## What changed

`openswing/source_initial_rank.py` checks the exact source operator, zero load
and mechanical state, stationary frame, identity section frames, zero jig
curvature, finite compliance, positive material lengths, forest topology and
one full Ground per connected component. Full rigid joints and supported
finite compliant hinges are included. Hinge scope retains coincident origins,
isolated parent endpoint, zero cold intercept and positive finite effective
stiffness. It does not substitute free or rigid joints for weak springs.

Conservative force/moment balance first removes all internal and reaction
wrench increments. Finite source compliance then yields zero strain/curvature
increments, and compatibility plus Ground removes all pose increments. This
establishes algebraic full rank, **not a numerical condition bound**. The
reported method is `source flexible-tree rank certificate`, and its physical
certificate explicitly records `numerical_condition_bound=false`.

`structured_static.check_initial_rank` uses this result only when the actual
force/circulation block is exactly zero and the circulation block passes its
column-scaled **1e-10** singular-value gate. Unsupported cases keep the prior
numerical fallback and thresholds. A nonzero unloaded rest defect is still a
residual to solve; it is not accepted as equilibrium. No loaded-stability
claim follows from this cold-start argument.

The previous 139-module kernel remains archived. The new 140-module snapshot
adds only `source_initial_rank.py` and changes only `check_initial_rank` in
`structured_static.py`. An AST comparison verifies that every other function
in that module is unchanged; the other 138 original modules are byte-identical.
Force, constitutive, compatibility, Newton and time-response equations stay
unchanged. Old checkpoints continue to require their original kernel identity.

## Verification

- **44 new production tests pass**, covering all five supported source
  operators, independent physical first variations, actual body/surface charts,
  retained matrices, scoped bypass of dense rank work, valid numerical fallback,
  unsupported states, singular/redundant constraints and separate circulation
  failure controls.
- **83 independent-oracle and existing rigid-tree tests pass**.
- **35 continuation checks pass** in smaller serial groups: 30 context,
  rejection and JSON-boundary checks, two JavaScript checkpoint roundtrips,
  and three bitwise uninterrupted/restarted-state comparisons.
- **19 numerical-rank regression checks pass**, including the 211-node saved
  mechanical matrix, explicitly released hinges and unchanged 1e-10 cutoffs.

These groups contain **181 passing tests** in total. Literal 211/419-node
startup measurements and built-browser verification are recorded separately.

## Literal 211-node comparison

Two new one-step jobs use exactly the same source, mesh, conditions and
tolerances as the retained frozen-matrix Flare20 jobs. The only kernel change
is the startup rank selection described above. Both saved state vectors,
hinge-chart values and reached load fractions are **bit-for-bit identical**.

| Accepted boundary | Original process | New process | Observed ratio | Rebuilt residual |
| --- | ---: | ---: | ---: | ---: |
| First load step | 42.63 s | 22.40 s | 1.90x | 2.85e-15 |
| Second load step | 52.75 s | 23.47 s | 2.25x | 2.59e-15 |

These are separate retained serial process measurements on this environment,
including interpreter startup and boundary reconstruction. They are not a
controlled simultaneous timing study, browser timing or complete-solve timing.
Both new processes exit successfully within their 90-second cap, with one
BLAS thread and a 512 MiB virtual-address limit. The selected rank report
retains the literal approximately 1e-6 N m/rad effective hinge stiffness and
records a circulation singular ratio of 0.0062771 against 1e-10.

The **419-node case also saves its first accepted load step**, at load fraction
3.67782e-6, with rebuilt residual **3.82e-14**. Its process exits successfully
in **27.54 seconds** under the same limits. It has 5,028 mechanical unknowns
and 5,444 total unknowns; no dense mechanical SVD is used. This is a partial
continuation boundary, not the full 419-node equilibrium or a mesh-convergence
result. Independent assessments restore and verify all three saved boundaries,
including source/kernel identities, checkpoint joins, and physical residuals.

## Built browser

All **29 checks pass** in the actual built Chromium page and Pyodide worker.
Two 211-node steps take **12.321 s and 12.718 s** after the worker is ready.
A complete page/worker reload separates them. Their largest normalized state
difference from the current Python kernel is **4.421e-16**, and saved-load
residuals are at most **4.607e-15**. These timings exclude initial page/runtime
loading and do not represent a complete equilibrium solve.

The browser rejects released Ground rotations, redundant Ground reactions,
changed checkpoint checksums and changed flight conditions. It verifies the
separate circulation gate, explicit algebraic certificate, both original
point-mass pylons, 16-degree sideslip and unchanged kernel identity. All 140
shipped kernel module hashes match the Python sources. There are no page
errors or external requests during the check.

The first scope-test invocation failed because its released-joint fixture
retained a forbidden Jangle record. Correcting that fixture required no solver
change. A combined continuation/rank invocation reached its 90-second process
cap before producing a final report. Its two Node subprocess failures are
retained. An isolated reproduction captures V8's subspace-allocation failure
under the inherited 512 MiB virtual-address cap; both JavaScript checkpoint
tests pass without that cap, retaining Node's 32 MiB heap setting. No complete
pass total is inferred from the truncated combined log. Numerical jobs retain
their original memory and time limits and are run in smaller serial groups.

## Evidence and scope

`artifacts/isae/source-tree-production-20261107/study-plan.json` pins the old
and new kernels, source-preserving continuation helper, identical 211-node
request settings, the next 419-node mesh, and the comparison gates before
the literal runs. The immutable new kernel is
`.reference/solver-snapshots/source-tree-20261107/`.

This work adds no archived ASWING targets or gust histories. FFWT-4 native
coverage remains **200/8,000** at 5%. The completed frozen 211-node equilibrium
has **0.5344% initial native moment error**, but only **1/7** 107/211-node mesh
checks passes 0.1%. Historical K/F and attachment semantics, further spatial
and field accuracy, complete PM2 gust histories and shared suite registration
remain open.

The next numerical step is to continue the saved 419-node boundary to full
load and repeat the seven unchanged 0.1% mesh gates against 211 nodes. The
startup optimization makes that refinement feasible; it does not establish
its result in advance. The timestamped progress dashboard correctly retains
the same native-comparison fractions.
