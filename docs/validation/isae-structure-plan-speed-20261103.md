# Structural-suite planning performance — 2026-11-03

Structural plan construction dropped from **36.78 s to 6.59 s** on this
UserLAnd host: **82.1% less time**, or 5.58× faster, in one paired measurement.
The comparison covers all 13 registered structural jobs and 71,712 required
output slots, including the 12 ST-5 snapshots.

| Measured quantity | Before | After |
|---|---:|---:|
| Full structural plan construction | 36.78 s | 6.59 s |
| Solver-module content-hash reads | 1,768 | 136 |
| Time in those reads | 24.91 s | 1.54 s |
| Other adapter content-hash calls | 296 | 143 |
| Declared jobs / required output slots | 13 / 71,712 | 13 / 71,712 |

The planner now shares content hashes within one invocation. Every new plan
and worker revalidation reads files again. Each job receives independent copies
of the hash records. The full before/after plans are identical after accounting
for the edited planner's own source fingerprint: model sources, solver-module
hashes, target identities, grids, generated recovery code, output counts and
numerical/reference gates all agree.

All **54 relevant structural registration and summary tests pass** in 35.63 s.
A focused adversarial recheck verifies that a same-size kernel edit with its old
timestamp is detected by the next planning call and rejected by a worker using
a stale plan. Editing one job's returned hash records cannot alter another job.
No physics implementation or accuracy threshold changed; no new numerical solve,
reference match, browser validation or distribution build is claimed.

This measurement isolates structural plan construction. The full ISAE source
inventory scan and other suite preparation remain separate costs. Timings are
host measurements, not a guarantee for every machine or full development cycle.

Evidence: [before](../../artifacts/isae/st5-plan-speed-20261103/before.json),
[after](../../artifacts/isae/st5-plan-speed-20261103/after.json),
[complete plan equivalence](../../artifacts/isae/st5-plan-speed-20261103/equivalence.json),
and [reusable measurement script](../../artifacts/isae/st5-plan-speed-20261103/profile-plan.py).
Original helper/test sources and both complete plans are retained beside them.
Existing ISAE scientific counts and whole-family qualifications remain unchanged.
