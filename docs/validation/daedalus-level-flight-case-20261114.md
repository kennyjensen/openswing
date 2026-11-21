# Checked Daedalus level-flight case in the app

The **Load checked level-flight case** button appears below the example selector
when Daedalus is loaded. It restores the literal public `dae.asw`, the new
regular per-component mesh, and the accepted 6.7 m/s level-flight equilibrium
from the [redistributed mesh study](daedalus-regular-mesh-20261114.md).
The button selects free-flight Bode response with 41 logarithmic samples from
0.1 to 10 Hz. Click **Run analysis**, then select **control.3 → Flight frame →
Yaw angular velocity Ω_z**. The frequency settings store angular frequency, 0.6283185 to
62.8318531 rad/s. Refresh the page after an ongoing calculation finishes to
load the updated interface; development automatic reloads remain disabled.

The [downloadable project](../../public/examples/dae-level-flight-project.json)
contains two editable cases: Bode response and steady trim. The Bode case has
no operating trim targets and uses the free aircraft force/moment conditions.
The steady case retains the original seven trim targets. Both include the
same unchanged saved equilibrium and its numerical identity, using SEGSPL
and the source moving-airflow operator. No frequency solutions are bundled.
The ordinary `.asw` import still starts with its ordinary operating settings;
the new mesh alone does not establish level flight.

The [publisher](../../scripts/publish-daedalus-level-flight.py) copies the
accepted state verbatim, sets editable fields from its solved condition, and
publishes identical copies in `examples/` and `public/examples/`. It preserves
the comparison's live-influence setting, Mach 0.1, aerodynamic lag and engine
plume. This is our declared comparison condition, not an identification of
Drela's original operating point. The yaw dip discrepancy remains open.

The [bounded replay](../../artifacts/daedalus-level-flight-case-20261114/replay-regular-mesh/result.json)
independently reconstructs the physical flight condition from the exported UI
fields and verifies equality with the saved trim condition. Both cases restore
with their original identity; both have 103 nodes, 98 intervals and 81
circulation values. Their maximum steady residual is **4.67953e-10**. The
released 1,953-state dynamic base has the same residual, a flight path of
**2.12e-11°**, and weight **232.5336 lb**. The current-export replay used
2.19 CPU seconds, 4.74 wall seconds and 93,664 KiB peak RSS, completed within
its limits, and was reaped. It also checks control, engine and lifting-beam
identities against the parsed `.asw`.

The [JavaScript checks](../../artifacts/daedalus-level-flight-case-20261114/javascript-checks.json)
evaluate the actual project/saved-state/numerical-policy validators in an
isolated V8 runtime. Both cases pass and the project round trip is exact.
The actual button handler loads the Bode configuration in the success branch
and rejects changed inputs, a failed download and a missing case. The main
module also passes a syntax check. These checks do not establish a complete
DOM import or browser solve; browser, build and WASM tests remain held under
the [UserLAnd interruption](userland-test-interruption-20261108.md).

A subsequent settings-schema check found an export defect that the generic
project validator could not detect: the publisher wrote `body-added-mass` as
`"1.0"`, but the HTML select accepts the exact string `"1"`. Both cases were
therefore rejected by `validateSettings` before import. The publisher now
writes the accepted dropdown value; the numerical factor remains 1.
The [before](../../artifacts/daedalus-level-flight-case-20261114/settings-before-fix.json)
and [after](../../artifacts/daedalus-level-flight-case-20261114/settings-after-fix.json)
receipts retain that distinction. Earlier generic-validator passes did not
prove successful app import.

The current check evaluates the actual settings templates, parses their fields
and dropdown options, then runs the actual `validateSettings` over both cases:
all **171 settings** pass, including six supported migration fields. The two
operating-point controls are represented from their constructor; model control
identities are independently checked by the native replay. The actual Bode
options function produces **41 logarithmic frequencies from 0.1 to 10 Hz**,
`control.2`, `control.3` and `power.1`, with a free frame. Both source-airflow
request gates accept the setup. The new
[regression tests](../../tests/daedalus-project.test.mjs) pass **42 assertions**
when evaluated in isolated V8; Node itself was not run. The
[current verification](../../artifacts/daedalus-level-flight-case-20261114/verification-select-fix.json)
checks the served project bytes and unchanged physical state. These checks
still do not exercise full DOM events, responsive rendering, WASM or a full
41-point browser solve.

A subsequent user run reached **Run analysis**, but browser field validation
rejected the loaded trim. Generated flap controls used `step="1"`, so the
fractional values F2 = -8.825752955534778 and F3 = 0.014960713339472114
were invalid number inputs. They now use `step="any"`, preserving the exact
saved settings. Validation errors also identify the field and include the
browser's reason rather than reporting only a generic operating-condition error.
The [regression receipt](../../artifacts/daedalus-level-flight-case-20261114/fractional-control-checks.json)
records four test bodies / 92 assertions passing in isolated V8. The control
test executes the actual input-construction code with a small DOM stub and
simulated number-step validation, for both published cases and both initial
and retained settings. Restoring the old whole-number step makes it fail at
Flap 2. The existing development server serves the fix. This is still not a
full browser load-and-solve check; the earlier settings-schema checks did not
exercise browser numeric validity.

The follow-up [request-path tests](../../tests/daedalus-request.test.mjs)
execute the actual settings restore, saved-equilibrium widget, Bode options and
Run analysis function with a small DOM stub and intercepted worker request.
All three test bodies pass (**77 assertions including module setup**). The
[captured request](../../artifacts/daedalus-level-flight-case-20261114/app-bode-request.json)
preserves the full 103-node saved equilibrium, source equations, mesh, trim
controls and physical condition. It requests control.2, control.3 and power.1,
free flight and 41 logarithmic frequencies, including exactly 1 Hz within
floating-point precision. Disabling the seed explicitly removes it; empty
airspeed stops before any request. The
[receipt](../../artifacts/daedalus-level-flight-case-20261114/app-request-checks.json)
pins all 45 input files. This stub covers selected active numeric fields, not
all main-module events or browser visibility and constraint behavior.

The [native boundary check](../../scripts/check_daedalus_app_request.py) then
passes that captured JSON through the production dispatcher, policy validator,
ASW parser, mesh normalization and FlightCondition conversion. It intercepts
the retained-frequency solver at its entry, before constructing matrices.
The [accepted result](../../artifacts/daedalus-level-flight-case-20261114/app-request-bridge-v2/result.json)
confirms the same seed, physical condition, mesh and free-flight response setup.
The first check rejected a representation difference: the app writes zero
circulation-mode counts explicitly, while the saved trim omits them. The
production CirculationBasis treats both as pointwise circulation; the revised
checker validates their beam keys and compares their nonzero modes. Both
observations are retained, and no production settings were changed to pass.
The successful native check used 2.014 CPU seconds, 5.684 wall seconds and
84,768 KiB peak RSS; it completed within its limits and was reaped. These
checks establish request transport, not browser solve completion or agreement
with Drela's plotted response.

No physical equations, ISAE fractions or comparison scopes changed. Existing
packaged application downloads were not rebuilt.
