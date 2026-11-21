# Wall-root custom trim and the remaining AE-2 branch

Updated 2026-11-05. Ordinary custom sensor constraints now work at a declared
steady solid-wall root. All **47 distinct Python regressions** and an actual
offline browser workflow pass. This fixes a derivative failure; it does not
validate the unresolved AE-2 point at 17 m/s. The native baseline remains
**2/2,200**, with no new native comparison cells added by this study.

## Correction and verification

A small clamped lifting wing reproduced the problem: custom trim attempted to
differentiate by moving the root through the ground image plane. Reducing the
target-continuation step could not fix that invalid derivative probe. The
retained pre-fix test fails with the ground-intersection error.

Custom Newton corrections now use the network's existing boundary-aware full
Jacobian. The final centered tangent and one-sided smoothness stencils run in
the same bounded wall-root derivative context. The accepted state is evaluated
outside that context. Full residual, rank, smoothness and physical-clearance
gates remain unchanged; no equation, material property or native tolerance was
adjusted. Ordinary trials that cross the wall are still rejected.

Four new tests cover both the historical and source-coupled structural operators,
with updated and frozen influences. Each compares a sensor-constrained solve
from an 8 m/s saved equilibrium against a separate ordinary 10 m/s solution.
Positions, rotations, internal forces/moments, reactions and circulation agree;
force/moment balance, unchanged seeds, final rank and real-crossing rejection
also pass. The other 43 tests cover source custom trim, general custom equations,
allocation/controller interactions, derivatives, frequency response and time
launch. Three larger batches reached their time caps; completed tests were
retained and only unfinished tests rerun. The aggregate identifies all 47
distinct passing tests and preserves the incomplete batch logs.

The public Python API recovers **9.99999999999664 m/s**, with full residual
**1.886e-14**. The offline workbench imports the same project and seed, solves
the sensor constraint and exports the result. All **11 gates and 1,695 numerical
comparisons** pass; the browser solve takes **9.56 s** after **28.42 s** startup
and project import. Execution counters and the cancellation-sensitive smoothness
ratio are excluded from physical parity; the original smoothness/rank limits
are checked independently.

Three pre-solve browser-harness failures remain recorded: an omitted `.mjs`
MIME type, inherited flap-control metadata, and inherited trim presets. The
latter two were correctly rejected during project loading. Only the test server
and project fixture metadata changed; no native request, physical result or
accuracy gate was changed to obtain the passing browser run.

The change covers ordinary custom trim. Wall-root weighted-allocation and
feedback workflows are not covered by this verification. Existing restrictions
on unsteady, moving and powered wall-root flow remain in force.

## AE-2 follow-up, with all unsuccessful outcomes retained

The earlier [18–20 m/s positive-branch comparison](isae-ae2-continuation-20261105.md)
is unchanged. The next diagnostic used quarter-speed steps from the accepted
18 m/s states, with the original model and physical gates:

| Diagnostic | Outcome |
|---|---|
| Nominal-80, 17.75 m/s from 18 m/s | Newton line-search failure at residual 0.00519. |
| Nominal-160, 17.75 m/s from 18 m/s | Memory failure allocating a 33.8 MiB matrix under the 512 MiB process cap; no physical conclusion. |
| Remaining six quarter-speed states | Not run because their preceding state was unavailable. No 17 m/s comparison was produced. |
| Nominal-20 and nominal-40 full-load cold starts at 20 m/s | Both computed and passed their physical checks. These are exploratory meshes. |
| Nominal-20, sensor RY fixed at 0.24 m, speed solved | Computed: speed **17.9234333 m/s**, Psi **18.4221392°**, residual **3.538e-14**; 15/15 physical checks pass. |
| Nominal-40, the same sensor target | Explicitly stopped and reaped without an accepted result. No mesh-validation credit. |

Using a sensor coordinate is a different parameterization of the same coupled
equations, with speed solved as an operating unknown. ASWING's v5.86 version
notes describe user-defined GCON constraints targeting sensor quantities. Here
the target is an openly declared diagnostic coordinate, not a fitted material
parameter or an invented native reference.

The coarse sensor point alone does **not** locate a turning point, exclude other
equilibria, establish stability, or explain the archived 17 m/s output. It has
no native comparison target and remains unrefined. Its reported solve duration
is 103.64 s, so custom continuation is still too expensive for a broad sweep.
Observed wall time and the subprocess monotonic timer differed substantially;
the final explicit stop records 313.99 s wall age while its supervisor records
48.12 s. The cause of that timing discrepancy is not established. These records
must not be interpreted as a successful fixed wall-time bound or a solver speedup.

Next useful work is to profile the complete custom tangent/smoothness evaluation
using the retained state, improve its cost without changing the equations, and
complete a refined branch trace. This unresolved point should remain separate
from expansion to the missing AE-4/AE-5 comparisons. Historical settings and
full ASWING validation remain open.

## Evidence

- [Results, checks, source hashes and failure records](wall-root-custom-trim-20261105.json)
- [All 47 distinct regression results](../../artifacts/isae/wall-custom-trim-20261105/test-summary.json)
- [Original failure](../../artifacts/isae/wall-custom-trim-20261105/before-tests.log)
- [Passing browser run](../../artifacts/isae/wall-custom-trim-20261105/browser-r3/report.json)
- [Quarter-speed outcomes](../../artifacts/isae/ae2-speed-refinement-20261105/serial.log)
- [Sensor-coordinate outcomes](../../artifacts/isae/ae2-sensor-continuation-20261105/serial.log)
- [Explicit final stop](../../artifacts/isae/ae2-sensor-continuation-20261105/cases/m40-y024/external-wall-limit.json)
- [Delivery and verification records](../../artifacts/isae/wall-custom-trim-20261105/)
