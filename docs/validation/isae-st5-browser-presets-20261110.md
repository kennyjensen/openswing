# ST-5 comparison setups in the workbench

All **16 original ST-5 static cases** are now included in the example picker:
four rigid cosine loads, four literal type-2 rollers, four forward-only
cosine/elliptical loads and four rigid elliptical loads. The new **Apply ST-5
comparison setup** action selects the inputs used by the current mechanics
comparison. It does not run a solve.

The original picker exposed only three rigid cosine cases. Selecting a model
did not select its reviewed structural equations or archived station grid.
The validated studies explicitly use `drela-segspl-v1` interpolation,
`drela-steady-section-v1` structural equations and the archived station grid.
The new action makes that choice visible and reproducible. General numerical
defaults and existing saved projects retain their prior behavior.

## Using a comparison setup

1. Choose an ST-5 case under **Example configuration → ISAE static validation**.
2. Click **Apply ST-5 comparison setup** below the example selector.
3. Review **Structural static**, **ASWING static · general sections**, file
   gravity and the node grid, then click **Run analysis**.

Joined-wing cases have **38 forward-wing and 32 rear-wing intervals**;
forward-only cases have **38 intervals**. These are the archived-station grids,
with independently known anchors retained exactly. The completed five-grid
convergence study remains separate; this button does not reproduce that full
study or authenticate the original automatic node generator.

The action replaces the mesh, selects bilateral struts and clears operating
constraints, derivative requests, feedback and loaded equilibrium. It leaves
the original `.asw` source unchanged. Source identity is checked before applying
the setup; edited or renamed source is rejected. Inputs captured before that
asynchronous check must still match the workspace before loading. The existing
case loader handles validation and rollback. The comparison equations and
station grid are applied only when this action is chosen.

The roller examples retain the literal public ASWING type-2 law. Their note
distinguishes this from the report's modified in-plane link. None of the
original joint rows, loads, stiffnesses, comments or reference values was edited.

## Verification and limits

The [data audit](../../artifacts/isae/st5-browser-presets-20261110/verified-data.json)
checks all **34 generated files**, exact upstream source hashes, pinned
comparison plans and targets, archived stations/anchors, parsed beam domains
and the literal roller rows. All sixteen saved current results use the
specified section policy and pass their recorded physical gates. All **141
production Python modules** remain unchanged. This is saved-evidence validation,
not a new solve or a browser replay.

**Browser integration, Node tests and builds remain unverified** under the
existing [UserLAnd test hold](userland-test-interruption-20261108.md). Eighteen
JavaScript checks are written for exact setup, saved-project compatibility,
source rejection and asynchronous input capture, but have not been run.
The picker/action wiring was reviewed in source only. The previously checked
downloadable build has not been regenerated. No solver, Node, browser or build
job was launched for this change.

ST-5's primary score remains **16,687/16,688**. The remaining force discrepancy,
modified-link interpretation, original node generation, reaction display and
unavailable modal evidence retain their existing qualifications. UI presets
add no validation observations or passes.

## Sources and maintenance

The [source manifest](isae-st5-browser-presets-sources.json) records each original
model, SHA-256, matching upstream paths and reviewed plan/target. The
[authoritative reference index](aswing-authoritative-references.md), Jan Part III
§4.5 and the [current mechanics scope](isae-st5-mechanics-current-20261110.md)
remain the scientific basis. The generated module contains inputs only, with no
saved predictions or alternative model fitting.

```sh
.venv/bin/python scripts/prepare_st5_browser_presets.py --check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/check_st5_browser_presets.py --output NEW_AUDIT.json
```

The first command is read-only. Without `--check`, it regenerates metadata and
adds missing example copies; it refuses to overwrite changed `.asw` files.
The second command performs only source parsing and saved-evidence checks,
with 512 MiB address space, 15 CPU seconds and 25 wall seconds as hard caps.
The existing build preparation copies `examples/` into `public/examples/`;
both copies are already synchronized here without invoking that build.
