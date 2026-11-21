# Corrected-kernel unloaded-wing verification

This directory preserves the completed fresh run after the own-bound axis-flow correction. It contains three newly computed native grids (requested N8/N16/N32), twelve independent reference cases, the exact bounded plan, source pins, foreground wrapper, terminal state, logs, comparisons and hashes. It does not overwrite the historical unloaded studies.

The executed main CLI used `--native compute`; the plan contains no saved-native inputs. All 63 necessary dependency files stayed unchanged during the run: 58 kernel modules, the study/reference/native scripts, the structural source helper, and the shared material table. The pinned `aero.py` SHA256 is `17d3c4ee8671ca0627f07af7ada8504855c30fba09615df545572d31cdfab5e3`. Both scientific child and foreground wrapper exited 0 after 131.44 seconds.

All three native physical result payloads and all twelve independent reference results equal their historical counterparts exactly. This establishes fresh provenance for the corrected kernel in the unloaded, zero-circulation condition. It does not establish loaded-state behavior or experimental flutter agreement. Each native grid contains two local 24-root searches; those searches leave the complete native finite spectrum unclassified. The independent study retains all 2728 computed roots across the twelve cases, including the coarse-grid growing conjugate pairs recorded in `completion-summary.json`.

The physical settings and tolerances are unchanged: wing25 analogue, 24 m/s, uniform requested panels with required material breaks, density 1.225, PG Mach zero, zero incidence/camber/Cm/gravity, stall disabled, lag enabled, and all independent mechanical coordinates. The native tangent step is 1e-5 and both left/right original-pencil residuals must be below 1e-9. No saved result substitutes for a native calculation in this run.

## Portable reproduction

From the repository root, choose a fresh output directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-durrant-unloaded.py --plan docs/validation/durrant-unloaded-current/plan.json --output /tmp/durrant-unloaded-current-new --native compute --kernel-root "$PWD"
```

A compatible interrupted or completed run can be resumed using the same command and output directory with `--resume`. Resume validates the exact plan, selected cases, source/kernel hashes, saved artifact hashes and process identity. A live owner is rejected. It reuses completed current-format records inside that run.

`--native saved` currently validates the original prototype-format native archive and its terminal evidence. The current compute-format native records in `results/` are not interchangeable with that older external-input schema. Use `--native compute` for a fresh study, or guarded `--resume` for current-format records; do not relabel these records as legacy inputs.

## Evidence

- `results/run.json` pins all twelve reference records and three freshly computed native records.
- `source-pins.json`, `plan.json`, `state.json`, `study.log`, and `run_current.py` preserve the exact dependencies, inputs, executed command, process identities and foreground outcome. Absolute paths in these historical records describe the executed workspace; the command above is the portable entry point.
- `completion-summary.json` compares the current physical payloads with the retained historical evidence, preserving full-spectrum growth counts and low-mode matches.
- `completion-manifest.json` pins the original completed run package. `copy-manifest.json` verifies every original file was copied here exactly; this README is additional handoff documentation.

The terminal `state.json` status is `completed`; its `phase` field is the last periodic progress snapshot. `results/run.json` records the final `finished` phase. These records do not constitute a completed browser workflow: the historical baseline browser attempt was incomplete, and the corrected-kernel browser fixture is prepared separately.
