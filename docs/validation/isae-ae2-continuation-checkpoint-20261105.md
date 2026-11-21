# AE-2 continuation checkpoint — 2026-11-05

This is the earlier ascending-only checkpoint. The
[completed follow-up](isae-ae2-continuation-20261105.md) adds full-load and
descending controls, verified browser delivery, and the positive branch at
18–20 m/s. Its remaining-work list supersedes the checkpoint below.

The nominal-80 negative-coupling, beta=5° continuation sweep is complete:
19 of 20 positive-speed states computed, with 266/266 physical checks passing
over the computed states. The 20 m/s state failed its Newton line search at
residual 0.0873 after 82.6 seconds; it did not time out. The zero-speed native
record has unavailable outputs and is not included in these 20 states.

These are solver and physical-consistency results, not native-ASWING matches.
The registered AE-2 baseline remains **2/2,200**. Following the preceding speed's
equilibrium does not recover the archive's positive-deflection branch at
17–19 m/s. Two representative comparisons are:

| Speed | Quantity | OpenSwing | Archived ASWING | Absolute relative error |
|---|---|---:|---:|---:|
| 17 m/s | RY (m) | -0.24845008 | +0.191155 | 229.97% |
| 17 m/s | Psi (degrees) | -18.844043 | +14.8018 | 227.31% |
| 19 m/s | RY (m) | -0.32014685 | +0.190580 | 267.99% |
| 19 m/s | Psi (degrees) | -27.153774 | +14.7329 | 284.31% |

The source fix addresses an actual warm-start derivative failure: a generic
finite-difference probe moved the clamped root through the ground image plane.
Source-coupled warm correction now uses the network's boundary-aware Jacobian
for both sparse correction and dense recovery. Physical clearance checks remain
in force. Four new tests and 56 existing seeded-corrector tests pass.

The first eight retained points used the original 1e-8 solver tolerance. An
earlier 9 m/s solve passed the residual criterion but failed the unchanged moment
balance check. New points 9–20 used a tighter requested tolerance of 1e-10;
the earlier failure remains retained. Reference and physical acceptance limits
were not relaxed.

Evidence:

- [Completed sweep and exit records](../../artifacts/isae/ae2-continuation-tight-20261105/serial-m80.log)
- [17 m/s report](../../artifacts/isae/ae2-continuation-tight-20261105/cases/ordered-m80-v17/report.json)
- [19 m/s report](../../artifacts/isae/ae2-continuation-tight-20261105/cases/ordered-m80-v19/report.json)
- [20 m/s failure](../../artifacts/isae/ae2-continuation-tight-20261105/cases/ordered-m80-v20/report.json)
- [Retained first-attempt study](../../artifacts/isae/ae2-continuation-20261105/plan.json)
- [Default-tolerance study](../../artifacts/isae/ae2-continuation-fixed-20261105/plan.json)
- [Reuse and tighter-tolerance plan](../../artifacts/isae/ae2-continuation-tight-20261105/plan.json)
- [Four new regression tests](../../artifacts/isae/ae2-continuation-20261105/source-seeded-tests-corrected.log)
- [56 existing regression tests](../../artifacts/isae/ae2-continuation-20261105/seeded-regressions.log)

Remaining work: four prepared direct-full-load controls at 17/20 m/s on nominal
80/160 meshes; broader affected regression checks; offline browser verification;
and synchronization of the browser kernels and downloadable bundles. The fine
ordered sweep is not run. Historical ASWING initialization and settings remain
unconfirmed. No numerical job was running at this checkpoint.
