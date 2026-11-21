# FFWT-2 complete time-matrix optimization

FFWT-2 can now use the existing analytical internal-load and reaction derivatives
in its complete Newton fallback. Other matrix columns still differentiate the
full current equations. The physical equations, time step, Newton acceptance,
line search and tolerances are unchanged.

## Controlled before/after comparison

Both calculations resume the same saved 1.10 s state and advance to 1.12 s.
The preceding kernel is retained in a frozen manifest; only
`openswing/time_integration.py` changes. AST and source comparisons verify that
the change replaces the full finite-difference assembly loop and leaves the
equations and Newton iteration logic intact.

| Measurement | Original full stencil | Analytical mechanical columns |
|---|---:|---:|
| Local runtime | 38.078 s | 33.135 s |
| Residual evaluations | 936 | 715 |
| Matrix builds | 4 | 4 |
| Newton iterations | 12 | 12 |
| Accepted / rejected time steps | 2 / 0 | 2 / 0 |

The 713-variable matrix contains 222 eligible mechanical columns. Computing
these from one physical-state capture avoids 221 residual evaluations per full
matrix. Every other column keeps its original stencil. Unsupported mechanical
contexts retain the original full fallback; force/moment measurement feedback
also retains the complete coupled stencil.

All **49,272 numerical result/checkpoint fields** agree within the existing
`2e-8 * (1 + abs(reference))` gate. The largest difference uses only
1.182e-7 of that allowance. The three saved roll rates are identical. Runtime
measurements are local; they are not ASWING or browser timing comparisons.

Five focused matrix/Newton tests and six saved-history assessment tests pass.
The matrix tests include independent full and centered stencils, BDF1/BDF2,
unavailable-derivative fallback, load-measurement feedback, and recovery after a
failed sparse factorization. The assessment tests reject missing intervals and
altered prefix/checkpoint provenance, and preserve every native output target.

## Original command qualification

The original driver contains `%`, `4 23`, `c`, `d` before time execution. The
[ASWING 5.97 User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes `C` inside the constraint editor as `freqCalc defaults`, and `D` as
completion of the editor. Therefore the final original constraint table cannot
be established from `4 23` alone. The guide does not specify the individual
assignments made by that preset here. This is an additional reason to retain
the pilot's declared free-roll rig interpretation as a qualification, not an
authenticated replay of all original commands. No original output is used to
fit the starting state or constraints.

The selected source model, driver, 801 native rows and all 4,005 output targets
remain unchanged. The comparison allowance is 5%; numerical and near-zero
absolute gates are unchanged. Full 2–10 s history, temporal/spatial refinement,
historical startup, other source models and shared family registration remain
required.

## First native comparison window

The saved continuation reaches **2.04 s**. All 94 steps from the frozen 1.10 s
prefix complete with no rejected steps; all 95 unique states pass the original
residual gate (maximum 9.351e-9, limit 1e-8). The 24 completed segments take
262.34 seconds in aggregate, excluding the earlier prefix and incomplete
attempts. The latest 17 four-step jobs all complete within their individual
90-second limits, taking 4.28–11.10 seconds each. Checkpoint boundaries retain
the BDF history and replay the saved discrete equations.

**10/25 computed comparisons pass at 5%**, covering five original rows from
2.00 through 2.04 s. The complete selected scope is **10/4,005**, with 3,980
unrun values. These are conditional comparisons under the declared startup;
they do not complete the original trajectory or family.

| Output | Passing / computed | Error over this window |
|---|---:|---|
| Roll rate | 5/5 | 0.134–2.833% |
| Continuous aircraft bank | 5/5 | 3.793–3.924% |
| Roll acceleration | 0/5 | Failed median 123.17%; max 156.30% |
| Sensor 2 bank | 0/5 | Failed median 45.65%; max 50.71% |
| Sensor 3 bank | 0/5 | Failed median 20.87%; max 21.12% |

At 2.00 s the original/current roll rates are 186.357/186.6066 degrees/s,
while their accelerations are -72.9894/+41.0895 degrees/s². The nearly matching
rates therefore have different local slopes. Aircraft bank is
-299.443/-287.6940 degrees. Sensor banks are 93.2353/131.8611 and
81.2771/98.4395 degrees. Longer histories, initial-state/constraint recovery
and hinge-motion refinement are needed to distinguish causes of the dynamic
discrepancy. No phase alignment or fitted initial condition is applied.

An independent check of the complete native table finds that **799/799**
available BDF2 rate derivatives agree with the printed accelerations within
their decimal-rounding bounds. Similarly **799/799** bank derivatives agree
with minus the roll rate. This supports the units, time step and signs used
for the comparison; these are reference consistency checks, not new solver
matches. See `native-kinematics.json` and `assessment-204.json`.

## Browser runtime verification

The dedicated source-airflow fixture passes in the shipped Pyodide/WebAssembly
runtime. Its 106-variable complete matrix uses 30 direct columns and 77 residual
calls; the maximum scaled difference from the full stencil is 5.001e-13, and
every other column is bitwise identical. A nonlinear Newton callback check
converges to its known root with residual 7.23e-13. All 138 development/public/
built kernel modules have identical bytes. This is numerical WASM verification,
not a full UI or FFWT-2 browser trajectory test.

Two earlier fixture attempts are retained: the transient demonstrator is
rejected for differing incident material frames, and the heave/pitch example
for a vertical fuselage Euler chart. These are existing source-time geometry
restrictions; neither fixture reached the matrix check. No production geometry
guard was changed. The successful fixture is the unchanged
`examples/source-airflow-check.asw`.

Evidence: `artifacts/isae/ffwt2-tangent-20261105/`, including `code-change.json`,
`step-parity.json`, the test logs, original timing runs and separately retained
timeout attempts. The earlier prefix and initialization evidence remain in
`artifacts/isae/ffwt2-pilot-20261105/`.
