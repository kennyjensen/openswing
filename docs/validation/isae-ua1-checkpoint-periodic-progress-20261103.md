# UA-1: current-source harmonic and checkpoint revalidation

Updated 2026-11-03. Small serial jobs, one BLAS thread. No production equations,
solver tolerances or acceptance limits changed in this study.

**The published UA-1 harmonic benchmark passes 148/148 on the current solver.**
Both four- and eight-unknown meshes were recomputed with the original strict
tolerances. Maximum relative amplitude error is **0.0016521%** and
maximum phase error is **0.0006092 degrees**. The suite runner exits 1 because
the full catalog remains incomplete; both selected numerical jobs completed
successfully. This is agreement with the published equation, not native output.

The supplemental repeated-stall study now completes **four coarse-grid cycles**
at 320 steps/cycle: **1,280 accepted steps, 1,281 unique states, zero rejected
steps and 63 checked restart boundaries**. Each current state and accepted BDF
predecessor retains displacement coordinates that exactly reconstruct its
physical positions. Expanded checks include local motion and structural loads.
The largest local acceleration is **1.883136e-17 m/s²**
against the unchanged **2e-8** limit.

The previous run failed at step 921 with **3.756128674e-8 m/s²** spanwise
acceleration. At the same step of this fresh cold-start history, the corrected
value is **2.089927e-33 m/s²**. No old production checkpoint seeds the new run.
The independent DOP853/Radau reference solutions are reused with verified hashes.

| Fourth-cycle coarse waveform | Error versus independent reference |
|---|---:|
| Lift | 0.064649% |
| Circulation | 0.040246% |
| Circulation rate | 0.121000% |
| Pressure drag | 0.256364% |

**This is not a new complete periodic-case pass.** Circulation-rate and pressure
drag errors still exceed the 0.1% fine-result requirement on this coarse grid.
The frozen 640-step/cycle run, temporal refinement checks and complete built
browser comparison remain pending. All four third-to-fourth-cycle changes are
below **0.0000182%**, but settling alone
does not establish timestep accuracy. Supplemental stall limits are ±1.5;
these are declared test settings, not recovered native UA-1 inputs.

UA-2 is unchanged: its 222 native comparison slots remain unverified because
the saved curves reproduce corrected 2D formulas and native 3D provenance is
unresolved. Broader current-source UA-2 time/mesh/browser validation is pending.
No registered case counts change and the full project remains incomplete.

Evidence: [harmonic run](../../artifacts/isae/ua1-harmonic-chart-20261103/report.json),
[coarse study](../../artifacts/isae/ua1-stall-chart-periodic-20261103/progress-n320.json),
and [source/input hashes](isae-ua1-checkpoint-periodic-progress-20261103.json).

Resume the already frozen study with
`scripts/run-isae-ua1-stall-chart-periodic.py run --max-jobs 64` using the
project Python environment and the existing single-thread environment variables.
Two such bounded batches cover the remaining 128 serial fine-grid jobs.
Do not prepare a new study or rerun the completed coarse grid.
