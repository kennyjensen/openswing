# SA-6: sensitivity to the published stall-transition width

2026-11-01. Halving or doubling the documented width does not resolve the
SA-6 mismatch. Both alternatives lose static and derivative matches in the
existing eight-state pilot. Production equations, defaults and registered
comparison counts remain unchanged. The native width is still unverified.

The Technical Description, section 5.7, equations 203–204, distinguishes
stall strength `Ks` from transition width `Delta cl`. Width controls the
sharpness of the lift-slope transition; Drela gives approximately 0.05.
This check uses fixed widths **0.025 and 0.10**, chosen before execution as
a factor-of-two bracket. They are sensitivity tests, not published alternate
settings, fitted parameters or changes to the reference data.

The scope retains the prior eight pilot states: all four paired aileron
models at 4° and 44° control, 128 requested intervals, alpha 12°, speed
20 m/s, zero PG Mach, pointwise circulation, frozen influences and `Ks=20`.
The last two settings remain a qualified historical-setup hypothesis.
Literal section data, all six static outputs, all 36 state derivatives and
the existing 3%/strict-zero comparison policy are retained.

| Transition width | Static checks | State derivatives | Pitch-rate subset | Derivative gains / losses |
|---|---:|---:|---:|---:|
| 0.05, saved control | 48/48 | 253/288 | 24/48 | — |
| 0.025 | 44/48 | 180/288 | 18/48 | 6 / 79 |
| 0.10 | 28/48 | 140/288 | 12/48 | 0 / 113 |

At width 0.025, failed CLq errors have median 4.34%, maximum 6.60%;
failed Cmq errors have median 4.83%, maximum 8.29%. At width 0.10 those
become 5.10%/17.45% and 5.75%/16.80%, respectively. These percentages
describe only failed checks in this pilot, not the complete SA-6 scope.

Neither variant meets the predeclared extension rule: at least one gain,
with no derivative or static losses over all eight states. No broader
sweep or setting change follows. This rejects these two width substitutions
under the retained setup; it does not prove that every possible width,
combined parameter change or historical implementation is excluded.

Sixteen cold bases and analytic six-column responses finish in one process
with one BLAS thread, taking **7.44 seconds after imports**. There are no
browser jobs or background workers. A separate implementation of the
straight-wing vortex fields, complete leakage residual and Jacobian, and
force/moment derivatives reproduces the results:

| Independent check | Maximum absolute difference or residual |
|---|---:|
| Nonlinear circulation residual | 1.73e-13 |
| Linear circulation residual | 3.78e-14 |
| Static coefficients | 5.56e-16 |
| State-derivative coefficients | 5.79e-15 |
| Circulation response | 2.51e-13 |
| Circulation Jacobian | 2.56e-13 |

Every result passes the existing convergence and local-flow validity checks.
A solver-free verifier reparses the original native decimal tokens and
scores all **672 comparisons** with exact rational tolerance arithmetic.
The execution and verification processes both exit normally with status 0.
This verifies the diagnostic calculation, not historical ASWING equivalence.

The qualified full SA-6 result remains **528/528 static, 528/528 F1 and
2,780/3,168 state checks**. Registered default SA-6 static acceptance remains
**290/528**. The full project goal is incomplete.

Evidence: [plan](../../artifacts/isae/sa6-stall-width-20261101/plan.json),
[analysis and every comparison](../../artifacts/isae/sa6-stall-width-20261101/analysis.json),
[receipt and source hashes](../../artifacts/isae/sa6-stall-width-20261101/receipt.json),
[serial producer](../../artifacts/isae/sa6-stall-width-20261101/run.py),
[native-token verifier](../../artifacts/isae/sa6-stall-width-20261101/verify.py).
