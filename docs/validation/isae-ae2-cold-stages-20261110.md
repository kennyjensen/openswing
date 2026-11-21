# AE-2: cold-solve tracing and bounded continuation diagnostics

Observed 2026-11-10 UTC. The previously failed **18 m/s, nominal-160**
negative-coupling case now reaches a fully checked solution in four separate
continuation jobs. Its branch still disagrees with archived ASWING. The
**20 m/s, nominal-80** case remains incomplete at an accepted **87.5% load**
checkpoint. The primary native score remains **548/2,200**: this diagnostic
study is separate from the original suite attempts and adds no primary votes.

| Diagnostic | Outcome | Completed-stage Newton iterations | Damped iterations | Iterations reusing a matrix |
|---|---|---:|---:|---:|
| 19 m/s, nominal 80 control | Complete; exact agreement with the preceding cold result | 72 | 42 | 22 |
| 18 m/s, nominal 160 | Complete; all 18 physical checks pass | 75 | 47 | 20 |
| 20 m/s, nominal 80 | Incomplete; 87.5% load checkpoint retained | 101 | 71 | 22 |

The last row excludes the killed final attempt, whose partial trace records
additional iterations. No completed-stage iteration in these diagnostics uses
the full-matrix fallback. Matrix storage, direct mechanical derivatives and
direct circulation blocks remain the existing structured implementation.

![Newton progress with checked load boundaries](../../artifacts/isae/ae2-cold-stages-20261110/newton-progress-verified.png)

Blue residual points are iteration-start values; green stars show independently
checked converged load boundaries. Newton damping is distinct from rejecting
an entire load step. The figure retains the rejected full-load attempt before
the successful 87.5% step; it excludes the later terminated partial trace.

## What completed, and what did not

The 19 m/s control has **zero difference in all four sensor outputs and every
restored solution coordinate** relative to the earlier accepted ordinary cold
solve. Its 18 physical checks plus two parity checks pass. This confirms the
production checkpoint route preserves that complete solution without a new
initial guess or an accuracy relaxation.

At 18 m/s on nominal 160, the fresh residual is **3.630e−14**. Tip Earth Y is
**−0.28175235 m**, versus native **+0.218111 m**; heading is **−21.87831°**,
versus **+16.7860°**. Sensor speed matches within **0.05957%**, while tip Y,
heading and local sideslip still differ by **229.178–284.755%**. This is the
same negative-deflection branch found on nominal 80, not a match obtained by
changing stiffness, stall parameters, geometry or reference data.

At 20 m/s, the attempted jump from 75% to full load exhausts its 30-iteration
attempt with residual 0.006072. The existing algorithm then halves the load
increment and converges at 87.5%, with residual **7.297e−14**. The next full-load
attempt takes accepted Newton fractions as small as **1/64**, repeatedly
refreshing the structured matrix. Its latest captured maximum residual is
0.002593 at iteration 8. The process reaches the supervisor deadline before
producing a full-load result. The maximum component need not decrease at every
iteration: the existing line search checks the squared residual norm.

The 87.5% checkpoint is an unfinished continuation state, not an equilibrium
at the requested operating point, a validation pass or a dynamics launch state.
No timed-out process was restarted. Both earlier failed full-run attempts and
the new diagnostic timeout remain on disk; the checkpoint is available for a
subsequent explicitly recorded investigation.

## Execution and verification

The first diagnostic adds only the existing `progress` callback to the
unchanged integration helper. Its whole-control run reaches the 75%-load
attempt but is killed by its supervisor after **30.021 wall seconds**, using
**7.153 CPU seconds** and 101.3 MiB peak RSS. It does not establish control
parity; the later staged control supplies that evidence.

The subsequent study uses the existing production `continuation` request with
one accepted load step per child. It preserves normalized coordinates exactly,
checks checkpoint identity and full residuals on restore, reruns the initial
rank gate, retains the original matrix-refresh and rejection rules, and requires
fresh full-load physical checks before declaring a result complete.

**13 staged processes are terminal and reaped: 12 exit zero, one times out.**
The completed control and 18 m/s result pass **38 checks**. The saved-only audit
verifies source pins, stage ordering, identical original requests apart from
checkpoint transport, exact checkpoint linkage, resource receipts and comparisons.
It imports no production kernel and performs no new physical evaluations.

The numerical children retain **one BLAS thread, 512 MiB address space and
15 hard CPU seconds**. A soft CPU signal at 14 seconds writes a stack trace.
Diagnostics use a **25-second worker alarm after input setup and a 30-second
outer supervisor**; the preceding native suite used a 25-second supervisor.
These wall-time guards are different and are not an equal-budget speed benchmark.
Peak recorded staged use is **137.0 MiB** and **10.297 CPU seconds**; successful
children take at most **27.666 wall seconds** including startup and checks.

The incomplete last job uses only **5.709 CPU seconds** before its 30.086-second
supervisor deadline. This and the whole-control timeout show that wall-time
failures here cannot be attributed to exhausting the CPU or memory caps.
Startup, I/O and scheduling contributions have not been separately measured.
The exact cause of the older uninstrumented SIGKILL outcomes remains unknown.
Splitting work adds setup costs; no whole-solve or browser speedup is claimed.

## Relation to the documentation and next investigation

The authoritative source catalog, Jan Part IV PDF/text and Drela steady PDF/text
hashes were checked. Jan **Part IV §3.2, pp. 8–12, Figure 3** remains the native
setup/result target. The source model, archived script and output bindings are
unchanged. Original ASWING settings, stopping behavior, stability and uniqueness
are still unrecovered; these diagnostics do not prove the archived curve wrong.

Drela **steady §4.6, Eq. 176 and p. 36** describes retaining circulation coupling
while lagging nonlocal geometry in the iteration matrix to preserve efficient
structural blocks. The current implementation follows that structure. The
traces show many damped steps and matrix refreshes, so checking the accuracy of
the lagged direction at a difficult stored state is a more specific next action
than assuming a dense matrix bottleneck. **§5.7, pp. 40–42** retains a unique
section inverse lift relation through stall; it does not establish uniqueness
of the complete nonlinear aeroelastic equilibrium.

Next: compare the lagged and complete physical Jacobian directions at the saved
87.5%-load state with a full-load residual, checking directional derivatives and
the same merit function. Any performance change must preserve the full physical
acceptance gates and be verified on both controls and failed cases. The other
two failed native mesh/speed combinations, nine remaining incidence sweeps,
browser/build tests and the full project goal remain open.

[Independent assessment](../../artifacts/isae/ae2-cold-stages-20261110/assessment.json) ·
[Staged plan and evidence](../../artifacts/isae/ae2-cold-stages-20261110/plan.json) ·
[Original instrumented attempt](../../artifacts/isae/ae2-cold-trace-20261110/plan.json) ·
[Plot reproducer](../../artifacts/isae/ae2-cold-stages-20261110/plot.py) ·
[Primary native comparison](isae-ae2-beta5-sweeps-current-20261110.md)
