# UA checkpoint displacement precision

Updated 2026-11-03. The checkpoint correction passes **24 focused production tests** and **3/3 expanded Python/browser checks**. Complete current-source periodic validation remains unfinished.

## Failure found by the complete-study attempt

The new UA-1 four-cycle study used the corrected arc quadrature, unchanged 320/640-step grids, 20-step serial Python jobs and the existing independent equation reference. It completed 46 coarse-grid segments (920 audited steps) before segment 47 failed the independent rigid-motion check. That segment returned all 20 steps without rejection, but its first step had spanwise local acceleration **3.75613e-8 m/s²**, above the unchanged **2e-8** limit. The study is retained as failed; the fine grid and browser periodic study did not run.

Absolute positions discarded about **1.04e-12 m** of displacement on this 200,000-aspect-ratio airfoil-limit mesh. BDF differentiation amplified the loss after checkpoint restoration. An unchanged-production capture reproduced the original endpoint and predecessor exactly. Retaining its displacement coordinates in a separate diagnostic reduced the next-step acceleration to **5.97021e-15 m/s²**. Force, moment, circulation and circulation-rate outputs were identical between those two eight-step probes.

## Production correction and verification

`openswing/time_state.py` now writes an optional `position_chart` in each time state: scheme `jig-relative-translation-v1`, physical origin, positive length scale and translation coordinates. Its reconstructed absolute positions must exactly match the saved physical positions. The decoder retains exact coordinates on the same mesh and translates origins before scaling on an identity-compatible reconstructed mesh. Malformed, nonfinite or inconsistent charts are rejected. Older checkpoints remain readable, but missing displacement information cannot be recovered retroactively.

The physical equations, nonlinear tolerances, timestep and acceptance limits are unchanged. All 135 other solver modules remain unchanged. Tests cover sub-ULP translation/BDF preservation, compatible origin changes, invalid charts, legacy decoding, elastic checkpoint continuation, variable-step BDF recurrence, source-coordinate accepted history and Radau continuation. One combined test job hit its 45-second cap after ten passing tests; smaller jobs completed all 24 checks.

| Paired Python/browser check | Steps per runtime | Maximum scaled difference |
|---|---:|---:|
| seed | 20 | 7.15422e-15 |
| continue | 8 | 5.67696e-15 |
| cold-UA1 | 8 | 1.70086e-12 |

The browser continuation uses its own new checkpoint. The seed starts from the retained legacy checkpoint, while the cold case starts from its own equilibrium. All 36 steps per runtime converge without rejection. Every compared state includes aerodynamic/frame fields, local nodal kinematics, positions/rotations, internal loads and reactions. The original 2e-8 runtime and rigid-motion limits pass. Accepted BDF endpoints and both predecessors are checked against raw output. Browser-loaded hashes match all 136 current solver modules.

## What remains for UA validation

The published UA-1 harmonic target already passes 148/148 checks; the source target is a theoretical formula, not native executable output. The original harmonic comparison and supplemental nonlinear/stall studies should remain distinct. Complete current-source periodic histories, refinement, settling and browser stalled continuation still need verification after this correction. No registered full-case count changes here.

UA-2 retains its historical attached-flow time/mesh/browser passes. Current-source full-period revalidation and broader operating conditions remain open; stall is supplemental unfinished coverage. Its 222 native comparisons remain unverified because the archived curves match corrected 2D formulas and their native 3D generating setup is unresolved. Equation verification alone does not establish native ASWING agreement.

[Failed full-study evidence](../../artifacts/isae/ua1-stall-corrected-20261103/plan.json). [Diagnostic evidence](../../artifacts/isae/ua1-checkpoint-displacement-20261103/diagnostic-summary.json). [Correction evidence](../../artifacts/isae/ua1-checkpoint-chart-20261103/summary.json).
