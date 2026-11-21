# Everyday workbench update

The user redirected work to app usability. This is not a new claim of general
ASWING validation or a resolution of the unknown Daedalus operating point.

The app retains its desktop result tabs and mobile Editor, Settings, Plots and
Output tabs. Only the three aircraft in `public/examples/drela-sources.json`
remain in the example menu. Daedalus loads by default, using its existing regular
mesh. The starting speed is 21.981627296587927 ft/s (6.7 m/s), displayed with ft/s
units; this is an editable starting condition, not a claim about Drela's plot.
New sessions select steady aeroelastic equilibrium and ASWING structure + airflow.
Saved projects keep their recorded equations and inputs.

Removed product UI: validation/progress/comparison links, the validation/scope
dialog, synthetic and ISAE example entries, and Daedalus/SA-12/ST-5 validation
setup buttons. The underlying cases, reference evidence and comparison pages are
retained in the repository. Secondary solver/control choices are collapsed and
visible descriptions shortened.

`web/steady-flight.js` adds a generic trim action. It builds ordinary operating
constraints from the loaded aircraft and selected control assignments. Powered
level flight solves alpha, bank, thrust, roll control (or sideslip), pitch/yaw
controls and elevation for zero net forces/moments and zero flight-path angle.
Without a roll actuator, sideslip balances roll. With a roll actuator, sideslip
is fixed at zero. Unpowered glide instead solves elevation from longitudinal
force balance, with all engine settings zero, and imposes no level-flight target.
All frame rates and accelerations are zero. Feedback is disabled for this preset.
The aircraft source, mesh, speed, atmosphere and aerodynamic settings are retained.
No saved validation equilibrium is loaded to substitute for a solve.

On success, exact solved values populate the flight/control inputs. Trim targets
are then released and the equilibrium retained for free-flight response analysis.
Failed/cancelled calculations do not show a trim success or adopt a state.
Custom models can change the control assignments under Trim controls; the
defaults follow the supplied aircraft's F1/F2/F3 convention where available.

Verification used isolated V8, without starting Node, a browser, Vite or WASM:

- `tests/steady-flight.test.mjs`: 7 test bodies, 60 assertions, including matching
  the established seven Daedalus trim targets, glide setup, rejected inputs,
  success/failure actions, exact fractional values and target release.
- `tests/daedalus-project.test.mjs`: 4 bodies, 92 assertions.
- `tests/daedalus-request.test.mjs`: 3 bodies, 77 assertions.
- Main JavaScript syntax passes. The evaluated main template and actual trim
  panel have balanced tags and 227 unique IDs (other imported panels omitted
  from this static nesting check).
- Read-only HTTP requests to the existing development server return both
  updated modules. Full browser rendering and a cold trim solve were not run;
  these checks do not establish trim convergence for every aircraft/speed.

The unfinished source-geometry derivative prototype was unwired and moved to
`artifacts/source-geometry-tangent-20261114/prototype/`. All 143 production Python
modules match the pre-prototype source pins. Its last bounded diagnostic ended
successfully and was reaped. No solver job remains from that study. ISAE
completion fractions and progress scopes are unchanged. Packaged ZIP downloads
were not rebuilt; manually refresh the running development app.
## Fresh-aircraft target cleanup 2026-11-15

The latest UI follow-up found that fresh file/example imports cleared the old
equilibrium but retained its operating constraints. `fillVariables` deliberately
retains missing variables marked "not in model", so a constraint could still
name a flap, engine or sensor from the previous aircraft. Custom equations and
control-allocation costs also remained associated with those rows.

The fresh-import branch of `inspect` now removes the rows and refreshes the
allocation/custom-equation controls. File selection, example selection and
file drop all use this branch. Mesh/property edits, ordinary ASW editing and
saved-case restoration use the existing non-fresh branch; their targets are
preserved or restored explicitly. The older turn-preset help text no longer
directs users to an example removed from the selector.

The existing import regression now starts with a sensor-based custom target and
checks removal with and without a default mesh, including allocation/custom
refresh. It checks that the non-fresh path preserves targets. Eleven
steady-flight test bodies / 99 assertions and six trim-to-response request
bodies / 166 assertions pass in isolated V8 with lightweight DOM fixtures.
Main-module syntax passes. Evidence:
`artifacts/aircraft-import-targets-20261115/checks.json`.

No browser, Node, build, solver or background job was started. No physics or
ISAE status changed. The previous goal turn made concrete progress on startup
and solved-condition metadata; this turn continues the user's app-usability
priority. Full browser verification and full ASWING parity remain unproven.

## Loading and field navigation 2026-11-15

Inspection of the normal Run analysis path found that inactive settings already
have a visibility filter. The remaining navigation problem was nested
disclosures: only the innermost `details` opened when validation failed, leaving
the field hidden if an enclosing disclosure was closed. The handler now opens
every enclosing disclosure before focusing the input and reporting validity.
The request validation rules are unchanged.

Example selection previously awaited each download independently before calling
`inspect`. An older slow response could therefore become a newer inspection and
replace the user's more recent choice. `web/aircraft-loader.js` now shares a
selection sequence across example downloads, file-picker reads and dropped
files. Superseded reads never enter inspection, and their failures do not
replace current status. A current read or inspection rejection is handled; a
later selection can recover. The existing inspection guard still owns ordering
after parsing starts. File-picker input is cleared before awaiting its read, so
an old completion cannot clear a later selection.

Six loader checks / 21 assertions pass, including execution of the actual three
main.js import handlers with deliberately out-of-order reads. Seven request
checks / 179 assertions pass, including nested disclosure opening before focus
and validity reporting, plus the existing completed-trim handoff. Isolated
negative checks fail when the loader's stale-read guard or the enclosing-panel
loop is removed. Main syntax passes. Existing-server HTTP checks return 200 and
the updated code for both modules. Evidence is in
`artifacts/loading-validation-20261115/`.

Verification used isolated V8 and lightweight DOM fixtures. No Node, browser,
build, solver or background job was started. Full browser verification remains
pending under the UserLAnd hold. No physics or ISAE status changed. The prior
goal turn made concrete progress by clearing stale aircraft targets; this turn
continues the requested app-usability work.
