# AE-2: 1° coverage extended through 17 m/s

Observed 2026-11-10 UTC. The current comparison advances from **608/2,200 to
680/2,200 at 5%**. All **72 newly accepted scalar comparisons pass**: median
error **0.38106%**, maximum **2.24815%**. Production equations, defaults,
original inputs and numerical tolerances are unchanged.

The new batch attempted sixteen original states at IAS 10–17 m/s, on both
meshes. Thirteen finished normally. Three timed out after saving a converged
solution. Independent physical rechecks completed those three states and two
saved states from the preceding batch, adding five accepted states without
repeating any equilibrium solve. Original timeout receipts remain intact.

| Current full-scope outcome | Scalar comparisons |
|---|---:|
| Pass at 5% | **680** |
| Computed mismatch | 12 |
| Unresolved failed-run output | 20 |
| Finite reference, comparison not yet run | 1,392 |
| Unavailable original reference value | 96 |
| Total required | **2,200** |

All three 5° sweeps have been attempted. The partial 1° uncoupled sweep now
contains **132/132 passing computed values**, from 33 accepted physical states.
Its 36 terminal records cover 144 required slots: 132 passes, four unresolved
outputs and eight unavailable zero-speed values. These are subsets of the
2,200-slot family, not independent progress scopes. The 1° plan still has
**126/162 records unrun**; its coupled layups have not started. All 10° and
15° sweeps remain required.

The twelve native mismatches remain in the 5° negative-coupling sweep at
17–19 m/s, where the solution takes the opposite deflection branch. Their
median error is **249.161%**, range **227.303–356.704%**. No additional computed
mismatch appears in this update. The unresolved executions are the 1° uncoupled
4 m/s coarse case and the four previously recorded 5° negative-coupling cases.
The original ten failed process receipts remain failures; five now also have
separate successful physical-verification receipts.

![Original 1° ASWING curves and current OpenSwing coverage](../../artifacts/isae/ae2-beta1-recovery-staged-0036-20261110/curves.png)

The curves show every finite original 1° reference point. Missing predictions
are not interpolated. All 132 current 1° values pass; their median/max errors
are **0.35155% / 2.25212%**. No experimental curve or alternate solver setting
is included in this native-reference count.

## Physical and mesh checks

The current total is **173 accepted states / 692 computed values**, with
**3,114 passing physical checks** and **85 passing mesh pairs** (170 separate
deflection/heading checks). Maximum mesh change remains **0.04078%** and
maximum fresh full residual remains **9.995e−13**. The original nominal 80/160
meshes have 81/161 intervals after breakpoints; these are not claimed identical
to the report's original 40-node arrays.

Five completed original cold solutions were independently restored and checked:

| 1° uncoupled original state | Fresh full residual | Physical checks |
|---|---:|---:|
| 3 m/s, nominal 160 | 2.292e−13 | 18/18 |
| 4 m/s, nominal 160 | 4.150e−13 | 18/18 |
| 16 m/s, nominal 160 | 1.374e−13 | 18/18 |
| 17 m/s, nominal 80 | 2.811e−13 | 18/18 |
| 17 m/s, nominal 160 | 3.073e−13 | 18/18 |

Each check rebuilds the original network, restores the saved state, evaluates
one fresh residual, and checks identity, force/moment balance, clamp conditions,
sensor reconstruction and aerodynamic totals. Requests, sources and production
code must match their recorded hashes before and after verification. Acceptance
requires all checks, a residual no greater than 1e−12, successful process exit
and completed source verification. The 4 m/s coarse case has no saved solution
and cannot be accepted through this route.

The first verification attempt, which included all source hashing inside the
numerical deadline, timed out and remains recorded separately. The staged
verifier checks those same sources before launching and after reaping its
numerical child. All five staged checks finished within the unchanged
one-thread, 512-MiB, 15-CPU-second and 25-second numerical limits. They used
2.835–3.213 CPU seconds each and at most 105,320 KiB peak RSS. These are
verification costs, not new equilibrium or browser timings.

## Evidence and remaining work

The saved-only assessor verifies the four disjoint current runs and the five
new verification receipts. It recomputes the same original comparison slots;
no duplicate target or alternative branch receives another vote. Its first
integration attempt exposed a mismatch with derived summary metadata, now
fixed without weakening original-input equality. Three focused unit tests pass,
including 23 rejection scenarios. The complete saved-data assessment passes
with zero production imports or physical calls. Its file-audit wall allowance
is 60 seconds; its 15-CPU-second/512-MiB caps remain unchanged. Numerical
worker deadlines are unchanged.

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog govern the comparison. Jan Part IV §3.2, pp. 8–12,
Figure 3 specifies the three layups and 1°/5°/10°/15° series. Literal `!B`
commands, frozen influence, sensor placement, atmosphere and original material
properties remain as registered. Historical setup qualifications from the
[preceding report](isae-ae2-beta1-current-20261110.md) remain open.

Next: continue the pinned 1° plan at uncoupled IAS 18 m/s, then the two coupled
layups, in small serial batches. Resolve outstanding executions and the native
branch discrepancy separately. The correction-merit diagnostic remains
unpromoted; browser/build tests remain held. AE-2 is not yet validated.

[Full assessment](../../artifacts/isae/ae2-beta1-recovery-staged-0036-20261110/assessment.json) ·
[Immutable original batch snapshot](../../artifacts/isae/ae2-beta1-sweeps-current-20261110/snapshot-0036/report.json) ·
[Saved-state verification plan](../../artifacts/isae/ae2-beta1-recovery-staged-0036-20261110/plan.json) ·
[Retained first verification failure](../../artifacts/isae/ae2-beta1-recovery-0036-20261110/AE-2-b01-ias003-m160/terminal.json)
