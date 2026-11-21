# FFWT-2 startup and time-command boundary

This follow-up tests the initial-state interpretation behind the zero-pass roll
acceleration and tip-sensor channels. All literal aircraft inputs, numerical
equations and convergence gates are retained. Native-reference acceptance is
5%. The earlier equilibrium-start trajectory remains separate evidence.

## Recovered source facts

The original FFWT10/V15/DF21 driver sets speed and flap, changes constraints,
then issues `X` for 200 steps and again for 800 steps, both at 0.01 s. It has
no explicit preceding steady solve. No matching `.pnt`, `.set` or `.con` is
present in the pinned source directory.

The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
says time marching uses the current target point as its initial state; a
positive step count starts a new stack. The previous pilot inserted a
zero-local-rate equilibrium before marching. A separate declared alternative
now starts from jig geometry, zero local/frame rates and zero circulation,
without an equilibrium solve. Actual historical defaults and the precise `C`
constraint preset remain unauthenticated.

The raw t=0 seed has residual 0.05438 and is explicitly retained as uncomputed.
Only the complete BDF1 state at 0.01 s and subsequent converged states enter
the comparison chain. The ordinary checkpoint validator replays the first
accepted BDF equations before continuation. This establishes the discrete
history, not a continuous initial-derivative certificate.

The original table's first two rows also support restarting BDF at 2 s:

| Relation at 2.01 s | First difference | Archived value | Printed-rounding bound |
|---|---:|---:|---:|
| Roll acceleration, degrees/s² | -78.1000 | -78.1145 | 0.10005 |
| Bank derivative, degrees/s | -185.600 | -185.576 | 0.1005 |

All subsequent 799 stencils in each channel agree with BDF2 within printed
rounding. A separate command-boundary branch requests one BDF1 step from 2.00
to 2.01 s, then BDF2 with its retained predecessor. The continuous-history
alternative is retained to isolate the effect of this boundary. Compatibility
with the printed rows supports this interpretation; it does not recover the
unexported initial operating point.

## Sensor-output audit

Unsteady Technical Description Eqs. 98, 111 and 114 define the sensor triad and
its bank in Earth coordinates. An independent Rodrigues reconstruction from
the saved nodal rotation vectors, composed with the saved aircraft rotation,
reproduces all ten tip banks in the earlier 2.00–2.04 s comparison window.
Maximum difference is 2.843e-14 degrees. The earlier mismatch is in the computed
motion, not a bank-sign or angle-display conversion error.

Evidence is retained in `artifacts/isae/ffwt2-startup-20261106/`, including the
source audit, original uncomputed seed, first BDF step, validated checkpoints,
individual progress/timeout logs and assessment tests. Every native table row
remains required; the full selected denominator is 4,005 scalar outputs.

## Completed comparison

The new jig-start trajectory reaches 2.04 s. The command-boundary branch
recomputes the identical 2.00 s state, takes one BDF1 step to 2.01 s and then
three BDF2 steps. Every accepted state meets the unchanged 1e-8 residual gate,
with no rejected steps. Two earlier segment timeouts are retained; their
unfinished outputs do not enter either comparison. The serial retries use
shorter job durations with the same 0.01 s physical time step.

Each column below compares the same five native rows, 2.00–2.04 s, at 5%.
Errors are the median and maximum among failed scalar comparisons. These are
three separate startup/protocol scopes; their passing counts are not combined.

| Channel | Earlier equilibrium start | Jig start, continuous BDF | Jig start, command restart |
|---|---|---|---|
| Roll acceleration | 0/5; 123.17% / 156.30% | 0/5; 159.97% / 199.87% | 0/5; 157.86% / 199.87% |
| Roll rate | 5/5 | 5/5 | 5/5 |
| Aircraft bank | 5/5 | 0/5; 7.38% / 7.45% | 0/5; 7.38% / 7.45% |
| Sensor 2 bank | 0/5; 45.65% / 50.71% | 0/5; 64.52% / 72.92% | 0/5; 64.44% / 72.83% |
| Sensor 3 bank | 0/5; 20.87% / 21.12% | 0/5; 31.97% / 32.28% | 0/5; 31.86% / 32.18% |
| Computed total | 10/25 | 5/25 | 5/25 |
| Full selected table | 10/4,005 | 5/4,005 | 5/4,005 |

At 2.00 s the jig-start roll acceleration is +72.8974 degrees/s² against the
native −72.9894 degrees/s². The acceleration discrepancy therefore predates
the second command. Across the comparison window, resetting history changes
acceleration by at most 4.7358 degrees/s², roll rate by 0.01923 degrees/s,
aircraft bank by 0.00509 degrees and either sensor bank by 0.08582 degrees.
It does not recover a failed channel.

Neither alternative resolves the mismatch. The source-supported restart is
now reproducible and checked, but the original initial operating point and
constraint preset remain unknown. Choosing the closer startup from these
outputs would not establish which one ASWING used. No physical inputs or
initial state were fitted to the reference.

All **12 focused assessment tests pass**, including rejected altered seeds,
missing discrete replays, missing time steps and an incorrect restart stencil.
The saved-only comparison audit verifies all 138 production module hashes,
source hashes, numerical gates, identical boundary state and full denominator.
Production equations, the browser build and distribution archives are unchanged
by this validation-only follow-up. Machine-readable results are in
`comparison.json`, `continuous-assessment.json` and `command-assessment.json`.

## Remaining work

The acceleration and tip-motion dynamics need an independent mechanical/aero
audit, followed by time and spatial refinement. The full selected history still
has 3,980 unrun scalar targets in each scope. Other source configurations and
shared-suite registration also remain open. The output-conversion audit rules
out a sensor display conversion error; it does not certify the underlying
coupled equations or establish native ASWING agreement.
