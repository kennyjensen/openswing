# UA-1: inclined periodic calculation in the built browser worker

Updated 2026-11-02. **1/1 browser periodic check passes**, with all **14 accuracy
and runtime gates passing**. The actual distributed worker computes eight
continuous cycles at 9°, k=0.94, peak-to-peak A/c=0.5 and 320 steps/cycle.
All **2,561 unique snapshots** are audited; all **2,560 steps** converge with
zero rejected steps. No production code or numerical tolerance changes in this
increment. This verifies an existing physical case in WASM; it adds no new
frequency, amplitude, mesh-refinement or native-ASWING comparison pass.

| Quantity | Full cold-history error | Final periodic-cycle error | Limit |
|---|---:|---:|---:|
| Lift | 0.01442% | 0.01719% | 0.1% |
| Circulation | 0.02291% | 0.03391% | 0.1% |
| Circulation rate | 0.01563% | 0.01499% | 0.1% |

Errors use dynamic variation, not the nonzero steady mean: lift and circulation
are normalized by peak departures from their reference means in the periodic
cycle, and from the steady initial value for the cold history. Rate uses its
reference peak. Every strip participates. The independent target is the
[published section-equation reference](isae-inclined-section-heave-reference.md),
using integrating-factor quadrature and the exact homogeneous startup transient.
Its separate direct DOP853 check and original acceptance limits remain intact.
The provisional 3% steady-aerodynamics allowance is not used.

Fundamental amplitude error is **-0.00762%**;
phase error is **+0.00682°**. Mean-lift
error is **-0.001887%** of dynamic lift
variation. Maximum final cycle-to-cycle change is
**0.003560%**, below 0.01%.
Maximum normalized nonlinear residual is **9.9204e-11**,
below 1e-10. First-step rate and motion errors remain diagnostics with the same
definitions as the native study; no easier limits are introduced.

## Runtime and retained-history verification

The built worker loads its own Pyodide, NumPy/SciPy and 136 packaged solver
modules. Their exact bytes and runtime provenance are recorded. It starts from
its own production steady equilibrium, with the complete forcing table present
from startup. The independent reference is never supplied as an initial state.
There are 128 serial requests of 20 steps, each capped at 45 seconds. Both BDF
predecessors survive continuation. The final forcing cutoff correctly clears
next-step history while retaining the complete accepted BDF2 method record.
The audit checks those records, coefficients, force axes, all circulation/rate
values, frame motion, times, solver orders and exact checkpoint joins.

Request times are **6.13–19.83 seconds**;
their sum is 1132.45 seconds. Runtime/model inspection is a separate request capped at 45 seconds before
the first solve in each worker lifetime. Its timings are recorded separately. This is a segmented validation measurement,
not an uninterrupted solve benchmark or full application UI timing.
Chromium 145.0.7632.0 reports no page errors.

Maximum scaled difference from the retained CPython calculation is
**3.6157e-09**, below 2e-8.
That historical calculation predates the separately verified
[forcing-endpoint rounding repair](isae-ua2-time-endpoint-fix-20261101.md).
Exactly one module, `forcing.py`, differs; the other 135 match. Both versions
are pinned, and the old frozen source and outputs are preserved. This is
agreement with the retained earlier Python result; it is not described as a
comparison of identical source versions. The browser also independently passes
the unchanged waveform, amplitude, phase, mean, settling and residual gates.

The first preparation attempt caught that source difference and started no
solver. A second prepared plan was superseded before execution when pre-run
review caught an obsolete assumption about terminal continuation history.
Both preparations remain recorded. The original 40-step browser pilot passed,
but its first resumed request exceeded the combined startup/solve deadline.
That failed batch remains separate. This fresh study starts from production
equilibrium again, separates runtime loading, and uses smaller 20-step requests
on the identical physical time grid. Its pilot and all remaining browser
requests finish successfully. 37 focused setup, reference,
endpoint and checkpoint-verifier tests pass.
The initial combined regression command reached its 90-second shell limit;
that incomplete attempt is preserved. All selected tests subsequently finish
in separate serial jobs, each with a 60-second limit and an individual result.

## Remaining scope

This uses four circulation unknowns and AR200000 to approximate the 2D section;
finite-tip effects remain. It closes the browser-runtime gap for one refined
inclined periodic case. Broader frequencies/amplitudes/incidences, stall,
arbitrary-model timestep accuracy and native UA-2 reference provenance remain
unfinished. The earlier 160-step circulation failure remains recorded, and
neither UA family nor the full project is complete. The workbench/archive
checks from the [UA-2 follow-up](isae-ua2-archive-ui-20261102.md) remain separate.

Evidence: [machine report](isae-ua1-incidence-periodic-browser-20261102.json),
[plan and source pins](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/plan.json),
[full-history audit](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/audit.json),
[producer receipt](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/production-execution.json),
[audit receipt](../../artifacts/isae/ua1-incidence-periodic-browser-20261102-r1/audit-execution.json),
[runner](../../scripts/run-isae-ua1-periodic-browser-r1.mjs),
[audit](../../scripts/audit-isae-ua1-periodic-browser-r1.py).
