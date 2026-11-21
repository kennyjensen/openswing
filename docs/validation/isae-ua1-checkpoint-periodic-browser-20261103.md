# UA-1: complete checkpoint-corrected browser verification

Updated 2026-11-03. **The actual built browser worker passes all 13 gates** for
the four-cycle UA-1 repeated-stall supplement at 640 steps/cycle. The worker
starts from its own cold equilibrium with the full forcing table; Python states
are comparison targets and never initialize browser production.

The rigid rectangular wing has unit chord, aspect ratio 200,000 and four
circulation unknowns, representing the nearly two-dimensional airfoil limit.
This geometry and all aerodynamic parameters are identical in both runtimes.

All **2,560 steps converge with zero rejection**. The retained histories contain
**2,561 unique states and 319 audited restart boundaries**. Each request advances
eight steps with a 45-second request cap. Every result is checked against current
Python across **26 physical fields**, including
aerodynamic/frame outputs, local nodal motion, positions, rotations, internal
forces/moments and reactions. Endpoint and accepted BDF predecessors are checked
against each runtime's own raw history.

The largest scaled Python/browser difference is
**2.727023e-09**, below the unchanged **2e-8** limit.
Forces use qS, structural moments qS times span, and other fields use
max(1, absolute expected value), as frozen before production. The independent
zero-local-motion check also passes: maximum local acceleration is
**6.344242e-17 m/s²** against **2e-8**.

| Browser fourth-cycle waveform | Error versus independent reference |
|---|---:|
| Lift | 0.016880% |
| Circulation | 0.011519% |
| Circulation rate | 0.033317% |
| Pressure drag | 0.066288% |

Cold-history and settled waveform errors pass the **0.1%** requirement.
Settling, prescribed motion, mean lift, amplitude, phase, initial rate,
nonlinear residual and persistent stall gates pass. The independent DOP853 and
Radau reference solutions retain their previously verified source/input hashes.

The [complete Python study](isae-ua1-checkpoint-periodic-20261103.md) supplies
the 320/640 temporal-refinement evidence. Comparing browser fine-grid errors
with Python coarse-grid errors is explicitly a mixed-runtime consistency check;
it is **not** a separate two-grid browser-order claim. No physical equations,
tolerances, runtime bytes or acceptance limits changed during either study.
All 136 solver module hashes loaded by the worker match the tested source.

This is one supplemental equation-based case: mean incidence 9°, k=0.94,
peak-to-peak A/c=0.5 and declared section limits ±1.5. It is not native ASWING
output or general dynamic-stall validation. The published UA-1 harmonic
benchmark remains 148/148 on these identical solver bytes. This adds one
complete stalled-browser comparison; it does not establish whole-family,
native-ASWING or full-history workbench/UI validation.

UA-2's native comparison provenance and its broader current-source time/mesh/
browser validation remain open. The full ASWING replacement is incomplete.

Evidence: [raw-history audit](../../artifacts/isae/ua1-stall-chart-browser-20261103/audit.json),
[summary and hashes](isae-ua1-checkpoint-periodic-browser-20261103.json), and the linked Python study.
