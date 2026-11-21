# Direct ISAE static-load workflow

The three archived ST-3 static files now run without changing their signed
Weight rows. This removes an input/workflow limitation in the
[ST-3 static study](isae-st3-static.md). It does **not** resolve that study’s
experimental discrepancies or constitute a full ISAE validation pass.

The subsequent [distributed static extension](distributed-static.md) also
supports signed `mg/Dmg` bench loads. This report retains its original run
hashes; three fresh native ST-3 controls and both offline browser tests are
recorded with that later implementation.

## Physical interpretation

The [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
defines Weight as mass times file gravity, acting at the end of a rigid pylon
attached to the beam. The ISAE static scripts use opposite signed Weight
entries to generate a force couple. In a zero-motion calculation, their forces
are exactly `Weight / g_file * gravity_body`, applied at the rotating pylon
endpoints. This preserves the nonlinear force and moment for every beam
rotation, including the reduction of moment as the wing twists.

OpenSwing permits those signed loading devices only through explicit static
support. Negative entries are not treated as physical inertia. Results flag
their algebraic mass bookkeeping, provide no physical center of gravity, and
omit the time-launch setup. Aerodynamic, modal and time-response calculations
still reject negative point masses. Distributed mass and point-inertia
validation remain unchanged. Positive-mass static states retain their normal
time-launch setup.

The upstream torque conversion remains visible: the archived scripts produce
an undeformed couple **1.3734 times the plotted torque**. The example files
retain their exact archived bytes and final loads. They are not corrected or
fitted to the measured data.

## Native verification

The [current-source replay](structural-static-workflow.json) contains **398
passing solves**: all 395 previous static states expressed directly as signed
Weight rows, plus the three unmodified archived files at 64 intervals. Every
nodal position/rotation, applied force/moment and support reaction is compared
with the earlier equivalent-load calculation.

| Quantity | Maximum absolute difference |
|---|---:|
| Node position, input L | 4.76e-12 |
| Node rotation matrix | 6.88e-12 |
| Applied force, input F | 8.89e-16 |
| Applied moment, input F·L | 1.33e-12 |
| Support force, input F | 1.34e-15 |
| Support moment, input F·L | 2.37e-11 |

The 19 focused tests also compare the literal files with the independent
continuous nonlinear rod, verify refinement at unchanged error bounds, check
large arbitrary rotations and reversed/zero gravity, and exercise physical
mass rejection and positive-mass time initialization. An additional 131
existing native checks pass, for **150 distinct passing native tests**. The
project/solution data checks add **13 passing JavaScript tests**.

Earlier failed test attempts are retained: test indexing/API/fixture mistakes,
a continuum check that required a finer mesh, and an obsolete assertion that
vacuum static calculations bypass the structured solver. The refined check
retains its original tolerance; no physical tolerance was relaxed. The
[source transition audit](structural-static-transition.json) limits production
kernel changes to seven functions in three modules; the other 94 modules and
the ASW parser are unchanged. Earlier studies keep their original source
hashes and are not relabeled as fresh runs.

## Browser workflow

Choose **Structural static · no airflow**, or open one of the three ST-3
static examples. Signed-Weight files select that analysis automatically and
open on the torsion distribution. The file’s gravity acts along body −z by
default; an explicit body-axis gravity vector can be entered, including zero.
Flight fields are hidden and excluded from the calculation. The output reports
residual, deflection, applied loads, reactions and force/moment balance. JSON,
section CSV and saved computed solutions retain the static result.

The initial desktop/mobile checks found that the default shell-strain plot
was unavailable because these files contain no shell coordinates. Their
default is now the available torsion distribution. **Both final offline
browser tests pass.** The desktop test compares every node of all three
64-interval literal cases with the native reference, checks zero gravity,
exports results, restores a saved computed solution without solving again,
and verifies rejection by aerodynamic analysis. The mobile test checks the
controls, computed plot, output and absence of horizontal overflow at
390 × 844 pixels. Both run actual Pyodide with the current 97-module kernel;
neither reports a browser JavaScript error. The
[browser record](structural-static-browser.json) retains full results and
source hashes; the [check summary](structural-static-checks.json) also records
the mobile result and retained failed attempts.

This mode does not enable aerodynamic trim, moving-frame inertia, controllers
or aerodynamic derivatives. Models containing engines still require a flight
condition and are rejected here. Signed static equilibria can seed another
static solve but cannot launch physical dynamics.

## Scope still open

The original experimental errors, primary/secondary source conflicts, fixture
and measurement uncertainties remain. The new workflow does not validate
other signed-weight models automatically: ST-5 literal networks need their
own rechecks, and unsupported joints/attachment stations remain. Ten of 41
ISAE families have partial quantitative comparisons; 31 lack them. All 40
broad ASWING requirements remain Partial.

## Reproduction

Use the repository’s Python environment and locally installed npm dependencies:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-structural-static-workflow.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_structural_static_workflow.py
node --test tests/projects.test.mjs tests/solutions.test.mjs
npm run build
npx playwright test tests/browser/structural-static.spec.js
```

The native replay needs the prior `isae-st3-static.json` reference record.
Its 398 raw results retain exact requests, module hashes and baseline keys.
The [pinned ISAE source](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865)
and original static report supply the experimental comparison; these direct
replays do not add new measurements.
