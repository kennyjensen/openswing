# Checked steady-continuation jobs

The solver now supports small serial jobs that retain accepted load states.
This addresses the loss of Flare20 progress when an entire cold solve exceeds
a process limit. It does not change the physical equations or make the whole
equilibrium instantaneous. Native coverage remains **200/8,000 at 5%**.

Follow-up, 2026-11-08: [workbench progress controls](steady-progress-workbench-20261108.md)
now expose this API through one-step advance and portable save/load with case
restoration. The historical API and built-browser evidence below remain intact.

## Contract

The optional JSON `continuation` object supplies `max_load_steps` and, on
restart, a checkpoint. Only accepted load levels consume that job budget.
The packet contains exact normalized coordinates with explicit layout/scales,
unwrapped hinge charts, current load factor, next increment, accepted count,
and cumulative rejected-attempt count. It also binds source/mesh/operator,
all flight/motion/load settings, solver controls and the kernel source hash.
Its checksum detects corruption; it is not an authentication mechanism.
Numeric hashing uses float64 values, so JavaScript's rewriting of `1.0` to
`1` and `-0.0` to `0` does not invalidate a checkpoint. Boolean and string
values remain distinct; nonfinite and inexactly representable integers are
rejected. The physical state is still saved without numeric rounding.

Resume verifies the saved state's complete physical residual at its saved
load against min(requested tolerance, 1e-12), and repeats the unloaded rank
gate. The original nonlinear equations, merit search, per-Newton 5° rotation
guard, chart rollback, adaptive load increments and 128-rejection budget remain.
No matrix is reused across job boundaries; the uninterrupted algorithm already
starts each load level with a fresh matrix. No output reference is used to
choose a state, branch, increment or physical parameter.

A pending result has `converged: false`, a separate
`openswing-static-continuation` packet, and no `equilibrium_state` suitable for
time launch. Only the completed full-load result exports a normal equilibrium.
This opt-in API supports the structured mounted/structural route; warm guesses,
controllers, derivative requests and other operating equations retain their
ordinary routes and are rejected in a bounded job. The regular workbench
still requests a complete solve. An accepted-step budget is not a wall-clock
guarantee; the native jobs also have external process/memory limits.

## Verification

All **40 focused checks pass** in
`artifacts/isae/ffwt4-continuation-20261106/tests-numeric-final.xml` (38)
and `tests-transport-final.xml` (2).
Three synthetic mechanical, source moving-airflow and midpoint cases produce
bit-for-bit identical final coordinates and hinge charts with serial JSON
restarts and uninterrupted solves. Tests cover changed setup and solver
controls, altered source/kernel identities, nonfinite/corrupt data, physically
inconsistent states, rejection-budget preservation, invalid job budgets and
unfinished versus completed API output. The existing unloaded-rank tests also
pass. Earlier failing harness runs are retained: an incorrect policy identifier
and an assertion expecting rejection at a later API layer were corrected.
The actual Node JSON round trip exposed a checksum portability defect; the
numeric canonicalization above fixes it. An initial combined run passed 38
checks but failed both Node processes under the inherited 512 MiB virtual
address-space cap. The final numerical suite retains that cap; the two small
Node transport checks run separately with a 32 MiB JavaScript heap limit.

The exact 139-module kernel is archived under
`.reference/solver-snapshots/ffwt4-continuation-20261106/`. The native jobs load
that archive explicitly, so later development cannot silently change their
equations. Their literal source, driver, request, predecessor, helper and
kernel hashes are recorded before computation. Each output directory is new;
prior checkpoints and failed attempts are not overwritten.
The portable serializer is separately archived in
`.reference/solver-snapshots/ffwt4-continuation-json-20261106/`. Only canonical
JSON hashing differs from the native study kernel. Old checkpoint hashes and
source identities remain unchanged; they are audited with their original
kernel. A kernel change intentionally invalidates an unfinished checkpoint.

The actual built Chromium worker passes **32 checks** (`browser/report.json`).
The synthetic source moving-airflow case completes in four one-load-step jobs,
including a complete page/worker reload after the first checkpoint. Final
positions, rotations, internal forces/moments, reactions, circulation and hinge
charts exactly match the uninterrupted browser solve. Altered checksums and
flight settings are rejected, as is use of a partial checkpoint for time launch.
The literal Flare20 browser preflight saves its first accepted load step with
both qualified pylons, beta 16° and a physical residual below 1e-12. This does
not claim a complete Flare20 solve in the browser. All 139 shipped module hashes
match the tested source, with no page errors or external network requests.

`scripts/verify-isae-steady-continuation.py` checks the test evidence, both
archived kernels, the source/local downloads and a fresh full-load physical
residual using the current kernel. Its retained report is `verification.json`.
The regular workbench still has no equilibrium-checkpoint resume controls;
the tested interface is the opt-in solver API.

## Literal Flare20 work

The preflight keeps the original PM2 source, speed 22, alpha 6°, beta 16°,
gravity/density and numerical settings from the startup study. Nominal eight
panels still produces 55 nodes, 52 elements and 712 unknowns. The two qualified
rigid-pylon attachments preserve original mass positions and source records.
Native attachment semantics remain unverified.

`scripts/advance-isae-ffwt4-equilibrium.py` runs one job and rebuilds its saved
state on a fresh network. Each process uses one BLAS thread, a 512 MiB address
space limit and a 90-second external cap. The audit script checks predecessor
joins, source/settings/kernel hashes, counters, rotation guards and fresh
physical residuals. The retained files are under
`artifacts/isae/ffwt4-continuation-20261106/`; per-job reports identify actual
load factors and accepted steps. Load fraction is a physical continuation
coordinate, not a percentage of computational work completed.

This is a deliberately coarse equilibrium preflight. The original driver mesh,
spatial/time accuracy, gust histories, historical input semantics and shared
execution registration remain separate requirements. No native comparison
value is added merely by accepting an equilibrium continuation step.

The completed audit (`assessment.json`) verifies **17 accepted load steps in
six jobs, zero rejected attempts, and load factor 1.0**. The final state rebuilt
from the exported equilibrium has residual **4.6076e-13**. The first eleven
load targets exactly match the earlier uninterrupted run's retained trace.
The six job reports sum to 209.23 seconds; individual reported times range
from 27.33 to 49.46 seconds. These are per-job monotonic elapsed measurements,
not a whole-browser speed benchmark. Both full source and physical point
locations remain unchanged. The final state is retained in `job-006/result.json`.

| Job | Total accepted steps | Saved load factor | Rebuilt residual |
| --- | ---: | ---: | ---: |
| job-001 | 3 | 1.35128625e-05 | 9.4132e-13 |
| job-002 | 6 | 4.13960941e-05 | 3.4294e-13 |
| job-003 | 9 | 0.00011562897 | 8.7468e-13 |
| job-004 | 12 | 0.000471975591 | 6.4244e-13 |
| job-005 | 15 | 0.0102713445 | 1.2573e-13 |
| job-006 | 17 | 1 | 4.6075e-13 |

[The continuation plot](../../../artifacts/isae/ffwt4-continuation-20261106/continuation.png)
shows hinge angles at the six saved job boundaries. Most hinge rotation occurs
at small applied-load fractions. The final angles are 40.031° and -5.645° under
the retained 16° sideslip. This is an internal homotopy trajectory, not a
physical time history or a comparison against archived ASWING outputs.
