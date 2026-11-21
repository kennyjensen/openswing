# ST-1 source readiness, 2026-10-27

No literal ST-1 input is executable with the current parser. This review adds exact driver/output accounting and identifies a small position-only candidate beyond the [earlier input audit](../isae-st1-input-audit.md). It does not repeat the parses or claim historical parser compatibility.

All **89 original files, 10 models, 14 drivers and 61 output candidates** remain visible and pinned in [report.json](report.json). The native exports contain **197 scalar targets**: 15 position rows (45 components) and 76 complex eigenvalue rows (152 real/imaginary components). All 25 real-only roots remain included. These counts exclude additional script arrays and undecoded plots; they are not a whole-family denominator. No jobs or slots are registered.

The smallest candidate is `Static_deflection/[45_0]_3a.asw` with its same-name shell driver and text export. It is the only model with neither an unfinished Engine block nor surplus scaling fields. The original clamp is at t=+0.28, mass 0.4kg at−0.28, and sensor at−0.22: 0.5m from the clamp, consistent with the report's static measurement station. Distributed weight is zero; original twist varies from 110° to 45°. The final `Post_analysis.m` loop (lines 607–620) applies mass 0.4 and twist adder 0, matching the retained state. The generator changes only the mass and twist-transform lines. This supports a declared final-state comparison; a run transcript proving source bytes at generation is absent.

The retained target row is:

| Body-relative position | Native token | Half-last-place |
|---|---:|---:|
| rx | `-0.129671` | 0.0000005m |
| ry | `-0.189497` | 0.0000005m |
| rz | `-0.949139E-01` | 0.00000005m |

These lowercase rx/ry/rz outputs are the beam-anchor position in aircraft axes. They are not sensor-frame components, Earth/GPS coordinates or baseline-subtracted deflections. The original shell selects 28–30; present guide selector numbers differ, so the saved headers carry the mapping. The postprocessing plots separately subtract the unloaded value and take absolute values; those transformations must not be applied to the native target row.

Primary unsteady theory §10.2 (p19, local text lines 1009–1018) samples position at the attachment independently of sensor axes. Equations 95–97 (p20) define pylon geometry from the undeformed offset and beam rotation; equation 98 defines the separate sensor triad. Equations 115–116 (p22) likewise make GPS position/velocity independent of sensor orientation. A scoped position-output capability could therefore defer an undefined triad without inventing axes. Current `validate_sensors`, `measure_sensor` and attachment rendering build the triad eagerly, so this capability does not exist yet. Any extension needs independent review and tests, preserving source records and rejecting or marking unavailable all dependent attitude, flow, sensor-frame and feedback uses.

That distinction does not cure the remaining literal-input issues. All ten models supply parallel sensor vectors. Nine have an empty trailing Engine header without End; four have 16 multipliers for 15 columns. The guide prescribes terminated blocks and named data columns, but supplies no rule establishing the intended surplus-field deletion or implicit EOF termination. Five modal Weight records are physically zero and already attach at valid endpoints; current null-point support addresses none of these blockers. The five active tip masses cannot be discarded. The modal `[45_0]_s` additionally has a negative literal distributed-mass multiplier and no same-name retained driver/native export; no sign correction is justified.

| Native scope | Files | Rows | Scalar targets | Command-path evidence |
|---|---:|---:|---:|---|
| Mesh sensor positions | 7 | 7 | 21 | One exact model/driver, I4 through I256 |
| Mesh eigenvalues | 7 | 54 | 108 | Same sequential driver; retain every root |
| Modal eigenvalues | 4 | 16 | 32 | Four exact same-name shell writes |
| Modal shared sensor.txt | 1 | 1 | 3 | Overwritten by four different drivers |
| Static command-named positions | 4 | 4 | 12 | Three same-name exports plus beam.txt |
| Other static position exports | 3 | 3 | 9 | No retained matching write command |
| Static eigenvalue export | 1 | 6 | 12 | No retained generating modal command |
| **Total** | **27** | **91** | **197** | **22 single-writer files / 173 scalars; five shared or unpaired files / 24 scalars** |

The static `[0_90]_3s.sh` writes `beam.txt`, not `[0_90]_3s.txt`; the `.txt` and `.csv` are identical bytes, while `.temp` differs. These copies remain separately visible. The modal postprocessor's hardcoded `[0_90]_3s` values differ from its retained native eigenvalue export and cannot replace it. Mesh drivers do not invoke the MODE F vacuum toggle, whereas the four modal drivers do; startup/toggle state is not fully recovered. Dropping real-only roots or treating all exports as conservative vacuum frequencies would hide this boundary.

All nine static sweep groups remain visible in the producer, with 14 experimental CSV candidates and 20 plot candidates retained separately. Their plots are not decoded into new targets here. Report text describes 40 cosine-clustered nodes, while the retained static shell requests I100; original command and reconstruction grid must remain explicit. The actual historical build, autoload state, airflow/pose/gravity direction and nonlinear continuation are still unknown. An initial static structural comparison must declare current assumptions and preserve any differences.

The supplemental `3 - Structure/Mesh_convergence_analysis` tree contains 19 files, all byte-identical to the family mesh tree, including its one model and 14 native exports. Those 129 duplicated scalar values do not add independent reference evidence or repair the input. Both original locations remain pinned.

The next bounded step is independent review of the position-only sensor capability, followed—if supported—by the unchanged `[45_0]_3a` snapshot with all three native outputs. No End insertion, sensor relocation, default-axis substitution, scaler truncation, tuning or output deletion is warranted. The other nine variants and every candidate remain separate work.

This review used source reads and standard-library token/count/hash checks only: **zero parser imports, parses, meshes, residuals, solves, matrix assemblies, tests or upstream script executions**. Original model hashes match the prior audit; all 89 original files match the frozen archive manifest. Existing backlog and registry are unchanged.
