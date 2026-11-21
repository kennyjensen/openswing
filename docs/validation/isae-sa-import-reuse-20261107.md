# Serial SA runner startup cost

**Follow-up:** direct forking from the result collector is suspended. The first
larger SA-10 batch reached the 512 MiB limit because children inherited the
collector's plan/results. Seven allocation failures, 61 computed results and
one interrupted job are retained in the
[resource-failure record](../../artifacts/isae/sa-import-reuse-20261107/inherited-memory-failure/execution.json).
The entire attempt is separate from the accepted baseline, which remains at
372 jobs. Report serialization also reached the memory limit. These are
runner failures, not additional aerodynamic failures.

A clean `forkserver` now isolates library imports from the collector. Streamed
atomic JSON writing removes duplicate full-report strings. All 18 process,
timeout, scheduling and report-writing tests pass; the initial test-import
failure is retained separately. A new 13-job benchmark includes the larger
SA-10 case that exposed the allocation problem. The replacement passes its numerical checks (maximum scaled difference
1.99e-16), but its observed median time is 10.45 seconds versus 8.08 seconds
for the ordinary controls, so it is **not adopted**. The large 896-strip
case also exceeds 512 MiB under ordinary startup; both launch methods
compute it successfully at 768 MiB. The baseline continues with ordinary
workers at that cap and streamed reports. All 19 final process/report
regressions pass. The original 18-pass run and one failed test-import
attempt remain available.

The SA rerun can reuse Python library imports while keeping every physical
solve in a separate process. The original worker, equations, numerical gates,
60-second timeout, process cleanup and source checks remain unchanged. The
parent runs no physical solver. The accepted baseline uses ordinary
Python startup. The attempted import-reuse batch is preserved separately
after the resource failure described above.

Fifteen process isolation, timeout, exit-code and bounded-scheduling tests pass.
The predeclared 12-job benchmark covers all six selected adapters, a known
circulation failure and a source blocker. Median physical-worker wall time
falls from **8.47 to 2.10 seconds**, a **4.03×** speedup; the shared preload
cost is 5.22 seconds. Including preload and reporting, the benchmark takes
99.17 versus 41.82 seconds. These are runner timings, not faster physics.

The initial exact-result gate **failed** for SA-15 and remains recorded as
failed. Eleven jobs matched exactly. SA-15 differed by at most 1.99e-16 on
the `abs(a-b)/max(1,abs(a),abs(b))` scale and used eight rather than seven
circulation evaluations. Two separately declared ordinary cold repeats both
produced the complete scientific result from the forked worker exactly,
including all evaluation counts. Every numerical and native-reference
pass/fail decision agrees across all four runs. This establishes ordinary
cold-run variation in the observed difference; no tolerance was changed.

Direct import reuse was initially adopted on that follow-up evidence, without relabeling the
initial failed gate. All benchmark runs remain separate from native progress;
they add **zero** comparison targets or passes. The production solver and
original suite runner are unchanged. Original failed native jobs are retained
and are not retried automatically.

The parent uses one thread, with approximately 162 MiB resident memory in the
full-plan benchmark. Each run retains memory and launcher-source records.
Resource use still needs monitoring on larger jobs and accumulated results;
the benchmark does not establish a memory bound for every later case.

- [Predeclared benchmark](../../artifacts/isae/sa-import-reuse-20261107/selection.json)
- [Original exact-result audit, including failure](../../artifacts/isae/sa-import-reuse-20261107/audit.json)
- [Ordinary cold-repeat audit](../../artifacts/isae/sa-import-reuse-20261107/cold-repeat-audit.json)
- [Process and scheduling tests](../../artifacts/isae/sa-import-reuse-20261107/launcher-tests.log)
- [Launcher](../../scripts/run-isae-preloaded.py)

The first clean-server run completed all 13 raw worker outcomes, but its
final report identity check rejected a changed resolved filesystem path.
UserLAnd hardlink emulation had changed the internal alias while the plan
bytes and launcher hashes remained identical. The failed final exit is
retained. Working plans are now regular copies, and the launcher pins the
logical requested path plus its content; a regression tests alias changes
and still rejects changed bytes. The independent comparison uses all saved
worker results, not a claimed successful report from that failed exit.

- [Clean-server and 768 MiB comparison](../../artifacts/isae/sa-import-reuse-20261107/forkserver-study/audit.json)
- [Final 19 process/report tests](../../artifacts/isae/sa-import-reuse-20261107/forkserver-tests-3.log)
