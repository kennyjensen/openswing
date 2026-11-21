# Source-airflow steady trim and time launch

The `drela-moving-airflow-v1` operator now supports mounted steady trim as well
as its existing dynamic analyses. A computed trim stores its solved flight
condition, controls, engine settings, loads, mesh and released constraints in a
launchable equilibrium packet. Time launch retains the same numerical identity
and physical state, releases the steady targets, and checks the full dynamic
residual before accepting snapshot zero. It does not solve another equilibrium.

This follows the [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
description of selecting steady versus unsteady constraints for the same
operating-point equations. The source inertia/damping/airflow equations are
unchanged; the new stationary route selects ordinary trim constraints while
holding frame rates and accelerations at zero. Dynamic network construction
retains its existing canonical frame-constraint validation.

Select **Mounted aeroelastic equilibrium** and **ASWING structure + airflow**,
set ordinary operating targets, and solve. Choose **Use computed equilibrium**,
then **Nonlinear time response**. The selected equations and loaded state remain
active. Saved projects preserve both the trim and its resulting time history.
Operating-point sequences can also use this steady formulation.

The earlier steady-only source operator remains a separate numerical policy;
its saved states are not relabelled. To use this workflow, compute the trim with
the source-airflow option. Steady custom equations, minimum-control allocation,
feedback trim and nonzero frame rates/accelerations remain unsupported here.
Existing dynamic feedback remains supported. Inverse time-actuator/history
targets, stepped axes, full native ASWING agreement and complete feature parity
remain open. No browser default or ISAE score changes.

## Physical checks

An engine trims the original `instrumented-oscillator.asw` to 5 N. The independent
axial-bar result is `F L / EA = 0.010 m`; the original model also specifies a
2 kg tip mass and 10 N s/m damping. A subsequent 3 N engine step must approach
0.016 m with the analytical damped-oscillator transient. Trim targets are
released, so the time solver does not keep forcing the engine back to 5 N.

| Time step | Scaled displacement/velocity error at 0.08 s |
|---|---:|
| 0.005 s | 0.402880% |
| 0.0025 s | 0.100596% |

The error uses displacement scale `3/500 m` and velocity scale
`(3/500) sqrt(500/2) m/s`. It decreases by approximately four under halving.
The fine result passes the predeclared 0.3% gate and 0.6 contraction gate;
the coarse error remains above the fine gate. Steady solvers are replaced with
failing stubs during launch, proving that this path does not recompute trim.
The launch input is unchanged and its checkpoint retains the original engine
setting plus the separate forcing history.

A loaded lifting-wing trim agrees with the stationary source operator in solved
incidence and every node position. Its circulation survives launch and its
zero-rate dynamic residual passes `1e-9`. A two-point engine trim sequence checks
solved setup retention, and changing an engine setting without changing the
saved physical state must fail the launch residual check.

## Verification record

Seven new trim/launch cases pass. Across focused trim, policy, aerodynamic,
engine and feedback-equilibrium coverage, 61 Python cases and 38 JavaScript
checks completed successfully. Completed cases from capped batches are counted
once; their order and separate completion logs are retained.

The actual built app passes the offline trim, time launch and both project
save/restore paths in 41.37 s. The launch preserves the solved 5 N setting,
releases the steady force target, applies the separate 3 N step, and completes
32 steps with two Jacobian builds. It sends exactly two calculation requests
(one trim and one time launch), with no network requests after going offline.
The saved initialization residual is `1.17e-16` and no equilibrium is recomputed.
Replaying the exact exported requests natively passes all 105,811 numeric
comparisons (2,092 steady and 103,719 time-history values), plus structure,
string and boolean comparisons. The unchanged numerical gate is
`2e-8 + 2e-8 |native|`; only the root evaluation counter is excluded. These are
cross-runtime checks, not comparisons with the native ASWING executable.

One additional existing free-frame feedback regression remains **unfinished**
on this revision. It contains a frequency solve and two nonlinear time histories.
The frequency solve was retained separately; the coarse history reached 0.075 s
of its required 0.08 s before the 180 s process cap interrupted its last step.
The fine history and combined original assertions have not completed. This is
not counted as a pass, and its gates were not changed. The progress trace
identifies slow accepted time steps, not a demonstrated stalled solver.

The first physical test run had three reader/setup mistakes (integer versus
JSON object keys, a nonexistent snapshot field, and omitted constructor
arguments). Their corrections preserve every numerical gate and the initial
failed log. The initial native/browser comparator also mishandled integer
Python dictionary keys. Comparison now uses the actual JSON wire format;
the saved first native result is reused without another solve. Initial failure
and process-limit logs remain available.

Code and checks: [source-airflow equations](../../openswing/source_airflow.py),
[native trim/launch tests](../../tests/test_source_airflow_trim.py),
[browser workflow](../../tests/browser/source-airflow-trim.spec.js).
Complete results and execution logs are retained in
`artifacts/isae/source-airflow-trim-20261104/`.
