# OpenSwing

An independent, MIT-licensed implementation of the published ASWING formulation,
with a browser workbench. **Development is ongoing; this is not yet a complete
ASWING replacement.** The intended end state remains full documented ASWING
functionality, `.asw` compatibility, and a JavaScript/WebAssembly web application
that runs locally in the browser. The JavaScript UI and worker use a self-hosted
Pyodide WebAssembly runtime for the numerical kernel; no server executes analyses.

For a prebuilt installation, use **Local app** and follow [Run locally](#run-locally).
It includes the runtime, source code, tests, examples and validation summaries.
Large raw experiment archives are a separate optional download under
**Validation & scope**. See `VALIDATION-ARCHIVES.txt` in the source ZIP and the
[archive catalog](docs/validation/archive-index.json) for paths and checksums.
Extract the optional archive beside the source ZIP to restore the raw files.
Source-only checkouts build and run without them; reproducing an individual
archived study may require its raw files.

Repository copies can store large validation records as checksummed gzip parts
under `docs/validation/.source-data` to fit source-hosting limits. Run
`python3 scripts/restore-validation-data.py` before inspecting those reports or
running tests; `npm run build` does this automatically. Restoration preserves
every original byte. The source ZIP already contains the restored records and
omits the redundant compressed parts; its restore step has nothing to do.

The timing observations below describe individual historical studies. See the
[current status](docs/STATUS.md) for the latest implementation and remaining work.

The [authoritative ASWING reference library](docs/validation/aswing-authoritative-references.md)
provides local PDFs of all four ISAE validation reports, related documentation,
and versioned source records. Downloads are in the visible `reference/` folder.

Current validation targets [tested ASWING results](docs/validation/isae-aswing-reference-status.md),
with experimental agreement optional. The [SA-3 arc correction](docs/validation/isae-sa3-accurate-arc.md)
fixes inaccurate material lengths near a curved tip and preserves old saved cases.
The 66-case rerun converges, but its archived drag discrepancy remains.

The [Daedalus four-output comparison](docs/validation/daedalus-rudder-four-outputs.md)
shows the remaining yaw, roll, sideslip and bank discrepancies against Drela's
drawing. Saved output recovery and an independent aircraft/elastic inertia audit
pass; the full reference match is still unresolved.

The [elastic boom–fin check](docs/validation/elastic-fin-feedback.md) verifies
distributed bending/twist with live aerodynamic feedback at 1 Hz. All 26 fine-mesh
response criteria pass, with a worst grouped complex error of 0.3601%. A portable
native regression and an independent reference generator pass. The full Daedalus
Bode discrepancy remains unresolved.

The [free-frame/hinged-fin check](docs/validation/coupled-fin-response.md) adds
twelve independent coupled-response comparisons and two passing regressions.
The requested log–log display is complete; the Daedalus rudder-to-yaw discrepancy
remains unresolved. These component results do not establish aircraft parity.

The [current ISAE suite](docs/validation/isae-suite.md) and
[family backlog](docs/validation/isae-suite-backlog.md) account for all **41
families and 279 original models**. Comprehensive comparisons with archived
ASWING results are the current development priority. The latest import inventory
accepts 212 models and records 67 errors. Every family remains visible, including
unimplemented comparisons, unavailable settings and failed solves; no whole
family is yet validated. The latest coverage expansions add every
[AP-2 propeller-position grid point](docs/validation/isae-suite-ap2-20261027.md)
and both complete [AE-1 sensor sweeps](docs/validation/isae-suite-ae1-20261027.md).
The default plan now contains 4,029 jobs across selected scopes in 25 families;
16 families lack adapters, including cases with no archived ASWING output.
The [full AE-3 native comparison](docs/validation/isae-ae3-frozen-influences-20261111.md)
computes coefficients, derivatives, mass properties and normalized rates at all
six archived operating points. At 5% tolerance, 434/725 comparisons pass:
178 computed values disagree and 113 embedded values lack resolved inputs.
The [adapter guide](docs/validation/isae-ae3-adapter.md) describes its scope and
the bounded, one-job-at-a-time replay.
The [ST-1 expansion](docs/validation/isae-suite-st1-20261027.md) retains all 197 native scalars and ten original models: two static jobs compute six positions, with two printed-precision matches, while 194 other scalar slots remain blocked. Neither complete position state matches.
Run `npm run test:isae:plan` to inspect registered
comparisons, or `npm run test:isae` to execute them. Reference-output acceptance
currently allows **5% relative error**, retaining the original absolute tolerance
when it is larger. Zero and tiny references (magnitude at most `1e-8`) retain
their original strict comparison. Numerical convergence gates are unchanged.
Use `--relative-tolerance 0` to restore strict acceptance; the pinned plan records
the policy, and reports retain both strict and provisional results. See
[ISAE_STATUS.md](docs/validation/ISAE_STATUS.md) for current counts and remaining failures. The earlier
[validation audit](docs/validation/isae-validation.md) retains its historical
results and import counts; experimental agreement is not required for acceptance.

The [zero-area/ST-4 audit](docs/validation/zero-reference.md) adds 64 literal
structural imports, 81 modal states and independent energy/continuous beam
comparisons, plus three WASM and three offline browser checks. Experimental
inertia, frequency-table and setup conflicts remained at that stage. This
historical numerical supplement left coverage at 16 partial / 25 pending.

The [primary ST-4 study](docs/validation/st4-primary-study.md) now compares
252 vacuum and 252 still-air modal states with 672 independent references.
It preserves all 78 before/after observations, including six incomplete
triplets, and compares the 72 complete triplets as sorted spectra. At 32
intervals the first three still-air frequencies agree with the continuous
model within 0.4712%, but their mean absolute experimental discrepancy is
9.264–9.296%, with a maximum of 54.867%. Air density is assumed to be
1.225 kg/m³; the primary zero-speed table does not report it. Missing inertia
and fixture details and higher-mode mixing remain physical limitations.
The 176 selected native checks, one JavaScript check, three WASM replays and
three fresh offline browser checks pass; this is not a full-suite or physical
validation pass.

Exact zero-speed still-air modes are available for a stationary, fixed frame,
with explicit density and retained pose/gravity. They add the published thin-strip
apparent inertia to the structural system. Broader zero-flow nonlinear analyses,
ROMs, stability sweeps, frequency response and time launches from this mode
remain unsupported.

The [Pazy ST-2 study](docs/validation/isae-st2-comparison.md) compares 77 static
measurement rows using 246 distinct solves and checks 16 air-free modal states.
Independent beam, WebAssembly and offline browser checks pass; experimental
discrepancies and source/load conflicts remain. All six literal Pazy files still
reject out-of-range attachments, so the solved reconstructions are explicitly
labeled. No material properties were fitted.

The [corrected primary Pazy study](docs/validation/pazy-loaded-comparison.md)
adds 225 static states, 26 modal states, 28 independent nonlinear references
and comparisons with all 77 static measurement rows. It corrects an inertia
product-sign error in my earlier derived inputs, verified against the original
Nastran mass matrices; the solver is unchanged. Use the four
`pazy-primary-conm2-*.asw` models. The earlier primary study is explicitly
superseded. Mesh convergence and native/WASM/browser agreement are checked;
experimental discrepancies, fixture details, literal attachments and the
explicit extension–torsion projection remain unresolved.

The [sparse modal adjoint recovery](docs/validation/modal-adjoint.md) avoids a
second full eigensolve for simple poles. All 26 saved corrected Pazy modal
matrices, 295 selected regressions, three WASM replays and three fresh offline
browser cases pass. Original physical equations and finite-root classification
are unchanged. The observed eigensolver improvement does not establish an
end-to-end browser speedup or resolve experimental discrepancies. Earlier
validation studies retain their original source pins.

The [dense modal reduction repair](docs/validation/dense-staircase.md) resolves
the ST-3 failures on the checked 8/16/32-panel meshes while retaining complete
finite spectra and original-equation checks. The 64-panel uncoupled case still
requires a tighter rank setting; experimental discrepancies remain.

The [ST-3 static study](docs/validation/isae-st3-static.md) compares 160 signed
measurements and the archived ASWING curves, and identifies a 1.3734 torque
conversion error in the upstream scripts. Independent beam and WASM checks
pass; experimental differences remain unresolved. The subsequent
[structural static workflow](docs/validation/structural-static-workflow.md)
supports the three literal signed-load files directly, with 398 native
replays and passing offline desktop/mobile browser checks.

The [literal ST-5 study](docs/validation/distributed-static.md) also supports
signed distributed bench loads with separate rotating centroids. Three
original joined-wing examples pass five mesh levels and desktop/mobile checks;
experimental bending-moment differences and unsupported attachments/custom
joint behavior remain.

The [current ST-5 comparison setups](docs/validation/isae-st5-browser-presets-20261110.md)
add all sixteen static cases to the example picker and an explicit **Apply ST-5
comparison setup** action for the reviewed section equations and node grids.
Source/data checks pass; browser integration and build verification remain
pending under the UserLAnd test hold. The current mechanics comparison is
16,687/16,688, with the remaining mismatch retained.

The [SA-6 aileron study](docs/validation/isae-sa6.md) checks all seven original
models and a separate 10-inch reconstruction against primary NACA tables.
It reconciles control signs, body/stability axes, yaw normalization and mixed
test angles; experimental and archived-ASWING discrepancies remain.

The [SA-10 winglet/tip-sail study](docs/validation/isae-sa10.md) compares six
variants, including an explicit root-joint reconstruction. Mesh/PG/influence
sweeps, drag at matched lift and offline browser checks retain failed states,
missing branches, growing junction velocities and experimental discrepancies.

The [SA-12 ground-effect study](docs/validation/isae-sa12.md) completes 2,866
states and compares all 75 lift and 71 drag measurements at their exact angles.
Three meshes, independent image-velocity checks, 33 WebAssembly replays and
17 offline browser cases pass their numerical checks. Experimental discrepancies,
unrecorded archive pitch and equivalent-flap section limitations remain.
The [SA-11 winglet/transonic comparison](docs/validation/isae-sa11-comparison.md)
now completes 5,304 requests: 1,227 computed and 4,077 rejected. Its 166
matched-lift drag requests produce 38 observed roots and 128 missing roots.
Source conflicts, growing local velocities and transonic model limits prevent
a validation pass. Seventeen of 41 families have completed quantitative studies
of part of their scope; 24 await completed studies. The earlier SA-12 package
contained 13 partial families, and the pre-primary-ST-4 ledger contained 16;
new distributions include the current ledger.

The [SA-13 airship diagnostics](docs/validation/isae-sa13.md) add conditional
outline reconstructions and native/WebAssembly comparisons, with unresolved
geometry and source-normalization conflicts. The zero-radius endpoint display
defect is repaired in the source after the complete regression and 36 repaired
checks. Exact terminal values are preserved without clipping nearby geometry.
This work has not increased the released coverage count.

The [SA-14 wing/body pilot](docs/validation/isae-sa14-pilot.md) adds 50 native
and WebAssembly cases, primary force normalization and independent body-field
checks. The [extended lift comparison](docs/validation/isae-sa14-polars.md)
evaluates all 180 archived polar rows and 44 exact experimental lift points in
2,952 native states, retaining 48 validity rejections. Another 78 WebAssembly
and 12 offline browser cases verify solutions and expected rejections.
Growing tip-local velocity still prevents a broad mesh-convergence claim.
The [original load-export audit](docs/validation/isae-sa14-load-exports.md)
reconciles all 426 printed rows with ASWING's staggered node/midpoint convention,
retains manually edited plotting rows, and compares 18 native profiles.
Section-load and moment-reference discrepancies remain explicit.
The [4° incidence comparison](docs/validation/isae-sa14-incidence.md) adds
54 native states, 18 WebAssembly replays and eight offline browser checks.
Equivalent coordinate frames agree, but experimental local-load errors persist,
especially at higher angles. The reconstructed inputs remain explicitly conditional.
The [consolidated SA-14 audit](docs/validation/isae-sa14-comparison.md) maps all
116 digitized points, 180 polar rows and 426 original load-table rows. It counts
3,035 distinct native conditions, retaining 48 rejections and all physical limits.

The [swept-line diagnosis](docs/validation/swept-lifting-line-limit.md)
reproduces that field growth with prescribed smooth circulation and independent
vortex integration. It identifies a singular swept force-velocity limit that
still needs a physically justified resolution and reference-ASWING comparison.

Steady equilibrium and eligible nonlinear BDF steps use sparse mechanical
matrices with a small circulation/frame Schur complement. Bounded matrix reuse,
direct circulation derivatives and exact influence caching reduce repeated work.
Every accepted state satisfies the full physical equations; mesh, time steps
and convergence tolerances are unchanged. General trim, controller and inverse
systems retain their general paths. See the [numerical method](docs/NUMERICS.md)
and [current performance evidence](docs/validation/frame-influence-reuse.json).

In the nonlinear matrix-reuse study, the default twenty-step Daedalus
free-flight case takes 76.43 → 51.05 seconds, including initialization at
28.67 → 13.81 seconds. Its complete offline browser check takes 102.78 seconds
and accepts all twenty steps without retries. These are shared-host observations,
not portable timing guarantees. The record retains source pins, original
convergence checks and complete physical-output differences, with 251 native
and 25 WebAssembly checks. The workbench distinguishes runtime startup,
force application, matrix assembly and time stepping.

Full DAE48 derivative-matrix assembly at the same saved state uses
163.70 → 131.16 CPU seconds in sequential native observations,
with every A/M entry unchanged. Elapsed clocks diverged; this does not establish
a consistent wall-time improvement or measure equilibrium search and frequency
response/output calculations. See the [influence reuse checks](docs/validation/bode-influence-reuse.json).

Bode runs now reuse the complete live response matrices when the aircraft and
operating point match, including after changing frequencies or selected inputs.
Saved-equilibrium launches also share their final physical tangent with Bode.
In the matrix-reuse study, full DAE48 native saved-state setup measured 248.70 → 202.06
seconds; repeated complete-matrix setup is 0.905 seconds.
A new full 21-frequency range in the offline browser takes
315.38 wall seconds after the initial construction.
First cold construction and universal final-Newton reuse remain unfinished.
See the [scoped matrix-reuse evidence](docs/validation/bode-matrix-reuse.json).

The shared warm-equilibrium tangent also stays sparse through its constraint
check. A conservative inverse-norm certificate keeps the original rank threshold,
with the full SVD as fallback. Full DAE matrices and the checked browser responses
remain exactly unchanged. Progress identifies the constraint-check stage; see
[the sparse rank-check evidence](docs/validation/bode-sparse-equilibrium-rank.json).

Small beam motion maps now use the same exact bounded cache. Entirely
positive-zero local motion also avoids unused interpolation work while retaining
its rotation-domain checks. The full DAE A/M comparison and checked browser
responses remain unchanged; see [the motion-reuse checks](docs/validation/bode-motion-reuse.json).

Bode input derivatives now retain their unchanged influence matrices throughout
the sweep and matching repeated runs. Full 21-frequency DAE responses remain
byte-identical; see [the input-influence checks](docs/validation/bode-input-influences.json).

Harmonic sweeps also reuse fixed beam factors and reduced A/M matrices. DAE48
retains all 5,167 states while factoring 1,867 variables per frequency, with
the original full condition and residual checks. In the scoped actual WASM
comparison, 21-frequency state solves use 52.20 → 33.87 CPU seconds,
plus 2.51 seconds of reusable setup. Initial matrix construction and
output recovery remain separate costs. See [the beam-factor reuse evidence](docs/validation/bode-beam-factor-reuse.json).

Retained aerodynamic matrices now apply the four original geometry samples in
batches. Full DAE matrices and checked browser responses remain identical; a
conservative native repeat pair uses about 8% less assembly CPU time. See the
[batched-field validation](docs/validation/batched-field-matrices.json).

Support loads now use a retained analytic output matrix, eliminating the checked
DAE support-moment cancellation error without changing the equations of motion.
See the [support-output validation](docs/validation/support-output-matrix.json).

Grouped geometry preparation further reduces DAE48 matrix assembly work.
Paired native A/M/G mean CPU time is 44.24 → 31.11 seconds, with identical
matrices and checked browser responses. This excludes equilibrium and app startup.
See the [grouped-geometry validation](docs/validation/grouped-geometry-stencils.json).

Vortex receiver matrices now share endpoint/core changes and build only changed
core columns during assembly.
Paired native DAE48 A/M/G mean CPU time is 55.81 → 47.99 seconds, with
identical matrices and checked browser responses. See the
[shared-vortex validation](docs/validation/shared-vortex-sources.json).

Volume receiver matrices now share source-change calculations during assembly.
Paired native DAE48 A/M/G mean CPU time is 52.41 → 45.36 seconds, with
identical matrices and checked browser responses. See the
[shared-source validation](docs/validation/shared-volume-sources.json).

Unchanged lifting-surface geometry now shares exact calculations during matrix
assembly. Paired native DAE48 A/M/G mean CPU time is 55.32 → 42.49 seconds,
with identical operators and checked responses. See the
[geometry-reuse validation](docs/validation/lifting-geometry-reuse.json).

Body and point-object influence derivatives now share the retained matrix path.
Sequential native DAE48 A/M/G assembly takes 50.43 → 35.93 CPU seconds,
excluding equilibrium, responses and app startup. See the
[volume-matrix validation](docs/validation/volume-matrix-reuse.json).

DAE48 inertia-matrix assembly now uses 40 load evaluations instead of 470.
The matrix and checked browser responses remain exactly equal; paired native
M-assembly CPU time is 11.37 → 1.63 seconds. See the
[rate-matrix validation](docs/validation/circulation-rate-matrix-reuse.json).

Bode matrix construction now reuses direct vortex derivatives. Sequential native
full DAE48 A/M/G assembly takes 173.64 → 90.37 CPU seconds on this host,
with the existing accuracy gates; this excludes the rest of application startup.
See the [matrix-assembly validation](docs/validation/direct-vortex-matrix-reuse.json).

Unchanged material matrices now share their damping-energy check across
dynamic snapshots. Full DAE48 output recovery uses 40.59 → 35.49 CPU seconds
with exactly equal outputs, excluding setup and state solves; see the
[material-matrix reuse checks](docs/validation/damping-matrix-reuse.json).

Bode output recovery now also retains the full moving-source field derivatives
from A and input assembly. On the full 21-frequency DAE48 case, native input/output
work uses 68.10 → 45.70 CPU seconds, excluding initial matrices and state
solves. Sensitive geometry derivatives and moment cancellation are corrected
without reducing the mesh or relaxing solver tolerances. First construction and
complete C/Q/D maps remain unfinished; see [the output-matrix reuse checks](docs/validation/bode-output-matrix-reuse.json).

Loaded-wing validation still has an unresolved ASWING comparison: the reconstructed
75% spar wing crosses locally at 22.58 m/s on the finest tested mesh, versus the
published 24.58 m/s number with incompletely known original settings. The
[native study and evidence](docs/validation/loaded-flutter.json) retain that gap;
no physical parameter was fitted to match it. The 16-interval crossing endpoints
and the 32-interval near-neutral point also pass
[public-API WASM and offline browser replay](docs/validation/loaded-flutter-portability.json),
including physical mode shapes and mobile CSV exports.
An [independent loaded-structure check](docs/validation/loaded-wing-mechanics.json)
now covers both wings' offsets and rigid shear/extension limits while holding
nodal loads fixed. Finest-mesh tip responses agree within 0.076%.
The [distributed structural dynamics check](docs/validation/loaded-wing-dynamics.json)
now compares complete nodal frequency-response and real-mass matrices. On the
finest meshes, overall response differences are below 0.39% and four matched
structural frequencies per wing agree within 0.204%. Weak point-load channels
need separate mesh checks. The new
[independent coupled reference](docs/validation/loaded-aeroelastic-reference.json)
recomputes the loaded equilibria, aerodynamic feedback, real/apparent inertia and
twelve local coupled modes. Finest selected-mode differences are below 0.015%.
Its independently bracketed crossing at 22.5763 m/s agrees with the production
solver near 22.578 m/s. Both remain below the published 24.58 m/s; shared aerodynamic
conventions, original setup and full-spectrum coverage remain unresolved. The
[kinematic-arm sensitivity study](docs/validation/aero-kinematic-arms.json) changes
only motion arms and moves that local crossing by less than 0.02 m/s, so this
particular choice does not explain the roughly 2 m/s gap.

The current workbench imports and exports `.asw` files, edits beam property
stations with spline previews and undo, edits per-beam computational nodes, displays aircraft geometry,
and solves rigid aerodynamics or **constrained quasi-steady aeroelastic equilibrium** for
lifting surfaces and slender bodies. Body lift/drag and distributed source/doublet
flow interact with the wings; point-object drag areas and aerodynamic volumes
also contribute to the flow at their current pylon positions.
Solid-ground and constant-pressure free-surface images reflect vortices and
volume singularities about a plane positioned using Earth coordinates and
aircraft attitude. The workbench displays that physical plane after a solve.
The Flow field tab surveys arbitrary body/Earth planes through rigid, deformed
steady or selected time states, with velocity decomposition and CSV/JSON/SVG
exports. It also inspects the steady bases of modal and frequency analyses.
The **Steady polars** tab runs an explicit angle list with the current rigid or
mounted settings. It plots CL, CD, CDi and Cm, retains failed points, and exports
the full sequence as CSV or JSON. Inspect a point to show its loads and report.
Choose independent starts or continuation from the previous converged point.
Continuation solves the full equations again; a failed point is retained and
the next point starts independently. Clear any loaded external equilibrium
first. Projects retain the angle list, starting-solution choice and inspected
single-point solutions. Exports identify the seed and any rigid cold retry.
See [steady operating-point sequences](docs/validation/operating-points-20261030.md)
for the JSON API and remaining workflow limitations.
Trefftz-plane lift, side force, induced drag and span efficiency use the current
circulation and a straight far wake. Total drag and load balance retain the
near-field forces; both drag definitions are displayed and exported.
Each lifting beam can use pointwise circulation or a truncated Fourier sine
series. The **Circulation representation** controls set its independent mode
count while retaining the structural intervals for aerodynamic interactions and
loads. The report exposes both the weighted solve residual and the local flow
defect, which need not vanish when the series is truncated.
The **Aerodynamic lag** option in the same panel defaults to enabled. Disabling
it gives instantaneous circulation and removes circulation-rate lift while
retaining apparent mass, elastic inertia and damping. Saved cases and computed
states record the choice; the solver report displays it. See the
[lag-option checks](docs/validation/aero-lag.md).
The **Wake core radius / chord** control defaults to 0.25 and adjusts smoothing
between different physical surfaces and at external flow samples. Interval
width remains a lower bound; same-physical-surface lifting interactions use zero
core. Saved cases and states retain the setting. The close-wake example and
[independent line-integral study](docs/validation/wake-core.md) illustrate its effect.
The **Freeze aerodynamic influences (K/F)** option uses the undeformed aircraft
and zero wind angles for vortex and volume velocity coefficients. Circulation,
current section frames, motion, gusts, jets and load transfer remain active.
Mach and the ground image plane still update the coefficients. New and older
OpenSwing cases default to **off**; ASWING's printed menu defaults to fast mode.
Use current influences for large deformation or close wake interactions. The
[frozen-influence notes](docs/validation/frozen-influences.md) specify attached
receiver, external survey and Trefftz conventions.
The **Span loading** view also shows force-point relative velocity, section-normal
speed and local Mach, including computed time histories and sampled envelopes.
The report locates the maximum local Mach; CSV and saved solutions retain the
sample coordinates and velocity. Older records without these quantities show
gaps. A [closed-form swept-line study](docs/validation/section-airflow.md) reproduces
the tip-velocity growth found in SA-2 without solving for circulation. The
subsonic rejection remains in place; these diagnostics do not establish a
converged or experimentally validated swept-wing solution.
The same view exposes local quarter-chord **cₘ**, normal circulatory load,
normal distributed gravity/inertial load, and the effective incidence change
caused by elastic deformation. These quantities extend to computed time states,
envelopes and exports. Incidence is displayed in degrees and stored in radians;
the inertial density excludes concentrated point masses and support reactions.
The **Normal section-load reference** example and
[analytical verification](docs/validation/section-outputs.md) explain the
definitions, current-length normalization and sampling conventions.
These four quantities also have complex eigenmode, harmonic-transfer and
initial-state-spectrum outputs. Select them in the Modes or Bode views; complex
incidence plots and CSV use radians, and spectra retain the additional time
unit and initial-value rate terms. Nonlifting or undefined base samples remain
unavailable. See the [dynamic output checks](docs/validation/dynamic-section-outputs.md).
The coupled solve includes connected beams, finite rotations,
all section stiffness couplings, gravity, full distributed/point inertia and
angular momentum, rigid pylons, rigid/pinned/roller grounds and joints, and
sprung-hinge Jangle laws with moving axes and continuous nonlinear splines.
Axial struts or tension-only wires brace the beams. Engine types 0/1/2 include
deformation-following thrust/torque, actuator-disk losses, P-factor loads, and
momentum-conserving propulsive jets coupled to circulation and point-object drag.
Circulation, deformation and selected operating variables share one nonlinear
system. Prescribed force, moment, lift or coefficient targets can solve for flow,
body motion, flap controls or engine settings. Earth position and attitude can
also be solved using load, Earth-motion-component and flight-path-angle targets.
Standard-atmosphere altitude sets density and sound speed; explicit density,
gravity and PG Mach settings are available. Equivalent-airspeed and dynamic-pressure
targets can solve true airspeed, and ASWING's N multiplier scales lift targets.
A free-flight preset solves the six accelerations for zero net load.
Steady-flight presets enforce the reference-point-aware turn kinematics and can
also trim all six net loads using angle of attack, bank, three flap controls and
an engine. Straight flight, level turns and climbing turns use the same coupled
elastic solve; speed and sideslip stay prescribed.
The workbench displays true-scale deformation, mass/CG/inertia,
loads, targets and support reactions, with CSV/JSON exports. Section recovery
adds local forces/moments, mechanical strains and curvature changes, signed
shell-point strain, strain bounds and closed-shell torsional shear stress. Coupled quasi-steady
stability/control derivatives include elastic response, fixed or free-flight
accelerations, coefficient matrices and structural-response plots. Broader trajectory
validation, remaining constraints, combined radius/axis discontinuities and other requirements remain open.

The numerical kernel also has an experimental **implicit time solver** with
local elastic motion, distributed real/apparent inertia, circulation lag and
strain-rate damping. BDF1/BDF2 and three-stage Radau IIA advance the coupled elastic and six-degree-of-freedom
frame state, either with prescribed frame accelerations or free-flight load
constraints. Saved equilibria can launch with compatible physical initial disturbances; nonlinear load and acceleration completion preserves the prescribed fields. Initial load release is supported through the API. The workbench exposes time
response, documented open-loop forcing tables, time plots and computed-state
playback in body or Earth axes. Optional actuator targets solve flap or engine
settings from specified load, lift or frame-acceleration histories while retaining
the trajectory equations. The time panel accepts rows such as `E1 Ax .2`;
[the inverse-target record](docs/validation/time-actuators.md) describes units,
reference checks and remaining limitations. Motion-history rows now also accept
the documented V/A/B, body-rate, Earth-position, attitude and climb-angle labels,
plus explicit Earth-vector targets such as `E1 velocity_earth.x -10`.
Cold initialization holds the entered frame motion and solves compatible elastic
shape and actuator settings. Target, achieved value and residual are available
in the time plots and CSV. See [motion-history scope and validation](docs/validation/inverse-histories.md)
for units, BDF accuracy, saved-launch restrictions and remaining gaps.
Accepted inverse roots and physical
checkpoint consistency now have additional [regression and WebAssembly checks](docs/validation/solver-consistency.md). Earth-coordinate gust fields are supported; the complete numeric gust catalog, ASWING companion-file restart and experimental flutter validation remain pending. Independent
oscillation, free-fall, rigid-body conservation, cantilever-frequency and
empirical-lag checks are recorded in [the numerical notes](docs/NUMERICS.md#implicit-time-integration).

An optional **Time-step accuracy check** compares a full step with two half steps
and accepts the refined endpoint when their scaled physical discrepancy is within
tolerance. Controls and checkpoint continuation support the setting; plots and
CSV retain its per-step diagnostics. Independent mechanical, controller and finite-wing studies, packaged-WASM
replays and offline browser checks cover this experimental OpenSwing extension.
It does not bound total trajectory error or replace mesh and time refinement; see [the verification record](docs/validation/time-accuracy.md).

Experimental **coupled eigenmodes** linearize the same elastic, inertia and
circulation-lag equations about a loaded operating point. Fixed-frame and free-flight
modes, vacuum, dense or shift-and-invert solves, left/right vectors, complex
loads/strains and body/Earth mode playback are available. Numerical rank, mesh and
linearization-step convergence must be checked. Root progression and instability
bracket refinement, bounded adaptive tracking grids and warm equilibrium
continuation are available across operating points. Fold/bifurcation tracking, arbitrary legacy control routines and ASWING/experimental modal validation
remain open. Scheduled feedback and integrated-error modes are supported.

Experimental **frequency response** solves the full forced dynamic equations for
flap, engine and complex spatial gust inputs. The Bode view includes unit-input
magnitude/phase, physical load and strain outputs, body/Earth phase playback at
the stated input amplitude, and CSV/JSON exports. Direct input and rate-dependent
loads are retained. Feedback commands and consistent physical initial disturbances
are supported. Initial disturbances produce one-sided Laplace spectra with the
required initial-value terms in rate-dependent outputs. Singular frequencies are
reported per input as gaps. ASWING frequency-response parity remains open.

Larger harmonic analyses use the full sparse descriptor matrices and pivoted
sparse LU. Exactly independent derivative probes share evaluations, and unchanged
node and element maps are reused. Circulation columns share direct physical derivatives with the nonlinear
solvers. Geometry columns combine grouped local derivatives with complete moving
vortex, volume and jet feedback; unsupported branches retain full residual
stencils. Constant input columns and physical output evaluations are reused
without reducing the mesh, frequency count or residual accuracy. Progress identifies loaded equilibrium, response-model construction,
inertia and damping, frequency completion, and final output. Initial-disturbance
spectra retain their dense reduction. See the
[Bode performance and accuracy checks](docs/validation/bode-geometry.json).

Ordinary **Sensor** records now provide moving pitot/vane, inertial, GPS and
structural measurements in steady, time, modal and harmonic results. Sensor axes
follow the elastic anchor and rigid pylon. The Sensors tab shows physical values
or complex perturbations; sensor quantities are available in history and Bode
plots and CSV/JSON exports. Scheduled feedback and integrated measurement errors
participate in the same time, modal and harmonic equations. Bounded explicit
and implicit actuator expressions and custom differential states support filters,
actuator lag, saturation and anti-windup. Arbitrary legacy control routines,
default ASWING index bindings and complete control-file compatibility remain
pending.

Controller cold and time solves now check the final centered tangent, with
[physical regression and packaged-WASM evidence](docs/validation/controller-time-rank.md).
This detects the reproduced smooth actuator ambiguities while preserving
controller initial states. Nonsmooth expressions additionally receive bounded
probes of the original full residual. When these find distinct accepted force
settings, the run stops without retrying through the witnessed ambiguity.
Unique saturation remains supported. The
[original clipping-boundary failure](docs/validation/controller-one-sided.md)
and [the correction's scope](docs/validation/controller-nonsmooth.md) are recorded;
finite probes do not establish general nonsmooth uniqueness.

See [the implementation and validation ledger](docs/REQUIREMENTS.md) for scope and
remaining work, [the numerical formulation](docs/NUMERICS.md) for equations and
conventions, and [the current work record](docs/STATUS.md) for continuation tasks.

On phones, the workbench has **Editor**, **Settings**, **Plots**, and **Output** tabs. Plots stacks the 3D aircraft, span loading, eigenmodes, structural response, time history, Bode response, and flow field. The analysis button and progress remain available across all four tabs. Switching layouts preserves the live controls and viewer; cases and computed solutions keep their settings.

The ASW editor uses VibeLattice's dark background and syntax palette, with ASWING
block names and distribution fields, numerical values (including Fortran
exponents), names and comments highlighted. Editing, selection and file contents
remain owned by the native text field.

The **Example configuration** picker includes all three `.asw` downloads from
[Drela’s ASWING page](https://web.mit.edu/drela/Public/web/aswing/) under
**Drela’s ASWING examples**: Daedalus (`dae.asw`), the ultralight sailplane
(`usa.asw`), and the swept flying wing (`fw.asw`). Their original files are
included in both the source and offline app downloads. They retain their
upstream attribution; see [THIRD_PARTY.md](THIRD_PARTY.md).

Under **ISAE aerodynamics**, the SA-11 picker includes **wing alone**,
**upper winglets**, and **upper + lower winglets**. The wing-alone baseline has
no winglets and retains the original `wing_alone.asw` bytes. The two winglet
examples correct joint-station scaling in the supplied files so their beams
can be inspected together; their surface geometry and section properties are
unchanged. These corrections are disclosed beside the picker and in each
file's comments. Provenance is in `examples/isae-sa11-source.json` and
`examples/isae-sa11-winglet-sources.json`. The corrected examples do not replace
the original inputs used by the validation ledger.
The picker and plot headings identify the selected winglet variant even though
both upstream files use `Wing_alone` in their Name block. Drag the aircraft view
to inspect both sides; one winglet can be hidden behind the wing in perspective,
while **Front** shows the upper/lower arrangement nearly edge-on.

These inspection examples still expose an unresolved local-flow Mach issue in
the aerodynamic solver. At 30 m/s and 5° incidence, clearing **Freeze aerodynamic
influences (K/F)** allows the upper-winglet model to compute on the two checked
meshes; it does not resolve the upper/lower variant or establish convergence.
See the [junction investigation](docs/validation/isae-sa11-winglet-junction-20261107.md).

Use **Horseshoes** above the aircraft view to show cyan bound lifting lines and
violet trailing legs. A preview uses the current mesh and wind settings without
solving; computed results use their actual influence geometry. Frozen influences
therefore show the jig horseshoes with wakes along body x. The drawing shows one
span of each semi-infinite leg; modal/frequency views show the base-state vortices.
Ground-image vortices are not drawn.

**Streamwise chords**, enabled above the aircraft view, draws the projected
surface outline. Turn it off to inspect the normal section chords.
This implements the plotting choice described under ASWING 5.45 and the
Options / U toggle under 5.75 in
[Drela's version notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt).
The drawing projection retains twist in the local surface plane and follows
deformed, time, modal and frequency-response geometry, including Earth views.
For a section whose span aligns with body x, the projection is singular and
the normal section is retained. Older saved responses without projected
geometry also retain their normal sections.

The input chord convention is separately explicit in
[Drela's FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt), under
the question about normal versus streamwise chords: normal chords are inputs;
the stated conversion from streamwise chord multiplies by local cosine of sweep.
It also follows from the local Cartesian `c,s,n` axes in
[Drela's theory, §1.1, page 5](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=5)
and the chord-aligned `c` axis in
[§1.5.2, page 11](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=11).
Thus the section chord is perpendicular to the local span axis `s`.
[Figure 16 and equations 155–157, page 32](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=32)
separately define the wind-aligned vortex/control-point offsets.

In normal-section display, mirrored surfaces are trimmed at their root join
to avoid overlapping skins. Both plotting choices leave input chords, raw
normal-section output geometry, horseshoes and aerodynamic equations unchanged.
See the [source evidence and display checks](docs/validation/isae-sa11-display-20261107.md).

## Host on GitHub Pages

The included [Pages workflow](.github/workflows/pages.yml) builds and deploys
the app for **https://openswing.vibefoil.com/**. Enable **GitHub Actions** as
the Pages source, set that custom domain, and add an `openswing` DNS CNAME
pointing to your repository owner's `<owner>.github.io` hostname. See the
[deployment instructions](docs/GITHUB_PAGES.md) for setup and HTTPS.

## Run locally

**With Python only:** download **Local app** from the workbench, extract the ZIP,
open a terminal in the extracted folder, and run:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open **http://127.0.0.1:8000**. On Windows, `py` can replace `python3`.
The prebuilt bundle includes all numerical runtime assets; it needs no Node.js,
pip packages or internet connection. Keep its directory structure intact.
The local ZIP omits the optional raw validation bundle. Its source download
still contains the complete implementation, tests and validation summaries.

**From source with npm:** requires Node.js 22.12+ (24 recommended) and Python 3
for ZIP packaging. No native NumPy/SciPy installation is needed to run the app.

```sh
npm ci
npm start
```

This builds and serves the app at **http://127.0.0.1:8000**. Stop either server
with Ctrl+C. For development with live updates, run `npm run build` once, then
`npm run dev` and open the URL it prints.

Development serves the Python kernel directly from `openswing/`, so native
checks and browser analyses use the same source files. Reload the page after
editing Python to replace the worker's already-loaded kernel. Production builds
and prebuilt downloads keep their packaged sources; rebuild them to include changes.

Keep the included `vite.config.js`: it starts dependency scanning from the
workbench entry point and avoids watching large reference and experiment trees.
The [fresh-cache startup check](docs/validation/dev-startup-20261030.md) verifies
that the development app loads its real dependencies and numerical worker.

You can also serve an existing source build with Python:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Use a web server rather than opening `index.html` directly. These servers only
serve static files: the JavaScript interface runs the Python numerical kernel
inside a browser worker using WebAssembly. The 3D view uses WebGL2 when available
and an interactive software projection fallback otherwise.

The initial source build downloads the pinned Pyodide,
NumPy, and SciPy runtime assets; wheel SHA-256 checksums are verified against the
runtime's lock file. Aircraft text is sent only to a local browser worker. All
numerical runtime files and fonts are served from the application origin.
An automated Chromium check disables networking after the runtime has loaded,
then reparses the mesh, solves mounted equilibrium and exports the result.
Initial loading still requires the static application assets.

The build's source ZIP is downloadable in the web app. All original code and
original example inputs are under the MIT license. ASWING source code is not used
or distributed. Reference publications and upstream example files are fetched
separately into an ignored directory and are not relicensed by this project.

`npm run build` creates `openswing-source.zip` and `openswing-local.zip` in `dist`.
It skips the optional raw validation bundle, which can be many gigabytes, and
removes any older generated `public/openswing-validation.zip` before Vite copies
the application assets. Original archives in `docs/validation` and their catalog
are retained. To include those raw archives in a hosted build, explicitly run:

```sh
npm run build:validation
```

That build also creates `openswing-validation.zip`, preserving the original
archive bytes and recording their SHA-256 checksums. A source-only rebuild
retains the catalog of missing optional files and advertises only archives
actually included in that build. No raw validation files are downloaded automatically.

## Distributions across a time history

After a time solve, choose **All snapshots** or **Sampled envelope** in the Span
loading or Structure tab. An envelope retains signed minima and maxima at each
material station and the time and snapshot where each occurred. Select a trace
or extremum to inspect its computed state. These are sampled extrema; refine
time steps and the mesh to resolve peaks between samples.

**All snapshots CSV** exports all beams and times in raw input units for the
selected family (structural sections, aerodynamic strips, or shoulder forces).
**Envelope CSV** exports the selected beam/quantity in displayed units, with
sample counts and each extremum's snapshot, time and forcing side. Missing
values remain gaps and incompatible grids are rejected. See the
[workflow and validation notes](docs/validation/distribution-history.md).

## Validate

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python scripts/fetch-references.py
.venv/bin/python -m pytest -q
npx playwright install chromium
npm run test:browser
npm run test:wasm
```

The upstream-file tests explicitly skip if reference inputs are absent. Run the
fetch script to exercise those compatibility tests. Browser tests load the actual
WebAssembly numerical kernel, run analyses, exercise file handling and exports,
check mobile layout, and invalidate stale results after edits.

This environment uses an ARM64 Ubuntu development release. Playwright 1.58.2
requires `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-arm64` for its bundled
browser on that host; this override is not needed on normally supported systems.

The dedicated `tests/browser/webgl.spec.js` workflow requires a working WebGL2
driver and checks an offline computed deformation, camera/shape controls and
mobile resizing. Its default is Chromium's WebGL-only SwiftShader mode. On this
host that driver fails; the recorded passing run uses Mesa's software Vulkan
driver instead. With a working Mesa Vulkan loader and ICD configured, run
`OPENSWING_WEBGL_DRIVER=mesa npm run test:browser -- tests/browser/webgl.spec.js`.
For a separately extracted driver, set `VK_ICD_FILENAMES` to its ICD JSON and
`LD_LIBRARY_PATH` to its required libraries. These are test-host dependencies,
not application downloads. The [renderer record](docs/validation/browser-renderer-20261006.json)
retains driver/package fingerprints, failed attempts and the successful workflow;
software rendering does not establish physical-GPU coverage.

## Time response in the browser

Select **Nonlinear time response**, start with 4–8 panels per beam and a short
run, then choose prescribed accelerations or free flight. The elastic transient
example includes a uniform flap and illustrative damping and shell data. The initial state is
elastic equilibrium with zero local elastic velocity. Free flight solves all six
accelerations from zero net loads; the `.asw` Ground records define the body frame.
The selected speed, flow angles, attitude and Earth position set the initial frame.
Prescribed, free-flight and mixed-motion startup with zero local motion use the
sparse coupled equilibrium solver and then check the original unsteady residual. Startup,
matrix assembly, nonlinear iterations and smaller-step retries appear in the
status area; accepted time advances only after a step converges.
Prescribed, free-flight and mixed-motion BDF1/BDF2 steps use sparse local mechanics
with circulation and frame variables in a small Schur complement. Failed sparse
corrections retry the full matrix; physical equations and convergence tolerances
are retained. Inverse actuator targets, feedback and
Radau still use their general dense matrices.

Open **Open-loop forcing table** to import or enter an ASWING parameter table.
For example, with a duration of 0.2 input time units:

```text
time +F1
0.00 0
0.05 0
0.05 1
0.15 1
0.15 0
0.20 0
```

This adds a one-unit pulse to the initial setting of flap 1. `F#` selects a flap,
`E#` an engine, and `+` in the header requests increments from initial settings.
Multiplier (`*`) and adder (`+`) rows, comments and doubled-time discontinuities
follow the documented format. Each segment uses a natural cubic spline; ASWING's
endpoint convention is unverified. The first sample must be at or before the
initial time. After the last sample, applied values become zero, including relative
(`+`) channels; extend the table to retain a setting. The last sample itself keeps
its tabulated value. Prescribed-frame channels `Ax/Ay/Az` and `Gx/Gy/Gz` use input
acceleration and degrees per input time squared. Active net-load targets accept
`Fx/Fy/Fz` (input F) and `Mx/My/Mz` (input F·L). Unsupported or inactive channels
produce errors. See [the numerical notes](docs/NUMERICS.md#open-loop-time-forcing).

The **Time history** tab plots coefficients, net loads, support reactions, motion,
node displacement/velocity and prescribed inputs. Scrubbing or playback selects actual computed snapshots,
updating the geometry, load and structural plots, metrics and report. Earth view
includes the computed frame translation and rotation. The camera stays fixed
during playback; use Fit when the aircraft moves out of view. Playback speed
is input time units per real second, independent of the solver time step.

History CSV contains global time series and optionally the selected node trace.
JSON exports every physical snapshot, its physical checkpoint data and the original
solve request. The continuation controls below provide a standalone checkpoint
format; this is separate from ASWING companion files. Span and section CSVs identify the selected time.
Cancel stops the worker and reloads the numerical runtime. Analyses still run
entirely in browser WebAssembly, including after the loaded app goes offline.

Time response is experimental. Refine the step and mesh: Newton convergence
alone does not establish temporal accuracy. BDF2 starts and restarts at doubled
times with BDF1. Radau IIA needs no predecessor and is available for constrained
motion; its nominal fifth-order ODE accuracy does not apply to every reaction
or constrained velocity. BDF startup can produce a peak reaction transient that
does not shrink with the time step for curved constraints and nonzero initial
velocity. Use Radau and check temporal refinement for those motions. A discontinuity snapshot retains its left-hand forcing; the
first following step uses the new value. Atmospheric altitude is fixed, with
an optional prescribed Earth-coordinate gust. Supported controllers, physical
checkpoint restart and direct launch from saved steady trim are available.
Cold/nonsmooth nonlinear initial-state construction, ASWING companion-file
restart, legacy control routines, broader constrained/nonlinear accuracy-control
validation and ASWING numerical parity remain open.

## Gust response

Open **Earth-coordinate gust field** for uniform flow, a one-minus-cosine pulse,
a sinusoidal wave, or expressions in Earth coordinates `x, y, z` and time `t`.
All values use the `.asw` input units. A frozen field stays fixed in Earth axes;
the aircraft moves through it during a time response. The gust also participates
in rigid analysis, coupled equilibrium and their local derivatives.

For a reproducible demonstration, select the **Elastic transient demonstrator**,
4 panels per beam, speed 10, angle of attack 0, and **Nonlinear time response**.
Choose **One-minus-cosine pulse**, leave its default Earth-z amplitude 1, onset
plane X=−3, direction [−1,0,0] and gradient length H=3. Use duration 1.3 and
maximum step .02 in the file's time units. The prescribed frame carries the wing
through the pulse; the reference point reaches its peak near t=.6. The individual
wing locations encounter the field at their own positions. The parameters are
illustrative, not an aircraft-specific design case. Refine the mesh and step.

**Preview an Earth-X profile** evaluates the same numerical field as the solver.
**Field time** sets the steady-analysis and preview time; a cold time response
starts at zero. Use the Time history selector to plot gust velocity at the
velocity reference in body axes. The solver report and JSON record the field,
reference sample and actual aerodynamic sampling locations.

Import/export uses an **OpenSwing JSON format**, including sums of fields.
[`examples/vertical-cosine.gust.json`](examples/vertical-cosine.gust.json) is an
original example. Import also reads the public ASWING type-5 numeric layout with
zero spanwise slope. **Export .gust** writes a canonical type-5 file for a frozen,
straight vertical cosine pulse directed along negative Earth X. Other fields
remain available through JSON. Nonzero legacy slopes, other numeric gust types
and nonzero unused parameters are rejected explicitly until their conventions
are verified. See [legacy gust interoperability](docs/validation/legacy-gust.md)
and [field definitions and limits](docs/NUMERICS.md#earth-coordinate-gust-fields).

Cosine and sinusoidal fields limit the sampled phase travel in each time step
to π/8, even outside a compact pulse. This helps avoid jumping over a narrow
gust. It does not estimate integration error or replace mesh/time refinement;
expression fields have no automatic feature-length detection. Coefficients,
wake alignment and source strengths retain their still-atmosphere references.
The unsteady model uses empirical circulation lag and the published aircraft
apparent-mass terms; it is not exact Sears gust theory.

## Python API

For a rigid steady analysis, **Settings → Circulation representation → Check
continuous Fourier wake** adds a reference CDi and span-efficiency comparison
below the coefficients and in the Solver report. Select Fourier modes on every
lifting beam; unsupported geometry gives an explanation. Angle sweeps retain
the check for each point. The JSON request option is
`"fourier_wake_diagnostic": true`; default results are unchanged.
[Verification and browser-runtime limits](docs/validation/fourier-wake-ui-20261101.md).

```python
from pathlib import Path
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid

model = parse_asw(Path('examples/rectangular.asw').read_text())
result = solve_rigid(model, FlightCondition(speed=30, alpha=5), panels=48)
print(result['CL'], result['CD'], result['residual'])

# Explicit continuous-wake accuracy diagnostic for straight Fourier traces.
condition = FlightCondition(speed=30, alpha=5, circulation_modes={1: 12})
result = solve_rigid(model, condition, panels=48, fourier_wake_diagnostic=True)
reference = result['trefftz']['continuous_fourier']
print(reference['available'], reference['CDi'], reference['reason'])
# The ordinary CDi, efficiency, loads and derivatives retain their discrete definition.

from openswing.network import solve_static
model = parse_asw(Path('examples/flexible.asw').read_text())
result = solve_static(model, FlightCondition(speed=30, alpha=5), panels=24)
print(result['max_displacement'], result['support_force'])

model = parse_asw(Path('examples/stress-wing.asw').read_text())
result = solve_static(model, FlightCondition(speed=30, alpha=5), panels=24)
print(result['structure']['summary'])
print(result['elements'][0]['shell'])  # signed strain, strain bound, shear stress

model = parse_asw(Path('examples/powered.asw').read_text())
result = solve_static(model, FlightCondition(speed=30, alpha=5, powers={1:3000}),
                      panels=24, strut_mode='wire')
print(result['engines'], result['struts'])

model = parse_asw(Path('examples/articulated.asw').read_text())
result = solve_static(model, FlightCondition(speed=30, alpha=5), panels=16)
print(result['hinges'])  # structural moments, angles, moving axes, extrapolation

# A steady right turn with zero sideslip and all six net loads trimmed.
import math
from openswing.operating import steady_turn_constraints
model = parse_asw(Path('examples/trim-aircraft.asw').read_text())
targets = steady_turn_constraints(math.radians(3), flight_path=0,
                                  trim_controls=[2, 1, 3], engine_control=1)
result = solve_static(model, FlightCondition(speed=30, alpha=4, mach=0,
                      attitude=(0, 4, 57), powers={1:120}), panels=16,
                      operating_constraints=targets)
print(result['operating_values'], result['earth_state'])

# Linear response about that trimmed state, with the six accelerations free.
# The same nonlinear solve retains its state for one coupled linearization.
result = solve_static(model, FlightCondition(speed=30, alpha=4, mach=0,
                      attitude=(0, 4, 57), powers={1:120}), panels=8,
                      operating_constraints=targets,
                      derivatives=dict(response='free_flight',
                                       parameters=['alpha', 'control.1', 'power.1']))
print(result['derivatives']['matrices']['accelerations'])

model = parse_asw(Path('examples/wing-body.asw').read_text())
result = solve_static(model, FlightCondition(speed=30, alpha=5,
                      acceleration=(0,0,1), body_added_mass_factor=1), panels=16)
print(result['body_force'], result['apparent_mass'])

# Level flight above the Earth Z=0 image plane; positions use input units.
condition = FlightCondition(speed=30, alpha=5, attitude=(0,5,0),
                            position_earth=(0,0,2), ground_effect=1)
result = solve_static(model, condition, panels=16)
print(result['ground_plane'], result['gravity_body'])

from openswing.operating import OperatingConstraint, free_flight_constraints
model = parse_asw(Path('examples/flexible.asw').read_text())
result = solve_static(model, FlightCondition(altitude_m=10000, speed=25, alpha=3,
                      mach=0, gravity_magnitude=4, load_factor=1.5), panels=8,
                      operating_constraints=[OperatingConstraint('speed', 'equivalent_airspeed', 30),
                                             OperatingConstraint('alpha', 'lift', 1000)])
print(result['atmosphere'], result['operating_values'])  # lift target = 1500 N

model = parse_asw(Path('examples/inertial.asw').read_text())
result = solve_static(model, FlightCondition(speed=30, alpha=5), panels=24,
                      operating_constraints=free_flight_constraints())
print(result['operating_values'], result['mass_properties']['cg'])

# Or replace selected prescribed inputs with independent target equations:
result = solve_static(model, FlightCondition(speed=30, alpha=3), panels=24,
                      operating_constraints=[OperatingConstraint('alpha', 'lift', 2000),
                                             OperatingConstraint('control.1', 'moment.y', 0)])
```

Mounted equilibrium requires sufficient `Ground` constraints. Its default Earth
gravity `(0,0,-g)` rotates into body axes with the aircraft attitude; the Python
API also accepts an explicit body-axis gravity override.
In free flight the grounds define the body frame; the net support force and
moment vanish. This is an instantaneous quasi-steady operating state, not a time
history or a guarantee of steady trajectory trim. Complete bank/turn relations
and remaining operating constraints still require implementation.
Use mesh refinement to assess discretization error. The current dense numerical
Jacobian is intended for modest meshes; start with 24 panels per beam. It rejects
unrestrained mechanisms and redundant reactions at the unloaded configuration.

Aircraft geometry, loads and motion use the file's **consistent input units**. Angles of
attack and sideslip are degrees; body rotation rates are radians per input time;
angular accelerations are radians per input time squared. Absolute linear
acceleration is specified at the file's acceleration-reference point. The browser
accepts angular rates/accelerations in degrees and converts them to radians for
the kernel and exports. Flap settings use the units implied by section derivatives.
Engine types 1/2 use shaft power in input F·L/T; type 0 uses the control units
implied by its thrust/torque gains. A shared engine-control index sets every
engine with that index. `strut_mode='bilateral'` is the default elastic axial
strut law; `'wire'` clips compression to zero. ASW input has no compression-type
or buckling-load field, so this choice is explicit and exported with the result.
Body apparent mass defaults to classical cylinder potential flow
(`body_added_mass_factor=1`). The published ASWING body formula has twice that
coefficient; use `2` or the corresponding browser option to reproduce it.
Both loads and the reported tensor use the selected convention. The discrepancy
and independent checks are documented in [NUMERICS.md](docs/NUMERICS.md).
`model.units.si_scales()` provides explicit SI conversion factors. A Unit entry
`L 0.3048 m` means one input length unit corresponds to 0.3048 m; its numeric
factor must not be discarded. The unedited source is retained for exact text
round trips, including comments and line endings.

Atmospheric `altitude_m` explicitly uses geometric metres (−5,000 to 86,000 m),
independent of the file's length units and `position_earth.z`. Density and sound
speed scale from the file's sea-level constants. Gravity magnitude is prescribed
separately and never changes the mass inferred from the file. Equivalent airspeed
is `V sqrt(rho/rho0)`; ASWING's exact VIAS convention and atmosphere-table
interpolation remain unverified. See the numerical notes for these limits.

`attitude` is `(bank, elevation, heading)` in degrees, following ASWING's axes
and rotation order. `position_earth` is the body origin in Earth axes. The plane
passes through the Earth origin, with normal `ground_normal=(0,0,1)` by default;
nonzero normals are normalized. `ground_effect` is `0` off, `1` solid, or `-1`
constant-pressure free surface. Geometry touching/crossing the plane is rejected.
Oblique compressible image flow is explicitly identified as an approximation;
jet-ground interaction, free-surface waves and wall corrections to local apparent
mass are not included. These settings are operating conditions, not new `.asw`
keywords. Companion operating-file formats remain in the requirements ledger.

`steady_turn_constraints()` uses heading rate in radians/input time, positive in
ASWING's heading direction (negative Earth Z angular velocity). Its default
ten equations constrain motion only. Supplying three distinct flap IDs in
**roll, pitch, yaw** order plus an engine ID adds six force/moment trim equations.
Those controls must have independent authority; their names alone do not ensure
trim exists. The preset imposes no actuator limits. A nonzero prescribed sideslip
is retained. Use `flight_path` in degrees for climbing/descending turns, or zero
heading rate for straight flight. This is local steady trim at the prescribed air
properties, not a time-marched trajectory or a stability result.

In the browser, select the elastic flight-trim example, mounted equilibrium and
a coarse starting mesh, then open Operating constraints → Straight flight &
steady-turn presets. Choose the controls, set the full flight-trim targets and
run the analysis. Refine the mesh; the included convergence study still shows
appreciable coarse-mesh deformation error.

Enable Stability & control derivatives in mounted equilibrium to add the coupled
linear response to a solve. `response='fixed_acceleration'` holds the six
accelerations fixed; `'free_flight'` solves their response and requires a base
state with zero net force/moment. Original inverse/trim constraints are released;
other inputs stay at their converged values. These responses do not keep
re-trimming the control settings after each input perturbation.

The distribution selector includes section forces/moments, mechanical strain,
curvature and signed shell strain/stress sensitivities. Section plots retain
material-midpoint samples and unavailable-data gaps. **Distribution CSV** exports
all input columns with their units.

With feedback enabled, the derivative system includes actual actuator settings,
integrated errors and custom controller states. They solve their equilibrium
equations while other solved commands remain fixed. Select `command.F1` or
`command.E1` for a controlled actuator's command, or a measurement command such
as `command.RY[2]`. Uncontrolled flap/engine settings retain `control.#` and
`power.#` inputs. A controller law may ignore a declared command, giving a zero
response. Controller angle commands use **degrees**; flight alpha/beta columns
still use radians. Integral and custom-state rates stay zero in these responses.

The default columns are `u, alpha, beta, p, q, r` plus declared controls/engines:
`u=delta V/V0`, alpha/beta in **radians**, and conventional stability rates
normalized by span or chord over `2 V0`. `basis='body'` uses velocity at the file's
velocity reference and body rates holding that velocity fixed. `'body_origin'`
uses velocity and rates holding body-origin velocity fixed. These rate columns
differ for offset velocity references. Output coefficient axes can be body,
stability, or reverse stability. Output axes and dynamic pressure remain at their
base values, following steady eqs. 226–229. The coefficient speed derivative
therefore includes the change of dimensional force with speed.

The distributed aerodynamic matrix excludes direct point-object, engine and
apparent-mass loads, following eqs. 220–223; total-fluid and net-load matrices are
also exported. The Derivatives tab displays matrices and nodal position/rotation
responses. CSV exports the selected matrix; JSON includes all response arrays,
reference points, parameter units, step sizes and linear residuals. Compare
meshes and difference steps. These quasi-steady responses are not time-domain
stability eigenvalues or flutter predictions.

Choose **Controller & measurements** to inspect actuator, command, measured
error, integral and custom-state response matrices with physical units.
A controller that leaves an unconstrained equilibrium state after trim targets
are released has no unique steady derivative and is rejected. Switching
boundaries, angle branches and gain-schedule slope changes are checked before
reporting a tangent. Dynamic stability still requires a separate mode analysis.
The [closed-loop derivative study](docs/validation/feedback-derivatives.json)
checks independent spring/controller and acceleration-feedback formulas,
nonlinear and scheduled laws, and an elastic wing using Fourier circulation.
Reproduce it with `python scripts/verify-feedback-derivatives.py`; after building,
run `node scripts/test-feedback-derivatives-wasm.mjs` for packaged-runtime
comparisons. These are internal verification and refinement cases, with no
ASWING executable comparison.

The Structure tab shows material-midpoint section values after mounted or
constrained equilibrium. Local force/moment components use the current c, s, n
frame; bending moments are translated to the tension axis, torsion to the
elastic axis. Curvature changes and mechanical strains are relative to the
unloaded jig. `Cshell`/`Nshell` locate a material point relative to the tension
axis under the theory document's convention. The user-guide labels instead
refer to the elastic axis; that ASWING convention remains unverified.

Shell-point strain retains its sign. The separate strain bound sums absolute
axial and bending contributions for the supplied extents. Torsional shear
stress is `M_s_prime / (2 Atshell)`, assuming a thin, closed, uniform shell.
If both shell coordinates are absent, shell strain is null; zero `Atshell`
means missing stress data, and negative `Atshell` is flagged invalid. Local
loads, mechanical strain and curvature remain available, and these display
parameters never change equilibrium. The original shell demonstrator includes
illustrative parameters; it is not a calibrated structure or strength model.

Plots support raw stress units, Pa and MPa when the file's unit conversion is
known. Section CSV retains input F/L² and dimensionless strain; JSON includes
frames, sample locations, availability, units and signed sampled extrema.
The reported peaks are **midpoint samples**, so refine near supports and load
jumps. Normal stress, transverse-shear stress, warping and material strength
margins are not determined by these inputs. Reproduce the mesh study with
`OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify-sections.py`.

## References

The public [ASWING site](https://web.mit.edu/drela/Public/web/aswing/) links the
[steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
[unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
[user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
[version notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt), and
[extended manual](https://web.mit.edu/drela/Public/web/aswing/ASWING_Extended_User_Manual.pdf).
The point-inertia convention is given in Drela's
[CG and inertia calculation note](https://web.mit.edu/drela/Public/web/aswing/CG_Calc.pdf),
referenced by the 5.99 version notes: `Ixy`, `Ixz`, `Iyz` are products of inertia,
so the corresponding off-diagonal tensor entries have the opposite signs.
The browser workflow is informed by the user's reference,
[VibeLattice](https://avl.vibefoil.com/).

OpenSwing is not affiliated with or endorsed by Mark Drela or MIT. Its code
license does not cover reference publications, ASWING, or third-party packages.

## Coupled eigenmodes

Choose **Coupled eigenmodes** in Analysis. The existing operating targets establish
an equilibrium; controls are then held or governed by the enabled feedback law.
With Free flight
and no targets, all six accelerations are solved for zero net load. This can be an
accelerating state: the report gives its drift, and the roots describe a frozen
linearization rather than a time-invariant trajectory.

**Mixed motion · per axis** lets each acceleration be prescribed or determined
from a constant net-force/moment target. Prescribed and mixed motion retain all twelve velocity,
rate, position and attitude states; prescribed acceleration does not remove their
kinematic drift. Fixed frame holds those states entirely. The base must satisfy
the selected load targets, including when reusing a saved equilibrium.

**Full descriptor · local Arnoldi search** retains the algebraic equations and
weak inertias while finding modes near the requested complex shift. It reports
the total finite spectrum as unclassified. Use a small mode count, compare nearby
shifts and refine the mesh and differentiation step. The reduced methods now
reject resolved weak inertias below their rank cutoff instead of silently
discarding them. Exact coordinate-integrator factors and full left/right
equation checks apply to all three methods.

The first published aircraft comparison uses MIT's
[flying-wing root map](https://web.mit.edu/drela/Public/web/aswing/root_map_fw.pdf)
and matching `.asw` file. Run `scripts/fetch-references.py`,
`scripts/extract-fw-reference.py` and `scripts/verify-flying-wing.py` with the
native Python environment; after building, run
`node scripts/test-flying-wing-wasm.mjs` for the packaged runtime checks.
[The comparison](docs/validation/flying-wing.json) preserves the published
numbers, inferred glide trim, mesh/step/shift studies and remaining differences.
The [comparison figure](docs/validation/flying-wing.svg) is also available as a
[PDF](docs/validation/flying-wing.pdf). Regenerate it with the optional `plots`
dependencies and `python scripts/plot-flying-wing.py`.
It is partial validation against a published figure; the original mesh and
solver settings are unknown. That archived study predates the Trefftz calculation
and its `efficiency` field is a near-field estimate. The subsequent
[Trefftz comparison](docs/validation/trefftz.json) independently recomputes the
trim and far-wake efficiency, using the earlier equilibria as checked warm starts.
Run `python scripts/verify-trefftz.py`, then build and run
`node scripts/test-trefftz-wasm.mjs` to regenerate and replay that comparison.
The [mesh and continuum figure](docs/validation/trefftz.svg), also available as
a [PDF](docs/validation/trefftz.pdf), retains the nonmonotonic aircraft trend.
Historical study hashes remain unchanged; their strict replay tools require
regenerating the corresponding native study with the current kernel first.
The official aircraft input is bundled unchanged as `examples/fw.asw` and is
available in the example picker. The reference figure must still be fetched
separately and is excluded from the source archive.

**Beam nodes** sets each logical beam’s interval count, cosine, modified cosine
or uniform spacing in undeformed arc length, or explicit `t` stations. The plot shows
required nodes and the selected Fourier basis against arc fraction or material
angle. **Edit displayed nodes** copies the current nodes for adding, removing or
moving stations. Apply validates the complete mesh before replacing the result;
property breaks and attachments are inserted automatically. Opening another
ASW document clears beam overrides. Property edits preserve them and validate
the new geometry. The global **Default intervals / beam** applies to beams
without overrides.

**Modified cosine in arc length** selects the fixed distribution checked
against the ISAE SA-2 printed coordinates. It reproduces the mesh used in the
passing SA-2 spacing comparison; ordinary cosine remains the default. This
option is not established as ASWING's universal default and does not resolve
all other ISAE discrepancies. See the [spacing comparison](docs/validation/isae-sa1-sa5-spacing-20261029.md).
Its API spacing name is `modified-cosine`; the
[implementation checks](docs/validation/modified-cosine-option-20261030.md)
cover retained meshes and portable settings.

Native APIs and JSON requests accept the same `panels` setting. An integer
retains cosine spacing for every beam; an object selects individual beams:

```json
{"default": 24, "beams": {
  "1": {"count": 32, "spacing": "uniform"},
  "2": {"nodes": [0, 0.1, 0.7, 1.6, 2]}
}}
```

Counts are intervals, before extra mandatory nodes. Explicit nodes must be
strictly increasing and include both ends of the logical beam’s domain, even
when the ASW property tables use decreasing `t` or a mirrored half-span.
**Export mesh / Import mesh** uses a version-1 `openswing-mesh` JSON envelope.
This is an OpenSwing analysis setting, independent of ASW property stations and
the unimplemented legacy `.set` format. Result requests, saved equilibria and
time checkpoints retain the chosen mesh. Reusing a state on different actual
nodes is rejected; time launch/restart reconstructs its original mesh.

The [material-mesh study](docs/validation/discretization.json) records circular
arc convergence for three distributions, analytic spring–mass Bode response and
poles, nonuniform full-Fourier equivalence, and saved-state launch/restart.
Reproduce it with `python scripts/verify-discretization.py`, build, then run
`node scripts/test-discretization-wasm.mjs` for the
[packaged WASM comparison](docs/validation/discretization-wasm.json).
The [convergence figure](docs/validation/discretization.svg) is also available as a
[PDF](docs/validation/discretization.pdf); regenerate it with the optional
`plots` dependencies and `python scripts/plot-discretization.py`.
Structural and aerodynamic sampling intervals are shared, with an independent
Fourier unknown count, as specified in ASWING steady formulation §3.1
(equations 62–63). Separate physical sampling meshes would be an extension;
they are not established as a requirement by that specification.

The [circulation study](docs/validation/circulation.json) varies Fourier
mode count and structural panel count independently, checks an elliptic wing
against lifting-line theory, and records the coupled heave/pitch spectra. Its
[figure](docs/validation/circulation.svg) and [PDF](docs/validation/circulation.pdf)
retain the published flying-wing discrepancies. Reproduce it with
`python scripts/verify-circulation.py`, then build and run
`node scripts/test-circulation-wasm.mjs`; the latter compares the packaged
WebAssembly results and restores native physical states. Run
`python scripts/plot-circulation.py` with the optional `plots` dependencies to
regenerate the figure. A smaller weighted residual alone does not establish
convergence: refine both the mode count and the panel count.

`CDi` and `efficiency` now mean Trefftz-plane values, with
`e=(CLi²+CYi²)/(π (Bref²/Sref) CDi)`. `CDi_near` and `efficiency_near` preserve
the earlier near-field quantities. The total-force identity is
`CD=CDi_near+CDp+CDbody+CDam+CDeng+CDrate`; it does not substitute the far-wake
drag for the near-field vortex contribution. JSON includes the coefficient
definitions, wake trace, induced velocities and per-strip drag. Ground images
require wind parallel to the image plane for this diagnostic. An intersecting
unresolved filament or negative discrete wake drag also produces an explicit
unavailable value. Time histories use a frozen current wake, without shed-wake
history. See [the numerical conventions](docs/NUMERICS.md#trefftz-plane-forces-and-span-efficiency).

For the original **Heave and pitch modal demonstrator**, use 4 panels, 50 m/s,
alpha=0, specified PG Mach=0 and gravity magnitude=0. Request 8 modes with the
fixed frame. It has a growing oscillatory pair near `0.772908 ± 32.449951 i / s`.
This is a verification model, not a validated aircraft flutter prediction.
`python scripts/verify-modes.py` compares it to independent two-dimensional
heave/pitch/circulation equations as aspect ratio increases and records inputs,
source hashes, all finite roots and numerical refinements in
`docs/validation/coupled-modes.json`.

Select a root on the Eigenmodes tab, choose a beam and physical quantity, and
inspect real/imaginary load, displacement or strain distributions. Phase playback
adds the linear complex shape to the loaded base with an explicit display scale.
It holds amplitude fixed; it is not a time simulation. The ordinary coefficient,
Span loading and Structure panes retain the base equilibrium. CSV exports roots
or the selected complex output; JSON includes every left/right vector, physical
output, state scaling and reduction diagnostics. Enable full matrices to include
`A` and `M` in `M dz/dt = A z`. Rates/frequencies use the `.asw` **input time unit**.

Vacuum omits aerodynamic loads while retaining real inertia and gravity. Engine
blocks are currently rejected in vacuum; a structural-only model can represent
rotor inertia in Weight records. Free-body zero modes can be defective and need
not admit individual left/right mass normalization. Exact coordinate integrator
equations now preserve their zero roots before the numerical eigensolve; the
root detail and CSV identify them. Other nonzero roots within the growth display
threshold are labeled **near neutral**, with their computed values retained.
That threshold is not an eigenvalue error bound. The literal material damping
law can also produce finite strain-relaxation poles; proximity to `-1/td` is
reported as a diagnostic, not proof of physical mode identity. A rejected weak
inertia/rank test requires tangent and rank refinement, not acceptance of a
smaller apparently stable spectrum. Small eigenpair residuals alone do not prove
that every physical mode was found.

The derivative matrix now extracts physical acceleration and circulation-rate
load coefficients before composing nonlinear hinge/controller laws. This avoids
false tiny inertia terms caused by subtracting nearly equal loaded residuals.
The original swept/twisted flexible-wing example now resolves its finite modes
and initial spectra at the checked meshes; true weak-inertia rejection remains.
The [descriptor-mass study](docs/validation/descriptor-mass.json) records rank,
difference-step, mesh and time-unit checks. This is numerical consistency
evidence; aircraft and mesh-convergence validation remain necessary.
The [verification figure](docs/validation/descriptor-mass.pdf) shows the
derivative-rank gap and the two loaded wing meshes. Reproduce the study with
`scripts/verify-descriptor-mass.py`, build, then run
`node scripts/test-descriptor-mass-wasm.mjs` for the packaged runtime.


## Frequency response

Magnitude plots default to **log–log** axes, with labeled decade gridlines
(0.1, 1, 10, …) and lighter minor lines. Phase uses a linear vertical axis;
linear magnitude and dB are also available. Plot frequency defaults to cycles
per input T (Hz when T is seconds), and angular responses to degrees. Use the
plot unit selectors for radians. CSV and sample details retain their labeled
native units. These display choices also apply to comparison plots and SVG
exports. Zeros are omitted on logarithmic gain axes; choose linear magnitude
to see them. See [Bode display conventions](docs/validation/bode-log-axes.md).

Choose **Frequency response · Bode**. Set the angular-frequency range in
**rad / input T**, spacing and sample count. The base uses the same operating
constraints as eigenmodes, with control settings held or governed by feedback.
Fixed-frame
response holds the aircraft frame; free flight couples the six accelerations,
body velocity/rates and Earth pose. An accelerating base is a frozen local model;
the report includes its drift. Check modes separately to assess stability.

For aircraft roll, pitch or yaw response, select **Use free-flight settings**
and run a new analysis. Fixed-frame body-rate responses are zero by constraint;
the interface explains this beside the selected result. Free flight alone does
not establish steady trim. The [Daedalus rudder project](examples/dae-rudder-project.json)
provides a saved steady, level 30 ft/s trim, eight panels per beam, PG Mach 0.1,
and a 0.1–10 Hz grid. Open it through **Project & saved cases**, then **Load case**.
Select **control.3 · Rudder → Flight frame → Yaw rate r** after solving. This is
a reproducible example, not the identified operating point in Drela's published
plot; numerical agreement and mesh convergence remain unverified. See the
[frame and trim checks](docs/validation/daedalus-rudder-frame.json) and the
[published-curve comparison](docs/validation/daedalus-rudder-sweep.svg).
The checked 8- and 16-panel meshes changed the complex yaw response by 0.51%,
1.99% and 6.73% at 0.1, 1 and 10 Hz, respectively, using the finer response as
the denominator. The remaining difference from Drela's drawing is substantially
larger at these samples, but the drawing does not specify its operating point
or mesh. These checks establish neither reference agreement nor convergence;
the [mesh report](docs/validation/daedalus-rudder-mesh.json) preserves the raw
comparison and the numerical checks separately.
Extending the saved matrices to 203 frequencies per mesh resolved all samples,
but found a maximum observed complex mesh change of 23.14% near 8.90 Hz and a
maximum magnitude change of 13.00% near 8.53 Hz. These are sampled differences,
not bounds on the continuum solution. The [frequency sweep report](docs/validation/daedalus-rudder-sweep.json)
and [CSV](docs/validation/daedalus-rudder-sweep.csv) include those results.
The [direct derivative check](docs/validation/daedalus-rudder-directional-check.md)
compares the saved matrices with fresh residual differences at the frequency
of the largest observed mesh change. All six tested directions pass at both
step sizes, including rudder forcing and frame yaw. This checks those directions
at one loaded state; it does not establish whole-matrix correctness, mesh
convergence or agreement with the published aircraft response.
The original [32-panel attempt](docs/validation/daedalus-rudder-refinement.md)
returned from trim but stopped at a moving-field derivative accuracy check.
Its saved state and failure are retained. The
[derivative recovery](docs/validation/daedalus-rudder-field-refinement.md)
allows six bounded refinement levels instead of four, keeping the same accuracy
threshold. The failing column now resolves, with an additional independent
step-size comparison; 29 native and eight WebAssembly regression cases pass.
The separate full-model follow-up completed the 32-panel matrices and responses
at 0.1, 1 and 10 Hz without repeating trim. Complex changes from 16 panels are
2.73%, 3.04% and 3.22%, respectively. The subsequent
[three-mesh sweep](docs/validation/daedalus-rudder-mesh-sweep.md) resolves all
203 frequencies on the finer mesh, reusing its matrices and three anchor
states. The maximum sampled 16-to-32 complex change is 14.28% near 7.26 Hz;
mesh convergence and agreement with the published curve remain unverified.

The [free-flight matrix optimization](docs/validation/daedalus-rudder-local-rates.md)
reduces the same saved 32-panel case's native assembly time from 227.52 to
73.46 seconds and full residual evaluations from 5,498 to 849. Every matrix
entry was compared: mass and forcing are exact, the largest state-matrix
difference is 3.35e-12, and four yaw-response comparisons pass. Fifteen focused
native and eleven WebAssembly tests pass. The local browser kernel is updated;
these timings exclude trim and frequency solves and are not browser timings.

The [operating-speed comparison](docs/validation/daedalus-rudder-speed.md)
adds a newly trimmed 16-panel case at the published design speed, 6.7 m/s.
All 203 frequencies pass their numerical checks. Its 0.1 Hz magnitude is 2.93%
above Drela's drawing, but the dip near 1 Hz still differs; the drawing's
operating point remains unknown. The [two-speed project](examples/dae-speed-project.json)
contains both physical trims with 101 logarithmic UI frequencies. This is a
sensitivity study, not matched-reference validation. Saved-state correction
now reports its iterations, matrix assembly and final checks; the
[progress checks](docs/validation/equilibrium-progress.md) confirm unchanged
numerical results in native Python and WebAssembly.

The [cruise-speed mesh comparison](docs/validation/daedalus-rudder-cruise-mesh.md)
now includes all 203 responses at 32 panels. Refinement changes the complex
response by only 0.462% at 1 Hz, leaving the reference dip unresolved; the maximum
sampled mesh change is 22.87% near 6.65 Hz. Import the
[paired cruise-mesh project](examples/dae-cruise-mesh-project.json) to load either
physical trim. A separate [fixed loaded-shape diagnostic](docs/validation/daedalus-rudder-fixed-shape.md)
confirms that elastic coupling matters, without establishing ASWING parity.
The [near-1 Hz coupling checks](docs/validation/daedalus-rudder-coupling.md)
confirm selected matrix derivatives against fresh nonlinear residuals and
separate the signed wing/rudder contributions. The printed body added-mass
coefficient changes the 1 Hz response by only 0.037%, leaving the dip unresolved.
These diagnostics do not change production physics or establish reference agreement.
The [independent component checks](docs/validation/daedalus-component-checks.md)
add a loaded boom–fin continuum comparison and twelve wing–fin aerodynamic
transfer cases. Structural refinement reduces the largest scaled motion error
from 0.341% to 0.0206%; the tested aerodynamic transfers also agree with the
independent reference. The full Daedalus yaw-curve discrepancy remains open.
The [loaded-motion follow-up](docs/validation/daedalus-loaded-motion.md) also
passes twelve nonzero-circulation translating-fin comparisons. Two isolated
rotational-velocity conventions change the 1 Hz aircraft response by only
0.068% and 0.308%; neither explains the reference minimum. All fourteen selected
responses pass their numerical checks. Production physics remains unchanged.
The [loaded rotating-fin comparison](docs/validation/daedalus-rotating-motion.md)
adds twelve independent cases with changing span/normal, profile force/couple
and physical moment-arm transport. All pass, with a separate 2,882-check saved
audit. This verifies the declared component convention; full-aircraft agreement
and higher-frequency mesh convergence remain open.
The [loaded propeller–fin follow-up](docs/validation/loaded-jet-coupling.md)
checks nonlinear circulation/inlet/jet feedback under prescribed motion.
Eleven four-interval and twelve eight-interval cases complete both probe widths;
one additional four-interval case passes a separate output-width refinement.
The original coarse-probe failure is retained. Four focused regressions pass;
these component checks do not resolve the aircraft response discrepancy.

Choose declared flap/engine inputs, harmonic gusts, or frame loads and
accelerations. With prescribed, free or mixed motion, the frame-input choice generates one
input for each axis: its active net-load target or its prescribed acceleration.
Each input is solved
with unit physical amplitude. Gust direction uses Earth coordinates and is
normalized. Cosine span modes include n=0; sine modes start at n=1. Their
wavenumber is `2πn / reference span`. The transverse direction is the loaded
body y direction projected perpendicular to the flight path. A convected Earth
field satisfies `ω = k · U_E`; uniform streamwise forcing is also available.
The input origin, normalized directions and each frequency's complex spatial
profile are exported. A coarse element phase increment triggers a refinement
note. The empirical gust model is not exact Sears/Theodorsen aerodynamics.

For the **Forced spring–mass demonstrator**, select 4 panels, 10 m/s, alpha=0,
fixed PG Mach=0 and gravity magnitude=0. Choose declared controls only, then
sweep 0.1–100 rad/s. Select Structural nodes → displacement y at the tip.
The exact unit-setting transfer is
`1 / [500*(1 + i*.02*ω) - 2*ω²]` metres. The ordinary Engine record supplies a
force of one newton per setting unit; the example needs no custom file syntax.
Resolve the resonance near 15.4 rad/s with a finer frequency range.

The Bode tab selects an input, output and station; magnitude can be shown directly
or as `20 log10` in dB relative to one numerical output unit per input unit.
Phase can be wrapped or unwrapped. Click a frequency marker or choose a sample
for geometry playback. **Input amplitude** is in the selected channel's physical
units; geometry is not normalized to a percentage of span. Phase playback holds
amplitude fixed and cycles for inspection, independent of physical frequency.
The ordinary coefficient, Span loading and Structure views retain the base.
CSV exports the selected complex transfer and gain/phase; JSON contains all
computed vectors/outputs and optional `A`, `M` and frequency-dependent `B`.

The full descriptor pencil is solved, including algebraic response and direct
loads; no modal truncation or pseudoinverse fills missing points. A free-flight
zero-frequency solve is commonly singular because position and attitude integrate
velocity/rates. Those points remain explicit gaps. Zero gain has undefined dB
and phase. Refine the mesh, frequency range and difference step before interpreting
resonances. Arbitrary legacy control routines,
general inverse dynamic targets, saved-grid extension and exact companion-format
compatibility remain pending.

### Initial-disturbance spectra

Open **Initial disturbances** and import a JSON array of physical profiles, or
enter it in the editor. Profiles are added to the selected harmonic channels;
choose **Initial disturbances only** to use them alone. Each profile is a real,
infinitesimal perturbation from the loaded equilibrium, with its own dimensionless
amplitude. For the **Instrumented spring–mass demonstrator**, use 4 intervals,
10 m/s, alpha=0, fixed PG Mach=0 and gravity=0, then import
[initial-spring.json](examples/initial-spring.json). The two profiles release a
0.002 m axial displacement and a 0.01 m/s axial velocity, respectively.

```json
[
  {
    "kind": "initial",
    "name": "Released axial displacement",
    "state": {
      "beam_fields": [
        {"beam": 1, "displacement": [[0, 0, 0, 0], [2, 0, 0.002, 0]]}
      ]
    }
  }
]
```

`beam_fields` linearly interpolates each `[t,x,y,z]` table onto the current
material nodes. Tables must include the exact first and last beam parameters;
there is no implicit reflection. Available fields are body-axis `displacement`,
spatial `rotation`, local elastic `velocity` and `rates`. Rotations are in radians,
rates in rad/input T, and other values use the ASW file's units. Alternatively,
`nodes` accepts exact current stations, for example
`{"beam":1,"t":2,"velocity":[0,0.01,0]}`. Duplicate field assignments are rejected.

The same state can include a physical panel `circulation` array, `frame` fields
(`velocity_origin_body`, `rates_body`, `position_earth`, `attitude_rad`), and
`feedback` dictionaries (`integrals` by signal name, `states` by custom state
name). Frame attitude contains bank/elevation/heading increments in radians;
frame fields require a moving-frame analysis. Fourier circulation must lie in
the selected basis. Omitted dynamic fields are zero. The solver completes loads,
reactions, dynamic accelerations and actual actuator increments, and rejects
profiles inconsistent with algebraic or differentiated constraints.

With `s = σ + iω`, the solver computes
`X(s) = integral_0^infinity δx(t) exp(-s t) dt`. Every output spectrum therefore
has one extra input time unit. The **Laplace damping σ** setting must exceed the
largest real part of the complete resolved finite spectrum, plus a numerical
margin. Leave σ=0 only for a decaying system; neutral/free-flight or unstable
systems require positive σ. This conservative check applies to the full system,
even if a particular profile would avoid a nondecaying mode. Refine rank tolerance
and difference step when a weak inertia or constraint rank is unresolved; do not
interpret rejection as stability evidence.

Rate-dependent outputs use `s X - x0`, including initial acceleration, damping,
apparent mass and controller rate terms. The initial physical output and completed
descriptor state/rate are included in JSON. The Bode view provides magnitude,
phase and **Spectrum CSV**; geometry shows the loaded base because a transform
value is not a periodic motion. The same physical schema also supports selected-mode ROM free responses and
compatible nonlinear disturbances from a saved equilibrium. It is not a legacy
ASWING file format.

Reproduce the independent mechanical/controller, free-flight and circulation
study with `scripts/verify-initial-response.py`, build the app, then run
`node scripts/test-initial-response-wasm.mjs`. The source-hashed records are
[initial-response.json](docs/validation/initial-response.json) and
[initial-response-wasm.json](docs/validation/initial-response-wasm.json).
The [standalone verification figure](docs/validation/initial-response.pdf) plots
the oscillator spectra and the acceleration boundary term.

### Matched broken-loop display

Choose **Display → Broken loop · 1 − u/x** for the guide's alternative gain
and phase plots. The response x is automatically paired with the input u:
actual flap/engine setting, the commanded measurement, net force/moment, or
prescribed acceleration. Both use the same physical units, so the displayed
ratio is dimensionless. The other command increments are zero. Gust inputs
have no corresponding aircraft response for this definition and show a gap.
Zero x also gives a gap; zero `1 − u/x` has no defined phase or dB value.

This implements the documented scalar display; it does not open a controller
equation or compute a unique multivariable return ratio. Other loops keep their
solved configuration. Very small nonzero x/u is retained and can amplify
numerical error strongly. Use numerical refinement and a suitable control
analysis before drawing stability-margin conclusions. Geometry and the saved
physical response retain x/u. The Bode CSV identifies the selected display,
formula, matching output, units and gaps; JSON includes both ratios.

`python scripts/verify-broken-loop.py` records eight mechanical/control cases,
including coupled actuators, acceleration feedback, actuator lag, difference-step
refinement and input-time scaling in `docs/validation/broken-loop.json`.
After building, `node scripts/test-broken-loop-wasm.mjs` repeats them with the
packaged runtime and verifies its sources against the study hashes. The checked-in
broken-loop study retains its earlier kernel hashes; regenerate it before testing
that study against a later kernel.

`python scripts/verify-frequency.py` records independent oscillator and coupled
heave/pitch/lag comparisons, the inputs, source hashes and numerical errors in
`docs/validation/frequency-response.json`. This checks the implemented equations;
it does not establish experimental or ASWING executable parity.

## Moving sensors

Use the documented `Sensor` block, with one row per instrument:

```text
Sensor
! index beam t    Xp Yp Zp    Vx Vy Vz    Ax Ay Az
  1     1    2    .3 2  .2    1  0  0     0  0  1
End
```

`Xp,Yp,Zp` is the undeformed pylon tip in body axes, attached at beam station
`t`. The two axis specifications determine aft-positive V, right-positive beta
and up-positive alpha axes; they are normalized and orthogonalized. Omitting
both vectors uses the body-axis directions. Zero or parallel individual vectors
are rejected. Choose **Instrumented spring–mass demonstrator** for a complete
example with two moving sensors and a force actuator.

**Sensor airflow** selects the full implemented induced/jet/gust field or
kinematic flow alone; this choice changes sensed airflow, not aircraft loads.
The native API uses `FlightCondition(sensor_flow='full')` or `'kinematic'`.
Sensor airspeed and flow angles use the pylon-tip relative velocity. Rate gyros
measure absolute rotation rate. Accelerometers measure specific force `a-g`:
level flight reads upward g, while free fall reads zero. GPS position/velocity
are Earth coordinates of the pylon tip. Body-relative position/velocity and
structural forces/moments refer to the beam anchor. All values use input units;
flow and attitude angles are degrees, rotation rates are radians per input T.

At an interior anchor the reported force/moment uses the left section trace;
the first endpoint uses the right trace. Both adjacent traces are retained in
JSON, in the anchor's c/s/n axes. Strain and shell stress use the selected
adjacent material midpoint, with its sample location and axes explicitly
reported; circulation also reports its sample location. Rigid-only aerodynamic
solves do not invent structural loads. Vacuum time/mode analyses retain inertial
and GPS measurements, with airflow unavailable.

The Sensors tab follows the selected time state, mode or harmonic input/sample.
Complex values use the saved mode normalization or unit forcing amplitude,
independent of geometry playback scale and phase. Time history, Eigenmodes and
Bode offer sensor quantities directly. Zero airflow has undefined flow angles;
a vertical sensor V axis has undefined bank/heading. Near-filament flow,
reverse-flow angle conventions and discontinuity trace choices still need ASWING
reference comparisons. Selected sensor-command histories, differential error integrals and scheduled
feedback are supported. `.con` tables require explicit channel/unit bindings;
default INDEXC compatibility and arbitrary legacy control routines remain incomplete.

`python scripts/verify-sensors.py` records beam-deflection and free-fall sensor
refinement with source hashes in `docs/validation/sensors.json`. Additional tests
check moving-frame transport, induction and complex acceleration/gust response.

## Feedback control

Mounted equilibrium, Time, Eigenmodes and Bode analyses accept an optional controller. Open
**Feedback control**, enable it, and edit or import the JSON definition. The
**Spring–mass PI example** button supplies the same definition as
`examples/position-controller.json` for the instrumented oscillator. Use
4 panels, 10 m/s, alpha=0, fixed Mach=0 and gravity magnitude=0 for its independent
mechanical reference. Its law is

```text
E1 = commanded E1
     - 200 * (RY[2] - commanded RY[2])
     - 20  * (UY[2] - commanded UY[2])
     - 100 * integral(RY[2] - commanded RY[2])
```

The pylon GPS position `RY[2]` is in Earth Y; `UY[2]` is its Earth Y velocity.
The ordinary Engine record converts one setting unit to one newton along body y.
Commands default to the initial measured values and actuator settings. Add a
`commands` object to change a reference, or use a time table such as:

```text
time +RY[2]
0    0
.03  0
.03  .01
.10  .01
```

This requests a 0.01-input-L position increment after t=.03. The doubled time
retains the left state and restarts integration with the right command. In Bode,
enter `RY[2]` under **Bode measurement commands** to add a unit reference input.
Declared actuator inputs remain available; a controlled actuator's input changes
its commanded setting while the feedback loop stays active. Controller outputs
and integrals appear in **Controller**, time histories and the Bode output-group
selector, with CSV/JSON exports. Modal controller values use the saved right
eigenvector; phase playback does not change saved values.

Each output specifies an `actuator` (`F#` or `E#`) and a list of terms. A term
has `input`, `gain` and optional `mode`: `error` (default), `integral` or
`value`. Errors are measured minus commanded. Named angular channels use degrees,
angular rates degrees/input T, and angular accelerations degrees/input T².
Sensor channels use `[index]`, e.g. `Az[2]` for specific force or `Wy[2]` for
rotation rate. Global `Ax/Ay/Az` mean absolute acceleration at the file reference;
sensor accelerometers subtract gravity. `V` and `V[index]` currently mean true
reference/local airspeed; exact ASWING indicated-speed conventions remain open.
Angle errors take the shortest signed branch. Commands on that branch cut and
singular attitudes cannot define a unique modal tangent.

A gain can be a number or a bilinear table:

```json
{"speed":[10,20],"density":[1,2],"values":[[-2,-1],[-4,-2]],"outside":"error"}
```

Rows correspond to density, columns to true airspeed, in file units.
`outside` explicitly selects rejection, `linear` extrapolation or endpoint
`hold`. State-dependent scheduled gain participates in the Jacobian. No
actuator saturation, dynamics or anti-windup is silently supplied.

For time startup, `initial_integrals` defaults to zero and remains prescribed
while the initial structure/actuators equilibrate. Integral derivatives can then
be nonzero. Steady and modal/Bode bases instead solve zero integral derivatives
together with the controller, network and selected operating targets.
`initial_integrals` are guesses in those steady solves. Default commands come
from the loaded structure at the prescribed operating settings, before trim;
an open-loop trimmed solution is not required. Incompatible commands or redundant
integral/trim equations cause a failed equilibrium.

In **Operating constraints**, select **Command F1**, **Command E1** or a selected
measurement command as the variable to solve. For example, the PI spring–mass
model can solve **Command RY[2]** for **Net force y = 5**. Its result is position
command 2.01, engine setting 5 and integral -0.05 in file units. The native target
is `{"variable":"command.RY[2]","quantity":"force.y","target":5}`.
The controller owns its actual actuator, so selecting that same actuator as an
ordinary trim unknown is rejected with the corresponding command name. A PI
controller can make some command/target choices redundant; the final full
tangent is checked even when its residual is initially zero.

Modal/Bode analysis preserves the solved geometry, motion, integrals, actuator
settings and commands, then releases trim targets according to its fixed/free
dynamic frame. Solved commands are held constant; actual actuators remain
dynamic algebraic unknowns. The original target results are exported in
`base.steady_trim`. Time startup retains its prescribed/free-flight frame;
arbitrary dynamic initial-state construction and arbitrary legacy
control-subroutine compatibility remain unfinished. Closed-loop static
derivatives retain controller equilibrium equations and release trim targets.

`python scripts/verify-control-trim.py` records mechanical command trim, released
closed-loop spectra/transfers and aerodynamic lift/pitch trim at multiple meshes
in `docs/validation/control-trim.json`. Its mechanical and section-moment
references are independent; the aerodynamic lift comparison uses the same
lifting-line kernel and does not establish ASWING numerical parity.

The native APIs, including `solve_static`, accept `controller=definition`. Original `.con` gain-table
syntax is also read, including scale factors, two grids and arbitrary table
blocks. Importing a `.con` file preserves its text in a definition with
`con` and `bindings`. Bindings explicitly identify every output index and every
`"sensor:input"` pair, including unit conversion factors:

```json
{
  "outputs":{"2":{"actuator":"F2","factor":1}},
  "inputs":{"0:8":{"input":"Ey","factor":0.0174532925199433}},
  "outside":"linear"
}
```

Here the input factor converts the named degree measurement to a table input in
radians; the output factor must match the model's actuator-setting unit.
An integral binding adds `"mode":"integral"`. The
[published manual](https://web.mit.edu/drela/Public/web/aswing/ASWING_Extended_User_Manual.pdf) identifies
global j=8 as pitch and j=6 as yaw rate; a
[public controller example](https://github.com/LeonardoAVONI/WingLoop/blob/main/WingLoop_Library/wingloop_testrun/aswing_geometry/00_Pitch_PID.con) also
identifies j=14 as pitch-error integral and j=5 as pitch rate. Other indices and
default output-unit maps are not guessed. Explicit bindings provide an
auditable import, not complete default `INDEXC.INC` compatibility.

`python scripts/verify-feedback.py` writes independent pole/transfer comparisons
and PI time refinement to `docs/validation/feedback.json`, including source
hashes. Broader flexible-aircraft feedback, custom routine compatibility and
ASWING/experimental closed-loop validation are still required.

## Custom nonlinear controllers and internal states

Each output can use a scheduled `terms` list, a target `expression`, or an
implicit `residual`. Select exactly one. An expression returns the complete
desired actuator setting, including any commanded bias you want to use. A
residual returns a scalar equation that must be zero and may read several actual
actuator settings. Its optional positive `residual_scale` normalizes that
equation; otherwise the actuator scale is used. All equations participate in the
same implicit solve as the aircraft, including acceleration feedback.

The **Actuator-lag example** button loads `examples/actuator-lag-controller.json`:

```json
{
  "parameters": {"kp": 200, "kd": 20, "tau": 0.05},
  "outputs": [{"actuator": "E1", "expression": "state('lag')"}],
  "states": [{
    "name": "lag", "initial": 0, "scale": 10, "unit": "file engine setting",
    "rate": "(command('E1')-parameter('kp')*error('RY[2]')-parameter('kd')*error('UY[2]')-state('lag'))/parameter('tau')"
  }]
}
```

This adds a first-order actuator lag of .05 input T to the original spring–mass
demonstrator. Internal states require a distinct name, positive characteristic
scale, unit label and rate expression; initial values default to zero. State
rates are per input T. Time startup holds those initial values while solving
the algebraic/structural equations. Steady and modal/Bode bases solve zero state
rates, treating the initial values as guesses. State values and rates appear in
Controller tables, time histories, modal/Bode outputs and CSV/JSON exports.

Expressions can read these literal-name functions:

| Expression | Value |
|---|---|
| `measurement('RY[2]')` | Current selected measurement |
| `error('RY[2]')` | Measurement minus command, with the named angle-error convention |
| `integral('RY[2]')` | Built-in integrated error; its differential state is created automatically |
| `command('RY[2]')`, `command('E1')` | Measurement command or controlled-actuator bias |
| `actuator('E1')` | Current actual setting, including another declared actuator |
| `state('lag')` | Custom internal state |
| `parameter('kp')` | Named constant or the same bilinear speed/density gain-table format |

Use `speed`, `density`, `time` and `pi` directly. Arithmetic supports `+ - * / **`
and unary signs. Functions are `sin`, `cos`, `tan`, `asin`, `acos`, `atan`,
`atan2`, `tanh`, `exp`, `log`, `sqrt`, `abs`, `minimum`, `maximum`, `clip`, and
`where(condition, yes, no)`. Comparisons are `< <= > >= == !=`; each comparison
has two operands. `where` evaluates only its selected branch, including scheduled
parameter lookups. Trigonometric functions use radians; named angular
measurements use degrees, so convert explicitly with `pi/180` where needed.
References require literal quoted names. Attribute access, indexing, loops,
imports and arbitrary Python execution are unavailable. Each expression is
limited to 4096 characters and 512 syntax nodes.

All coefficients, measurements and states use consistent file units. Unit
labels describe states; they do not convert values or perform dimensional
analysis. Ordinary flap/engine inputs supply actuator command biases; the
definition's `commands` object sets measurement references.
`examples/antiwindup-controller.json` supplies an explicit ±5 actuator
limit with back-calculation anti-windup. Saturation and anti-windup are never
added automatically. Piecewise laws require time-step refinement. Modal/Bode
checks compare one-sided control-residual tangents in state, rate and forcing
directions; a switching boundary or an overly large difference step can prevent
a valid linearization. Smooth composite expressions such as `abs(error(...))**2`
remain usable. Time-dependent laws are frozen at the selected base time for
modal/harmonic analysis; this does not establish stability along a time-varying
trajectory.

`python scripts/verify-custom-control.py` records independent actuator-lag
spectra/transfers, matrix-exponential transients, saturated equilibria and
piecewise nonlinear ODE comparisons in `docs/validation/custom-control.json`.
The expression interface is an OpenSwing extension for named channels and
custom differential states. It does not interpret legacy Fortran routines or
expose every internal ASWING array. Full control-file and aircraft/experimental
parity remain part of the unfinished goal.

## Selected-mode reduced-order models

After an aerodynamic **Coupled eigenmodes** analysis, open **Reduced-order
model** in the Eigenmodes tab. Select any of the returned modes and input
channels, name the output measurements, and enter comparison frequencies in
rad/input T. A selected complex mode automatically includes its conjugate.
The real matrix model is evaluated alongside the full descriptor at every
requested frequency. The table reports complex responses and absolute errors;
the plot and normalized error use the selected output's physical units.
Changing ROM settings invalidates its exports, while modal phase playback does
not change either the saved modal result or the ROM.

Inputs include declared flap/engine settings, active controller measurement
commands, and uniform Earth-axis gusts. The Python/JSON API also accepts fixed
spatial cosine/sine gust families using the harmonic input format with
`wave: "uniform"`. Convected gusts have frequency-dependent phase and cannot
currently be exported as constant real input matrices. Use the full Bode
analysis for those inputs. Outputs use the named measurement syntax described
under feedback, such as `V`, `Az`, `RY[2]`, `UY[2]`, `Ay[2]`, `Ey[2]` or
`Fc[2]`. All angular measurement outputs are in degrees; all other quantities
use their stated file units. Sensor accelerometers measure specific force.

Open **Beam loads, deformation and aerodynamic outputs** to add node motion,
section forces/moments/strain/stress, strip circulation and loads, or global
forces and coefficients. Choose a quantity, beam and sample, then **Add output**.
The sample stays bound to its beam and material coordinate on this solved mesh;
unavailable quantities are omitted. Explicit rotation and elastic-incidence
outputs use radians. These choices can be combined with named measurements or
used alone by clearing the measurement text box. Saved computed solutions retain
the selected outputs and the original matrices.

Physical outputs retain direct control/gust and state-rate contributions.
JSON and matrix text include selectors and units; annotated `.rom` exports use
SI units with explicit OpenSwing sample labels. A model with derivative-input
output terms requires JSON or matrix text because the observed legacy layout
cannot represent those terms. See the [physical ROM output study](docs/validation/rom-outputs.md)
for independent spring, lifting-line and coupled heave/pitch references.

For example, the bridge accepts:

```json
{
  "action": "rom",
  "source": "... complete .asw text ...",
  "panels": 4,
  "condition": {"speed": 10, "alpha": 0, "mach": 0},
  "gravity": [0, 0, 0],
  "rom": {
    "count": 2,
    "selected": [0],
    "inputs": ["power.1"],
    "outputs": ["RY[2]", "UY[2]", "Ay[2]"],
    "frequencies": [0, 1, 10, 50]
  }
}
```

`count`, `shift`, `method`, `frame`, `step` and `rank_tolerance` define the modal
search; `selected` contains distinct zero-based indices in that result. Omit
`selected` to retain all returned modes. The original .asw, operating conditions,
trim constraints and controller definition determine the common loaded base.
The browser reuses the saved modal request when generating its ROM.

Open **Initial disturbances and free response** to import the same physical
profile JSON used by Frequency response (for example,
`examples/initial-spring.json`). Enter times in input T and Laplace damping
in 1/input T, then rebuild. Profiles can accompany periodic inputs, or you can
deselect all periodic inputs and compare free motion alone. The API options
are `initial_inputs`, `initial_times` and `initial_shift` inside `rom`.

Each profile is checked against the complete finite system before projecting
it with the left mass-dual map. JSON includes the completed physical state,
the ROM initial coordinates, represented and omitted states, and full/reduced
output histories and spectra. The browser shows signed histories or spectral
magnitudes, complex comparison tables and CSV downloads. The reported omitted
norm uses scaled dynamic coordinates; it is not an energy fraction. An invalid
profile is reported separately without hiding valid profiles or driven results.

The full system's growth bound controls spectral convergence, including modes
omitted from the ROM. A rejected spectrum leaves finite-time histories
available. These are frozen linear free responses about the modal base;
nonlinear launch separately completes compatible physical profiles from a saved equilibrium. Matrix text records
the initial states; legacy `.rom` exports contain the driven matrix model.
The [initial-condition study](docs/validation/rom-initial.json) compares
independent oscillator/controller solutions, deliberate truncation, time units,
mesh/step changes and a loaded-wing modal identity.
The [standalone comparison figure](docs/validation/rom-initial.pdf) shows two
examples where truncation misses important initial motion. Reproduce the study
with `scripts/verify-rom-initial.py`, then build and run
`node scripts/test-rom-initial-wasm.mjs` for the packaged runtime.

The exported real matrices satisfy `zdot=A*z+B*du` and
`dy=C*z+D*du+D_rate*d(du)/dt`, with baseline outputs saved separately. The state
maps satisfy `dx=state_lift*z+state_input_lift*du`. A checked algebraic input
contribution preserves direct reactions and accelerations; homogeneous modes
alone do not contain these forced responses. `D_rate` makes any sensor
derivative-input feedthrough explicit. Full state scaling, selected poles,
units, baseline geometry, comparison data and request provenance are in the
JSON export. Matrix text is a compact companion; retain the JSON for full
state-layout and base metadata. Both are versioned OpenSwing formats.
The **ASWING .rom** button also exports the annotated complex-mode layout
observed in published ASWING files. It converts time and dimensional
measurements to SI, retains angles in degrees and flap/engine settings in their
stated file units. Physical command/gust inputs convert to SI; their names and
global Earth-velocity names are explicit OpenSwing extensions. Material
derivative-input feedthrough cannot fit this file layout; in that case only
JSON and matrix text are offered. Full state maps and the operating baseline
remain in the JSON.

Dependent/defective modes and unresolved derivative-input constraints produce
errors. Mode truncation can omit unstable or important fast modes; a successful
matrix export is not evidence of control-design validity. Refine the mode set,
mesh, difference step and frequency range. `scripts/verify-rom.py` records
spring–mass harmonic/step references and coupled heave/pitch/circulation
comparisons in `docs/validation/reduced-model.json`. These original references
do not replace published ASWING or experimental aircraft validation.

## Read an existing .rom file

Open **ROM files**, select an annotated ASWING `.rom`, and enter angular
frequencies in rad per printed time unit. This viewer works independently of
the current aircraft and entirely in the browser. It shows printed poles,
selected eigenvector/output coefficients, magnitude/phase and real A/B/C/D
matrices. A complex representative supplies its conjugate; real poles
contribute once. Singular frequencies appear as gaps. Download the original
file, a normalized `.rom`, or the complete imported result as JSON.

Original labels, printed units and coefficient values are preserved. Missing
physical input units remain unspecified. Known differences between eigenvalue
and input-rate time units are reconciled for the response, with printed data
unchanged. Files with ambiguous conjugate duplication, incompatible complex
real-pole residues, complex direct matrices or incomplete tables are rejected.

The JSON bridge accepts the following request without an `.asw` source:

```json
{"action":"rom_import","text":"... complete ROM text ...","frequencies":[0,1,10,100]}
```

The bundled
`examples/mechanical-reference.rom` is an original two-input analytical example.
`scripts/verify-rom-file.py` checks nine pinned public files from the
[ISAE validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation)
and four independent/generated mechanical cases; source hashes and results
are in `docs/validation/rom-file-sources.json` and `rom-file.json`.
These checks establish the observed annotated layout and literal matrix
response. ASWING's additional Bode reconstruction, older formats, executable
interoperation and full aircraft/experimental agreement remain unverified.

## Stability progression and instability boundaries

After a coupled eigenmode solve, open **Stability progression and boundaries**
in the Eigenmodes tab. Enter an increasing list of speeds (input L/T), or
another supported operating parameter. The sweep reuses the saved aircraft,
mesh, constraints, controller and eigenvalue search settings. The browser defaults
to warm continuation from the saved modal equilibrium, then the nearest solved
lower-parameter point. Each point solves the full equilibrium equations and
linearizes its own loaded state. Disable continuation for independent cold solves. The original modal result remains
available while the sweep runs; **Inspect point modes** selects a computed
point for shape playback, physical outputs and ROM generation. Further sweeps
use the original saved modal request until another main analysis is run.

Root paths show one representative per complex conjugate pair and each real
root once. Matching uses mode shape and predicted eigenvalue movement, with a
one-to-one assignment. Ambiguous matches, roots entering/leaving the returned
spectrum, and failed solves produce explicit gaps. No path or instability
bracket is inferred across a gap. The display distinguishes full finite-spectrum
coverage from a limited count/shift search. Even full coverage at the sampled
points can miss instability between them.

When a tracked root changes the sign of its real part, optional refinement
narrows the parameter bracket and checks that a computed growth rate approaches
zero. The table distinguishes oscillatory candidates, aperiodic instability,
stabilizing crossings, unresolved brackets and unrefined brackets. Reported
values are computed points, not interpolated predictions. Near a parameter
value of zero, provide an absolute parameter tolerance as well as the relative
tolerance. An oscillatory crossing may be a flight-dynamics, control or material
damping instability; inspect its mode before interpreting it as flutter.

Export **Sweep JSON** for every computed equilibrium, mode, diagnostic,
assignment and failed point, or **Root paths CSV** for the tracked grid paths.
Changing sweep settings invalidates those exports; phase playback does not.
The JSON API accepts, for example:

```json
{
  "action": "stability",
  "source": "... complete .asw text ...",
  "condition": {"speed": 40, "alpha": 0, "mach": 0},
  "panels": 4,
  "gravity": [0, 0, 0],
  "modes": {"count": 8, "step": 0.000001, "rank_tolerance": 1e-9},
  "stability": {
    "warm_start": true, "adaptive": true,
    "max_subdivisions": 4, "max_extra_points": 16,
    "parameter": "speed", "values": [40, 45, 50], "refine": true,
    "parameter_rtol": 0.0001, "parameter_atol": 0,
    "growth_tolerance": 0.000001, "max_iterations": 24,
    "min_assurance": 0.6, "ambiguity_margin": 0.05, "max_distance": 1
  }
}
```

Parameters include `speed`, `alpha`, `beta`, `altitude_m`, `density`, declared
`control.N`/`power.N`, and zero-based `target.N` entries in the supplied operating
constraints. A swept prescribed variable must not also be a trim unknown.
Direct actuator sweeps with feedback require an explicit command/bias treatment
and are currently rejected; speed/target sweeps retain the full controller.
Flight-condition sweeps currently require aerodynamic modal bases.

The workflow follows the operating-point progression described in the
[ASWING MODE guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt).
`scripts/verify-stability.py` records independent heave–pitch/circulation and
scheduled-feedback comparisons in `docs/validation/stability.json`.
Select **Subdivide uncertain tracking intervals** to insert midpoint solves when
an assignment is uncertain or a local correction fails. Depth and extra-point
budgets bound the work. Warm endpoints are recomputed after intermediate states
are inserted. Superseded attempts remain in JSON with `superseded_by`; only the
final attempt at a value contributes to convergence and coverage. Unresolved
intervals remain gaps. Exactly tied assignments are rejected even when the
configured ambiguity margin is zero. Python/JSON defaults keep `warm_start` and
`adaptive` false for reproducibility with earlier requests.

Local correction does not prove nonlinear branch uniqueness or follow folds.
Adaptive search windows, generalized invariant-subspace tracking, project/case
persistence and ASWING/experimental flutter agreement remain open.


## Save and reuse a steady equilibrium

Open **Saved equilibrium** to save the latest static/modal/Bode base as
OpenSwing JSON. **Use computed equilibrium** makes that state the initial guess
for the next solve; changing conditions or trim targets then recomputes the full
loaded equilibrium. You can also load the small state file or a complete static,
modal or Bode result containing it. Mode phase playback never alters this state.
The file and checkbox apply to mounted equilibrium, eigenmodes, Bode and time response; ROM
generation uses the selected modal base automatically.

The source text and mesh must match exactly, including comments and the aircraft
name. Incompatible files, meshes, controller state layouts and nonfinite states
are errors. There is no remeshing or silent fallback to an undeformed solve.
Physical positions, rotation vectors, internal loads, support reactions and
circulation are re-encoded using the new solver scales. Trim guesses use saved
physical values. Controller actuator, integral and custom states are preserved;
unspecified commands retain their solved values, while explicitly prescribed new
commands and changed actuator biases take precedence.

```python
from openswing.network import solve_static
first = solve_static(model, condition, panels=8)
# Keep the same model and mesh; change the prescribed condition or targets.
continued = solve_static(model, changed_condition, panels=8,
                         initial_state=first['equilibrium_state'])
```

For JSON static requests, put `initial_state` at the request top level. For
`modes`, `frequency` and `rom`, put it inside the corresponding options object.
A stability request accepts it inside `stability` with `warm_start: true`.
The version-1 `openswing-equilibrium` format stores a steady state and, in new exports, its launch setup.
It is not an ASWING `.pnt`/`.set` file or a time-history restart. Local Newton
correction and a final tangent check are required for steady reuse; no nonlinear branch
uniqueness, fold continuation or restart equivalence is claimed. Numerical
checks are described in [the continuation notes](docs/NUMERICS.md#physical-equilibrium-continuation).


Reproduce the physical-state/adaptive tracking evidence with
`OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify-continuation.py`.
After building, `node scripts/test-continuation-wasm.mjs` checks the packaged
kernel, including a native-generated finite-rotation state from that study.
The study retains the old stability artifact's original hashes as a historical
regression baseline and records separate hashes for its current generating code.


## Run equilibrium in bounded jobs

The JSON solver API can pause an eligible mounted or structural load
continuation after a chosen number of **accepted load steps**:

```python
from openswing.bridge import dispatch
request['continuation'] = {'max_load_steps': 3}
result = dispatch(request)
while result.get('continuation_status') == 'pending':
    # Save this JSON checkpoint before starting the next small job.
    request['continuation']['checkpoint'] = result['checkpoint']
    result = dispatch(request)
```

A pending result has `converged: false` and no `equilibrium_state`. It is not
ready for time launch or native-result comparison. The checkpoint retains the
load factor, exact normalized coordinates and their physical scales, unwrapped
hinge charts, next increment and cumulative rejection budget. Resume requires
the same source, kernel, mesh, flight/load settings and solver controls, then
rebuilds the saved boundary's full physical residual and rechecks unloaded rank.
Every subsequent load step starts with a fresh matrix. The original nonlinear
equations, line search, rotation guard and convergence target remain in force.

This opt-in API covers the structured steady route with prescribed conditions
or canonical acceleration/load constraints. Controllers, warm guesses,
derivative requests and other operating equations are rejected for bounded
jobs; their ordinary solve routes remain available. The main workbench still
uses the ordinary complete-solve request. A job's accepted-step budget is not a
wall-clock deadline. Native automation should also retain an external process
limit and resume only from an accepted checkpoint. The
[`openswing-static-continuation` format](docs/validation/isae-ffwt4-continuation-20261106.md)
is an OpenSwing restart format, separate from ASWING `.pnt` and time checkpoints.

## Continue a time history

In the Time response tab, open **Continue a computed trajectory**. Scrub to the
state to continue, then select **Use selected state**. Set an additional duration
and maximum step, and choose **Continue loaded state**. The saved trajectory's
source, mesh, controller, frame and physical state define the continuation.
Earlier snapshots remain in the result; later snapshots are replaced by the new
branch. The reported retries belong to the new segment. Changes to ordinary
setup controls require a new main analysis; continuation settings are separate.

**Save selected checkpoint** downloads a standalone OpenSwing JSON file.
**Load checkpoint** accepts it or a full time result (using its last state), and
creates a new segment starting at the saved absolute time. It requires the same
ASW source. The checkpoint includes elastic velocities and rotations, internal
loads/reactions, circulation, frame motion/pose, actuator/integral/custom states,
the BDF predecessor and the next step size. A changed LU factorization may
change roundoff or Newton iterations; continuation is checked to numerical
tolerance rather than promised bit for bit.

The original forcing table and its relative (+) reference settings are retained.
Values become zero after the last sample. **Replace the future forcing table**
accepts a table starting no later than the checkpoint time; an empty replacement holds the
saved setup's prescribed settings. Replacing the table resets BDF history for
the next step. The initial state remains the physical state before this input
switch. At a doubled-time event, the saved state uses left-hand forcing and its
next step uses right-hand forcing (BDF methods restart with BDF1; Radau does not
need a predecessor). Retained prefix snapshots keep their
own checkpoint settings if the future table or numerical settings change.

```python
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint, resume_time
history = solve_time(model, condition, panels=4, duration=.1, dt=.01)
saved = checkpoint(history)                 # last state; pass an index to branch
continued = resume_time(model, saved, duration=.1)  # additional time, ending at .2
```

The JSON bridge action is `resume_time`, with `source`, `checkpoint`, and a
`time` object containing `duration`; optional `dt`, `order`, `tolerance`,
`max_steps` and `forcing` override continuation settings. `forcing` omitted means
retain the original table. The API returns the new segment, including its initial
checkpoint state. Browser continuation from a selected result combines the
retained prefix with this segment. Checkpoints are data only and do not execute
code. They are not ASWING `.pnt`/`.set` files or steady-equilibrium JSON. Direct
launch from saved steady trim uses the separate launch workflow below.
Arbitrary physical-profile construction for nonlinear time integration remains
open; initial spectra use a frozen linear model.

`scripts/verify-time-checkpoints.py` records independent damped-oscillator time
refinement, checkpoint equivalence and controller discontinuity checks.
After generating that study and building, run
`node scripts/test-time-checkpoint-wasm.mjs` to resume native checkpoints using
the packaged browser kernel.


## Launch time response from saved steady trim

Save or use a computed equilibrium, select **Nonlinear time response**, and keep
**Start from loaded equilibrium** checked. The saved flight condition, mesh,
loads, gravity, frame pose and controller are authoritative. Solved trim settings,
measurement commands, actuator biases, integral states and custom states survive
even when the sidebar still contains the original guesses. Duration, maximum
step, integration order, frame mode/load targets and the forcing table come from the time
controls. The source must match exactly.

For ordinary launches, the first snapshot is the saved state with zero local elastic velocities and
circulation rate. The solver checks the full physical and steady controller
equations without recomputing equilibrium. Steady trim constraints are released;
free flight solves its six acceleration unknowns. Free or mixed motion requires
the saved net loads to satisfy the chosen frame load targets.
New forcing applies after the first snapshot. Relative `+` columns use saved
solved settings or controller commands/biases. A nonzero saved field time is
retained; the table must start no later than that absolute time. Applied values
become zero after its last sample, including relative channels.

Saved motion-history launches have a separate initial-state contract. Currently,
one nonrotating Earth-velocity or Earth-position target is supported with
force-only mixed motion, unchanged loads, no controller/gust, and an explicit
target table. Position histories must initially match both saved position and
Earth velocity. The saved
physical state is held while actuator settings and accelerations are completed
for the initial history. Snapshot 0 is that completed right state; the original
before-input snapshot and source equilibrium remain separately owned in
`launch_transition.before_input`.

New velocity-history checkpoints use scope version 3; position histories use
version 4. Versions 1–3 remain velocity-only. Compatible replacement tables,
doubled-time slope changes and zero cutoff complete a separate right state while
holding the physical motion. Both sides remain inspectable at the same time;
they do not count as additional integration steps. BDF history restarts after a
change. Continuing from an already completed right state does not repeat that
initialization. A run ending exactly at a break retains its left state; a later
continuation completes the right side. Version-1 and version-2 checkpoints keep
their original linear/smooth-table contracts.

The same transition dispatcher handles supported cold-start inverse histories,
including compatible BDF/Radau position replacements and the tested smooth controller
case. Old accepted states and their inputs are never reinterpreted against a
replacement table. Newly completed right records provide physical-state checks;
they do not supply a discrete-step or authenticated continuous-derivative
certificate. Incompatible position/velocity changes are rejected; an explicit
impulsive-event model and ASWING impulse conventions remain unfinished. Other
saved-history combinations also remain open. Consistent initialization can still
be expensive. See the [input-transition evidence](docs/validation/input-transitions.json)
and [the preceding smooth-table checks](docs/validation/saved-spline-histories.md).

Radau position-history runs use Earth position and velocity relative to the
prescribed trajectory, while preserving the physical force, moment, structure
and actuator equations. Unselected Earth components remain free. The method
records its own chart and all accepted stages; changing methods does not relabel
an earlier accepted step. Checkpoints retain the original position, velocity and
acceleration target samples. Old Radau records without those samples cannot be
silently upgraded. Incompatible initial position or Earth velocity is rejected
before the costly cold-initialization sweep. Time refinement is still required,
and ASWING executable/discrete parity is not established. See the
[Radau position-history evidence](docs/validation/radau-position.json).

Position-history checkpoints can round-trip through browser JSON without
mistaking equivalent numeric spellings (`0` and `0.0`, including signed zero)
for changed inputs. Their definition signatures remain intact. Input values are
compared exactly, with no numerical tolerance, and booleans remain distinct
from numbers.

```python
from openswing.time_initialization import launch_time
history = launch_time(model, steady['equilibrium_state'],
                      duration=.2, dt=.01, frame='free')
```

The bridge action is `launch_time`, with `source`, `equilibrium_state`, and
`time: {duration, dt, order, frame, forcing}`. The API holds saved loads by default;
`loads=[]` releases them after the first snapshot, while another load list
replaces them if the attachment mesh remains unchanged. Computed snapshots can
subsequently be checkpointed and continued normally.

Older equilibrium files without launch setup still support steady reuse.
Recompute and export them to launch time response. An inconsistent saved state
is rejected; there is no automatic initial-derivative projection or support
release. These OpenSwing files do not implement ASWING `.pnt`/`.set` interchange.

Reproduce the component and flight checks with
`OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify-steady-launch.py`, then
`npm run build` and `node scripts/test-steady-launch-wasm.mjs`.

## Editing beam distributions

Open **Beam properties**, select a beam and property, and choose **Load property**.
The table contains the file's station/value pairs in input units. Insert, delete
or double an interior station, or apply a value multiplier and offset. Each side
of a doubled station needs at least two points. To add a property, enter a
supported name (including indexed flap derivatives such as `dCLdF12`) and load it;
omitted defaults are supplied by the kernel. A new chord requires explicit values.

**Preview edit** constructs and validates a separate model, including its geometry
and mass data. The plot shows the spline used by the current kernel, separate
curves at jumps, reflected values and any extrapolation. **Apply preview** updates
the model, clears stale analysis results and retains matching flight-control inputs.
**Save** downloads the edited `.asw`. **Undo applied edit** restores the previous
document, including its original formatting. Preview omission removes an explicit
property, restoring its default; removing chord changes a surface into a body.
Apply raw ASW-text or mesh changes before using the property editor.

Native use:

```python
from openswing.asw import parse_asw
from openswing.asw_edit import edit_distribution

model = parse_asw(source)
edited = edit_distribution(model, 1, "EA", multiplier=2)
source_to_save = edited.dumps()
normalized_source = model.dumps(canonical=True)
```

Unchanged `Model.dumps()` remains byte-identical to its input. Changed models write
explicit global records and one station grid per property using round-trip float
precision. Comments are retained at the top; unknown blocks retain their original
text. Replacing a distribution rebuilds its spline; direct array mutation without
rebuilding is rejected on export. Both export paths preserve the distinction
between half-span symmetry, full-span asymmetric properties and doubled stations.
Use **Draw graft on plot** to place replacement points, or enter station/value
pairs in the graft field. Their sorted end stations delimit the replacement.
**Join curve and slope at both ends** snaps the two endpoint values and slopes
to the existing curve. With this option off, the clicked endpoint values are
retained and doubled stations preserve joins that have jumps or corners.
The operation follows table edits, multiplication/offset and the selected
symmetry change. The preview does not commit until **Apply preview** is chosen.

**Make left and right independent** expands a mirrored property into explicit
negative and positive station grids, retaining its curve, jump sides and center
corner. Only that property changes. **Mirror the positive half** retains the
nonnegative stations and discards the negative half. If zero was not a station,
its current value is inserted and the new half spline is previewed. The `y`
coordinate reflects about its center value. Automatic symmetry applies to
lifting surfaces; point objects and body properties are not mirrored.

Grafts save ordinary `.asw` station/value data. Since the documented format has
no endpoint-slope fields, tangent joins use an adaptive natural-spline
approximation. The preview reports its maximum value and slope errors over the
entire property domain, including the exterior of the graft. Both errors must
meet **Relative graft tolerance**; slopes are multiplied by domain length, and
both are normalized by the target curve's value range. A constant curve uses
its magnitude, or one for a zero curve. Refinement has a 4096-station limit;
unresolved edits are rejected. These extra property stations do not themselves
increase the structural mesh; doubled corners remain mandatory mesh stations.

The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
documents cursor grafts, tangency and property symmetry. Its exact spline
endpoint and graphical-editor algorithms remain compatibility gaps. The
native and packaged-WASM `distribution-graft` studies check explicit cubic
references, saved-file reconstruction and variable-stiffness spring compliance
and modes under spatial refinement.

Reproduce the graft checks with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_distribution_curve.py tests/test_asw_edit.py tests/test_asw.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-distribution-graft.py
npm run build
node scripts/test-distribution-graft-wasm.mjs
npm run test:browser -- tests/browser/distribution-graft.spec.js tests/browser/distributions.spec.js
```

## Mixed frame motion and finite forcing tables

In nonlinear time response, choose **Mixed motion · per axis**.
For each body axis, prescribe its acceleration or solve that acceleration from a
net-force or net-moment target. Enter constant targets in the mixed-motion panel;
time-table columns `Fx/Fy/Fz/Mx/My/Mz` can vary the selected targets. Free flight
selects all six net-load equations, defaulting to zero. Other acceleration
components use the motion fields or corresponding `Ax/Ay/Az/Gx/Gy/Gz` table columns.

Net loads include inertial reaction and exclude the supporting Ground reactions.
For a point mass with no external x force, `Fx = -m ax`; a positive Fx target thus
produces negative ax. The target is a load-equation constraint. Moments refer to
the `.asw` moment reference, and accelerations refer to its acceleration reference.
The **Guided rigid-body demonstrator** has one unit of mass and principal inertias
2, 3 and 4, with no aerodynamic surface or volume. Set gravity to zero to reproduce
its simple inertial relations.

```python
from openswing.time_integration import solve_time
history = solve_time(model, panels=4, frame="mixed",
    load_targets={"force.x": 0, "moment.z": 0}, gravity=[0, 0, 0],
    duration=.2, dt=.01, forcing="time Fx\n0 0\n.1 1\n")
```

This prescribes the remaining four acceleration components. The force target
ramps from 0 to 1 through t=.1 and is zero afterward. At the final table sample,
the integrator records its left-hand state, then advances with right-hand forcing;
BDF methods restart with BDF1. All specified
channels become zero after the table ends, including `+` columns: their initial
offset is not retained in the tail. A blank table preserves the setup's settings.
The extended manual documents the zero-after-end rule; its exact interaction
with relative channels still needs an ASWING executable comparison. Checkpoints
retain mixed constraints and applied targets; a saved steady launch must satisfy
the selected initial load targets before new forcing is applied.

## Mixed modal and harmonic frame constraints

Modes, frequency response and reduced models accept `frame="mixed"` with
`load_targets={"force.x": value, "moment.z": value, ...}`. Each selected net-load
row determines its corresponding reference acceleration; the other components
remain prescribed. `frame="prescribed"` holds all six accelerations while retaining
frame motion and accepts six harmonic acceleration inputs. All twelve frame
kinematic states remain active. Fixed frame
omits those states; free flight uses six net-load rows, zero by default. Nonzero
constant load targets are also accepted in the free-frame Python/JSON API.

The frequency-response input selector **Frame loads and accelerations** creates
six channels from the selected constraints. In the API, use `target.force.x`
through `target.moment.z` for active net-load targets, or `acceleration.x` through
`angular_acceleration.z` for prescribed components. Inactive load targets and
conflicting acceleration inputs are rejected. Linear accelerations use input
L/T²; angular-acceleration harmonic inputs use **radians/input T²**, while the
ASWING Gx/Gy/Gz time-table columns use degrees/input T². Force and moment inputs
use input F and F·L. Every harmonic input is an increment about the reported
constant base value.

```python
from openswing.frequency_response import solve_frequency_response

response = solve_frequency_response(model, condition, panels=4,
    frame="mixed", load_targets={"force.x": 0, "moment.z": 0},
    frequencies=[0.7, 3.0],
    inputs=["target.force.x", "acceleration.y", "target.moment.z"])
```

Net loads include inertial reaction: for a one-unit mass with no external x
force, unit Fx gives ax = −1. A prescribed unit Ay instead produces net Fy = −1.
Moments are about the ASW moment reference, and linear accelerations use the
separate acceleration reference. Frame motion includes both transports. Outputs,
Bode CSV, JSON and ROM generation preserve the selected layout and units.
ROM frame-input labels are annotated OpenSwing extensions. General inverse
constraints, defective-mode ROMs and ASWING numerical/experimental validation
remain required.

| Dynamic frame | Acceleration constraints | Frame perturbation states |
|---|---|---|
| Fixed | Base values held | Omitted |
| Prescribed | All six prescribed | Twelve |
| Free | All six determined by net loads | Twelve |
| Mixed | Selected components determined by net loads | Twelve |

`python scripts/verify-dynamic-targets.py` recorded eight independent mechanical,
rotating-frame, feedback and ROM cases with source hashes in
`docs/validation/dynamic-targets.json`. This record retains its historical source
hashes. Regenerate it before using `node scripts/test-dynamic-targets-wasm.mjs`
against a changed kernel.

The `python scripts/verify-integrators.py` study records exact zero roots,
weak nonzero poles, time-unit scaling and rigid-body/feedback spectra in
`docs/validation/integrators.json`. Its checked-in hashes now record an earlier
kernel. Regenerate it before using `node scripts/test-integrators-wasm.mjs` to
repeat its nine cases with a changed packaged runtime. Exact row/column
determinant factors preserve the kinematic zero
roots without snapping small values to zero. A dense change of coordinates can
hide those factors; general defective invariant-subspace tracking and Jordan-chain
ROMs remain pending. Small computed growth rates still require refinement.


## Nonlinear time launch with a physical disturbance

In **Saved equilibrium**, load an equilibrium or use a computed one. Select
**Nonlinear time response**, open **Initial physical disturbance**, and enable
its checkbox. Enter a physical state object or import one `kind: initial`
profile from a frequency/ROM study. The original
`examples/initial-nonlinear-spring.json` supplies a finite spring displacement
and velocity. Its beam endpoints match `instrumented-oscillator.asw`; set gravity
and angle of attack to zero when computing that example's steady base.

All fields are increments from the saved state, and omissions are zero. Beam
fields interpolate `[t,x,y,z]` rows onto the exact saved mesh. Displacement uses
input L, velocity L/T, rotations radians and rates radians/T. Circulation uses
L²/T. Frame fields are `velocity_origin_body`, `rates_body`, `position_earth`
and `attitude_rad`; attitude adds bank/elevation/heading radians to the saved
Euler angles before conversion to a rotation matrix. Feedback `integrals` and
`states` use their declared physical units. Actual actuators, internal loads
and reactions are solved, rather than supplied in the profile.

The launch solves the original nonlinear equations and differentiated
constraints while holding the prescribed coordinates fixed. It reports
residuals, local uniqueness, one-sided derivative checks and half-spacing
comparison. Incompatible profiles and unresolved constraints are rejected.
This experimental numerical initializer needs a compatible saved steady base;
cold construction, arbitrary support changes and nonsmooth/higher-index cases
remain limited. Very small physical increments are subject to floating-point
resolution of the absolute geometry. Refine derivative spacing, rank settings,
mesh and time step; convergence is not an accuracy certificate for an aircraft.

New forcing applies after the initialized first snapshot. Checkpoints retain its
physical velocities, circulation, controller states and completed acceleration
loads. Select **Radau IIA** for curved constraints with nonzero initial velocity;
BDF startup can produce a reaction transient whose peak does not converge.
Radau solves three coupled stages of the same physical equations and needs no
predecessor. The BDF options retain BDF1 startup. The API is:

```python
from openswing.time_initialization import launch_time
trajectory = launch_time(model, saved_equilibrium, duration=.12, dt=.01, order=5,
    disturbance={"beam_fields": [{"beam": 1,
        "displacement": [[0, 0, 0, 0], [2, 0, .2, 0]],
        "velocity": [[0, 0, 0, 0], [2, 0, .1, 0]]}]})
```

The JavaScript worker accepts the same fields under `time` in an
`action: "launch_time"` request. The default scaled derivative spacing is .01
and rank tolerance is 1e-7. See [the numerical notes](docs/NUMERICS.md#nonlinear-consistent-initial-disturbances)
for the derivative-array formulation and its limits. The reproducible mechanics
study is `scripts/verify-nonlinear-initial.py`; its packaged-WASM counterpart is
`scripts/test-nonlinear-initial-wasm.mjs`. These are independent component and
trajectory checks, not an ASWING executable or experimental comparison.


The six-case [native study](docs/validation/nonlinear-initial.json) and
[packaged WASM replay](docs/validation/nonlinear-initial-wasm.json) record source
hashes, independent references and refinement/restart checks. The
[validation figure](docs/validation/nonlinear-initial.svg) (also [PDF](docs/validation/nonlinear-initial.pdf))
shows acceleration and force errors alongside displacement histories.


## Velocity fields on arbitrary planes

Run an aerodynamic analysis and open **Flow field**. Choose body or Earth
coordinates, an origin, normal and preferred in-plane direction. The direction
is projected into the plane and normalized; the second direction is normal ×
first direction. Enter bounds in the file's length units and 2–99 samples per
axis, then select **Sample selected state**. Time scrubbing selects the computed
checkpoint; eigenmode and Bode analyses select their steady base. Changing the
state or plane clears the previous survey. On narrow screens the plot scrolls
horizontally so labels retain their size.

Arrows show the two in-plane velocity components. Color shows magnitude, either
in-plane component or the normal component. All speeds use input L/T. Available
contributions are rigid-frame kinematics, gust, lifting vortices, body/point
sources and doublets, propeller jets, their induced sum, atmospheric air velocity
and frame-relative velocity. Air velocity is gust plus induced flow relative to
the still atmosphere; frame-relative velocity additionally subtracts rigid body
translation and rotation. A moving sensor also subtracts its local elastic
velocity, which is not defined at arbitrary off-body points.

Saved geometry, actual controller/trim actuators, circulation, Earth pose, gust
phase and time-event side are restored without solving a new equilibrium or
advancing time. Structural-only states have no aerodynamic survey. JSON exports
include the complete sampling request, selected saved state, plane basis,
positions in both frames, masks and all component vectors. CSV retains the
position frame and all Cartesian/plane components in named columns. SVG is a
standalone version of the selected plot; changing plot quantities reuses the
same computed samples.

These are regularized external fields on frozen straight wakes. They do not
resolve shed-wake history, boundary layers or body interiors. Circular body
segments and the nonfluid side of the ground plane are masked. Ground images,
compressibility, volume strengths and gusts retain the solver's documented
approximations. The [public ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes slice-plane gust plotting; exact ASWING plotting and numeric gust-file
catalog parity remain unverified.

Reproduce the field checks with:

```bash
.venv/bin/python -m pytest -q tests/test_flow_survey.py tests/test_time_state.py
.venv/bin/python scripts/verify-flow-survey.py
npm run build
node scripts/test-flow-survey-wasm.mjs
.venv/bin/python scripts/plot-flow-survey.py
```

The source-hashed native and packaged-WASM reports are
`docs/validation/flow-survey.json` and `flow-survey-wasm.json`. Independent vortex
and body integrals, point/PG/ground tensors, polar jet momentum and Earth-frame
kinematics are distinguished from saved-sensor cross-path checks. The browser
workflow is in `tests/browser/flow-survey.spec.js`.


## Concentric body-radius jumps

Doubled `radius` stations on a nonlifting beam now produce concentrated body
sources and shoulder forces. The **Stepped body · weak-limit verification**
example checks zero resultant and the pitching moment of a closed body in
uniform flow. Its axial stations have different radii on the two sides; this is
preserved in ASW import/export and shown with annular faces in the geometry.

In **Span loading**, select **Shoulder force x/y/z** for force impulses in input
F. They are separate from distributed strip forces in F/L. **Shoulder CSV**
exports every shoulder's position, left/right radius, area change, incident
velocity and force. Solver report and JSON retain the same data. Time history
has per-shoulder force channels, and scrubbing updates the impulse plot and CSV.
The shared field sampler includes shoulder sources and their ground images.

The implementation integrates the smooth slender-body source and force laws
across the radius change. It also integrates the prescribed radius-dependent
core through that change; it does not select an arbitrary single radius there.
Concentrated loads act at their actual structural nodes, without distributing
them over adjacent intervals. Steady, derivative, nonlinear time and checkpoint
paths share those equations.

This is a weak-limit extension of the documented slender-body approximation,
not a resolved blunt-face or separated-flow model. A coincident position or
tangent break requires an explicit transition geometry because the limiting
path would otherwise be unspecified. Nonzero endpoint radii do not create
implicit end caps. Exact ASWING discrete jump/core evaluation remains unverified.
See the derivation in `docs/NUMERICS.md` and the
[ASWING steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).

```bash
.venv/bin/python -m pytest -q tests/test_body_shoulders.py tests/test_volume.py
.venv/bin/python scripts/verify-body-shoulders.py
npm run build
node scripts/test-body-shoulders-wasm.mjs
.venv/bin/python scripts/plot-body-shoulders.py
```

The native and WASM reports in `docs/validation/body-shoulders*.json` retain
source/runtime hashes and independent area/axis quadratures, load and reaction
checks, units, elastic beam response, derivatives and time/checkpoint replay.
They distinguish physical-model limits from source-hashed numerical agreement.
The [validation figure](docs/validation/body-shoulders.svg) is also available as
a [standalone PDF](docs/validation/body-shoulders.pdf).


## Refine a loaded frequency response

After running **Frequency response**, open **Add samples or extend the frequency
range** in the Bode response tab. Add a linear/logarithmic range or a list of
angular frequencies in rad/input T. This supports both extra detail near a
resonance and a wider range. Exact duplicates are skipped; distinct nearby
floating-point values remain distinct samples.

New samples reuse the original loaded state, controller configuration,
linearized equations and input definitions. The original samples, including
unresolved poles, remain unchanged. Convected gust inputs are evaluated again
at each new frequency to retain their spatial phase. Harmonic transfers and
shifted initial-state spectra retain their different rate and unit conventions.
The chosen input/output, station, sample frequency and phase view stay selected.
Adding zero frequency switches the plot to a linear axis; log plots explicitly
state when zero is omitted. CSV and JSON export the complete refined grid.

Refinement is available while the analysis is loaded in its local numerical
worker. Changing the aircraft/settings, starting another frequency analysis or
restarting the worker requires a new analysis. No imported result is silently
attached to a different dynamic model. Exported JSON includes the complete
solve request for a fresh replay; its live continuation handle is not an ASWING
companion file or a persistent checkpoint.

The native API provides `FrequencyAnalysis` for repeated frequency batches and
`FrequencySweep` for transactional merging of samples. At the JSON boundary,
`action: "frequency"` with `retain_frequency: true` returns `frequency_session`.
Send that handle with `action: "extend_frequency"`, the identical `source`, and
`frequencies` to refine the loaded grid. `discard_frequency` releases the handle.
Only the most recent retained sweep is kept; stale or changed-source requests
fail explicitly. Old/new reports own their result arrays independently.

```bash
.venv/bin/python -m pytest -q tests/test_frequency_sweep.py tests/test_frequency_response.py
.venv/bin/python scripts/verify-frequency-refinement.py
npm run build
node scripts/test-frequency-refinement-wasm.mjs
.venv/bin/python scripts/plot-frequency-refinement.py
```

The source-hashed reports and standalone SVG/PDF figures are in
`docs/validation/frequency-refinement*`: [SVG figure](docs/validation/frequency-refinement.svg)
and [standalone PDF](docs/validation/frequency-refinement.pdf). They compare analytical mechanical,
feedback, gust-phase and initial-spectrum responses, time-unit scaling, a
retained free-flight DC gap and a loaded elastic trim. A fresh full-grid solve
is an additional replay check; it is not independent physical validation.


## Compare frequency responses

In **Bode response**, open **Compare inputs, outputs and stations** after a
frequency solve. Use **Add current response** to retain the chosen input/output
and station. Change the selectors and add more outputs. **Add input range**
compares the selected output for every input between the chosen first and last
indices, including cosine/sine gust families. **Add all stations** compares the
chosen quantity across structural nodes, sections, aerodynamic strips or sensors.
The gust-mode order is a nonnegative integer; it is no longer capped at eight
by the browser. Higher orders require adequate spatial resolution.

Curves with different response units or different spectral meanings have
separate plot axes. Every trace has its input name, output, component and station
in the legend. A comparison contains independent unit-input responses; it does
not apply all inputs at once. Initial-state spectra retain their extra time unit
and Laplace shift. The scalar broken-loop display uses each input's own matched
output, with unmatched channels and singular reciprocals retained as gaps.

Magnitude/dB, wrapped/unwrapped phase and linear/log frequency controls also
apply to the comparison plots. Phase unwraps independently for each curve and
restarts after a missing sample or exact zero. Refine the frequency spacing
when phase varies rapidly; sparse samples cannot reveal intervening revolutions.
Zero amplitude has no phase or
dB value. Log plots omit zero frequency explicitly; the exports retain it.
A mouse click or Enter/Space on a sample selects that trace's input, output,
station and frequency for detailed inspection. The existing physical-amplitude
geometry view still shows one response; initial spectra show the loaded base.

Hide or remove individual curves, or clear the comparison. Exact repeated
selections are deduplicated. Adding frequencies retains the selections and
updates every comparison curve. Changing the model or analysis settings clears
them along with the old result. Comparison CSV is a long-form table of all
visible traces at every frequency, with physical units, complex values, phase
convention, initial shift and explicit gap/zero status. **Export plot SVG** saves
a standalone labeled vector figure for each compatible group. Plots can scroll
horizontally on narrow screens.

The original **Gust-mode phase demonstrator** supplies a fixed offset drag point,
two sensors and a force actuator. At speed 10, alpha zero, zero gravity and zero
Mach, its unit vertical gust force has the analytical spatial-phase relation
printed in the ASW comments. It is a compact check of the gust-mode display,
not an aircraft validation case. The comparison workflow implements the
multi-response and forcing-range selection described in the
[ASWING BODE guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt).

```bash
node --test tests/frequency-comparison.test.mjs
node scripts/verify-frequency-comparison.mjs
npm run build
# With the local production app served at http://127.0.0.1:8000:
OPENSWING_BASE_URL=http://127.0.0.1:8000 npm run test:browser -- tests/browser/frequency-comparison.spec.js
```

The [standalone comparison figure](docs/validation/frequency-comparison.svg),
[CSV](docs/validation/frequency-comparison.csv) and
[source-hashed display check](docs/validation/frequency-comparison.json) reuse
validated numerical responses and independently check their offset-point gust
force/moment references. They validate display/export behavior; they do not
constitute a new aircraft or kernel benchmark. Their source hashes identify the
historical kernel used; the reference-airflow increment below changes the kernel.

## Reference airflow in a gust

In **Mounted equilibrium → Operating constraints**, **Set reference airflow
targets** uses the entered Speed, α and β as targets at the `.asw` velocity
reference. It replaces the target list with three equations and solves the
still-atmosphere speed and angles needed to achieve that local airflow. Those
input fields become initial guesses. This also works when preparing a loaded
modal or frequency-response base.

For example, use the **Gust-mode phase demonstrator**, speed 20, alpha 6, beta
−3 and a uniform Earth gust `[3, -1, 2]`. With zero attitude, the desired local
velocity is `20 [cos(6°)cos(−3°), −sin(−3°), sin(6°)cos(−3°)]`. The solved
still-air velocity is that vector minus the gust. Ordinary prescribed speed
and angle fields keep their still-atmosphere meaning when the preset is absent.

Individual target selectors also offer **Reference equivalent airspeed** and
**Reference dynamic pressure**, both including the gust at the posed reference
point. Equivalent airspeed uses the square root of density divided by the
file's sea-level density; exact ASWING VIAS instrument conversion is unverified.
Reference flow excludes induced flow and local elastic velocity, following
[steady equations 181–184](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
The report and JSON show local reference velocity, speed, angles, equivalent
airspeed and pressure separately from the still-atmosphere quantities used for
coefficient normalization. Undefined flow angles export as null.

The native API accepts target names `reference.speed`, `reference.alpha`,
`reference.beta`, `reference.equivalent_airspeed` and `reference.dynamic_pressure`.
`openswing.reference_flow.reference_airflow_constraints(speed, alpha, beta)`
creates the three-equation preset; the JSON bridge exposes the same operation
as `action: "reference_airflow_constraints"` with `source` and `preset`.
Saved equilibria retain the solved setup. Modal/frequency/time launches release
steady trim constraints according to the selected dynamic frame.

```bash
.venv/bin/python -m pytest -q tests/test_reference_flow.py
.venv/bin/python scripts/verify-reference-flow.py
npm run build
node scripts/test-reference-flow-wasm.mjs
OPENSWING_BASE_URL=http://127.0.0.1:8000 npm run test:browser -- tests/browser/reference-flow.spec.js
```

The [native study](docs/validation/reference-flow.json) and
[packaged-WASM comparison](docs/validation/reference-flow-wasm.json) record
source hashes, independent vector/load references, consistent feet/millisecond
units, branch-cut continuation and a saved spring equilibrium's analytical
frequency response. The elastic case checks integration with a loaded wing;
it is not an independent aircraft validation.

## Weighted trim with redundant controls

Use **Operating constraints** to assign the required force, moment or other
physical targets. For each additional actuator, add another row and select
**Least-squares control effort**. Each row must solve a different flap or engine.
The **Weighted control trim** fields then set a positive weight and preferred
setting for every solved flap/engine, including those assigned hard targets.

The solver minimizes `½ Σ weight × (setting − preferred)²` subject to the full
physical equilibrium and selected targets. Preferred settings default to zero;
weights multiply squared settings in the file's control units. Prescribed and
controller-owned actuators are outside this objective, while their physical
loads and any controller equations remain in the coupled problem. Actuator
limits are not imposed. The report shows the resulting objective, controls,
physical residual, stationarity and local curvature checks. A converged local
allocation does not establish global optimality or aircraft stability.

Try **Redundant thrust allocation** with speed 10, alpha 0 and zero gravity.
Solve Engine 1 for net force x = 20; assign Engines 2 and 3 to least-squares
control effort. Weights `(1, 4, 2)` and preferred settings zero give engine
settings `(40, 5, 10) / 4.75`, satisfying `2 E1 + E2 + E3 = 20` exactly.
Changing Engine 2 to a net moment z target of zero also imposes `2 E1 − E2 = 0`;
Engine 3 remains the free control direction. Save the equilibrium to continue
with new targets or use it as a loaded modal/frequency base. Dynamic and
stability-derivative responses release the steady allocation constraints.
Reloading an equilibrium as a steady guess still uses the current target,
weight and preferred-setting fields.

The Python/JSON interface uses `quantity: "minimum_control"` for the extra
actuator rows, and optional `weight` and `preferred` fields on all selected
actuator rows. A minimum-control row has no hard target; omit `target` or set
it to zero. For example:

```python
operating_constraints = [
    dict(variable='power.1', quantity='force.x', target=20, weight=1),
    dict(variable='power.2', quantity='minimum_control', weight=4),
    dict(variable='power.3', quantity='minimum_control', weight=2),
]
```

This implements the redundant-control capability described in the
[ASWING v5.86 notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt).
Those notes do not publish the weight formula; exact ASWING weighting and
branch-selection parity remain unverified. OpenSwing's formula is explicit.

```bash
.venv/bin/python -m pytest -q tests/test_control_allocation.py
.venv/bin/python scripts/verify-control-allocation.py
npm run build
node scripts/test-control-allocation-wasm.mjs
OPENSWING_BASE_URL=http://127.0.0.1:8000 npm run test:browser -- tests/browser/control-allocation.spec.js
```

The [native study](docs/validation/control-allocation.json) and
[packaged-WASM study](docs/validation/control-allocation-wasm.json) record exact
source hashes, weighted projection references, nonlinear disk momentum,
proportional elastic flap allocation, a controller-owned engine, consistent
units and saved-equilibrium harmonic response. Earlier numerical reports,
including `reference-flow*.json`, retain their historical kernel hashes.

## Custom trim equations and sensor targets

In **Operating constraints**, add a row, select the variable to solve, and choose
**Custom equation / sensor target**. Enter a unique equation name, expression,
target, output unit label, and positive residual scale. The sensor selector can
fill the expression and units. Each equation is a hard equality in the same
nonlinear solve as deformation, circulation, loads and any active controller.
For the **Instrumented spring–mass demonstrator**, use mounted mode, four panels,
zero gravity, speed 10 and alpha 0. Solve `power.1` with
`sensor("2.displacement_body.y") = 0.01`, units `input L`, scale `0.01`.
The 500 N/m spring requires engine setting 5 N. Alternatively, the adjacent axial
strain target `sensor("2.strain.s") = 0.005` gives the same state.

Python/JSON constraints use this original OpenSwing schema:

```json
{
  "variable": "power.1",
  "quantity": "user.tip",
  "expression": "sensor(\"2.displacement_body.y\")",
  "target": 0.01,
  "residual_scale": 0.01,
  "unit": "input L"
}
```

The name after `user.` starts with a letter and contains at most 48 letters,
digits or underscores. Expressions support finite scalar arithmetic, `pi`,
`sin/cos/tan`, `asin/acos/atan/atan2`, `exp/log/sqrt`, `abs`, `minimum/maximum`,
`clip(value, low, high)` and lazy `where(condition, a, b)`. Trigonometric functions
use radians; sensor angles and operating alpha/beta/attitude use degrees.
References use literal strings:

| Accessor | Available values and conventions |
|---|---|
| `sensor("2.field.axis")` | Every scalar/vector measurement listed in the Sensors panel. Vectors use `x/y/z`, except structural force, moment, strain and curvature use `c/s/n`. Scalar fields omit the axis. Sensor rate/acceleration units are radians/input T and radians/input T². |
| `variable("power.1")` | Any declared operating variable, including actual flap/engine settings and controller commands available to the current solve. Uses the same units as `operating_values`. |
| `load("force.z")` | Net externally applied `force.x/y/z` or `moment.x/y/z`, including gravity and inertial reaction; moments refer to the ASW moment reference. Support and internal reactions are excluded. |
| `aero("CL")` | Current `CL`, `CY`, `CD`, `Cl`, `Cm` or `Cn`, with the coefficient conventions reported by the solver. |

The unit label records the expression's physical units; it does **not** convert
values or check dimensional consistency. Constants and target values must use
consistent file units. Residual scale divides the expression-minus-target error;
choose a physically meaningful scale rather than an arbitrarily tiny number.
Undefined measurements, unsupported syntax, dependent equations, and inconsistent
one-sided tangents produce errors. Angle expressions use their reported numeric
branches; no automatic angle wrapping is applied to an arbitrary formula.

Sensor locations and axes follow their moving pylons. Displacement is the beam
anchor displacement; Earth position refers to the pylon tip. Structural loads use
the reported one-sided trace and strain/stress use the adjacent material midpoint,
not the exact anchor location. Check the Sensors panel and refine the mesh when
using these measurements as targets. Missing shell dimensions remain undefined.
Air-data targets respect the selected full or kinematic sensor airflow mode.

Custom trim starts from a loaded equilibrium and continues the target values.
A saved equilibrium uses its physical state as the initial guess and the current
editor's equations/targets. A seed containing a controller requires the matching
controller definition, including when using weighted allocation. Controller-owned
actuators remain governed by their control laws; select a `command.*` trim variable to adjust their commands. Extra
minimum-control slots can allocate redundant actuators while retaining custom
constraints as exact equations. The final physical tangent and one-sided custom
row slopes are checked. This establishes local numerical regularity, not global
uniqueness or stability.

Equations, reference units and diagnostics are included in result JSON and the
solver report. Saved equilibrium files retain the definitions. Derivative, modal,
Bode and time responses release the steady custom equations and start from the
solved physical controls and state. Time launch retains the saved setup; ordinary
steady/modal/Bode reuse solves again with the current settings.

[ASWING v5.86 notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt)
document custom `C_user1`/`C_user2` equations hard-coded in `GCON`, with sensor
quantities as examples. This bounded expression interface replaces that editing
workflow; it does not import or execute Fortran routines. Exact ASWING sensor
trace, interpolation and custom-routine parity remain unverified.

Verification commands:

```sh
.venv/bin/python -m pytest -q tests/test_custom_constraints.py tests/test_custom_trim_integration.py
.venv/bin/python scripts/verify-custom-trim.py
npm run build
node scripts/test-custom-trim-wasm.mjs
```

The source-hashed numerical study is `docs/validation/custom-trim.json`, with
packaged browser-kernel checks in `custom-trim-wasm.json`. Earlier studies retain
their original source hashes and are historical evidence when those differ.

## Saved and measured Bode overlays

In **Frequency response → Compare inputs, outputs and stations → Overlay saved
or measured data**, choose a computed output and open a local file. OpenSwing
Bode and comparison CSV files are recognized automatically; choose one series
from a comparison file. Other numeric tables need explicit column numbers,
delimiter and header-row count. Whitespace tables accept `#`/`!` comments and
Fortran `D` exponents. Comma, tab and semicolon tables accept quoted fields.

Map real/imaginary values or magnitude/phase (degrees or radians); dB means
`20 log10(magnitude)`. Set the source frequency to radians or cycles per source
time unit. Enter the size of that time unit in the current model's input T units,
and the multiplier that converts the response into the selected output/input
units. Include the reference amplitude when converting dB values. The harmonic
convention selector conjugates data using `exp(-iωt)` into `exp(+iωt)`.
Unit conversion is explicit: labels alone cannot identify the numerical unit
magnitudes of another aircraft file. Initial spectra also require the same
Laplace damping; CSV imports check this after time conversion. Raw tables rely
on the user's declared target and conversion.

Preview the converted range, finite-sample count and first response, then add it
to the comparison. The imported curve has its own frequency grid and a dashed
line. Clicking an external sample displays its value without changing the
computed geometry. Curves can be hidden or removed. CSV exports include computed
and imported samples, source labels and the conversion mapping; SVG exports
include both curves and their legends. The physical result JSON stays unchanged.
Frequency refinement retains overlays. Changing the analysis clears them and
invalidates pending previews or file reads.

Frequencies must be finite, nonnegative and strictly increasing. Missing response
fields (`NA`, `NaN`, `null`, `-`, or empty delimited cells) remain gaps. Zero
magnitude has no phase or finite dB value; `-Infinity` dB represents zero.
There is no interpolation, automatic fitting, uncertainty estimation or inference
of channel meaning. Files are limited to 2 MiB, 10,000 samples per series and
64 imported curves. Column indices start at one; the header count skips nonempty
parsed rows (whitespace comments are removed first).

`examples/oscillator-bode.csv` is an original analytical reference for
`instrumented-oscillator.asw`: mass 2 kg, stiffness 500 N/m and damping
10 N·s/m, with one intentionally missing sample. Select sensor 2's body-y
displacement, choose comma columns 1/2/3, skip one header row, magnitude/phase in
degrees, cycles per source time unit, time multiplier 1 and response multiplier
0.001. The file uses Hz and mm/N; the model uses seconds and metres. It is
synthetic reference data, not an experiment.

The [public ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
documents BODE's saved-data overlay workflow. Exact automatic parsing of ASWING's
legacy Bode output variants is still unverified; use explicit table mapping when
the column meanings are known. Time-history and distribution-data overlays remain
separate outstanding features.

```sh
node --test tests/frequency-overlays.test.mjs tests/frequency-comparison.test.mjs
node scripts/verify-frequency-overlays.mjs
npm run build
```

The numerical conversion study is `docs/validation/frequency-overlays.json`.
It checks independent oscillator responses and verifies the source/runtime hashes
of the reused custom-trim native/WASM baseline. This display feature leaves the
numerical kernel unchanged; offline browser tests additionally run the current
packaged solver and verify import, export, refinement and invalidation.

## Elastic rotor mount and whirl flutter

Select **Elastic rotor mount · whirl flutter** to study the coupled pitch/yaw
motion of an ideal rotor on a flexible mount. The original
`examples/whirl-flutter.asw` uses ASWING Engine type 2, which includes transverse
inflow and motor-mount rotation-rate terms. Its rotor angular momentum is a
separate `Weight` property. This is the elastic-mount capability described in
the [ASWING v5.82 notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt)
and [unsteady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).

To reproduce the four-interval reference:

1. In **Nodes**, choose **Uniform in arc length**, set **Intervals** to 4, and
   apply the beam mesh.
2. Set speed to 10, alpha/beta to zero, custom gravity to zero, custom density
   to 1.225, and fixed PG Mach to zero.
3. Choose **Coupled eigenmodes**, the fixed aircraft frame, 4 modes and the dense
   solver. Keep vacuum off. All four modes decay at this speed.
4. In **Stability progression and boundaries**, sweep speed from `10, 14` and
   refine the bracket. The four-interval model crosses into whirl instability
   at about **12.382 m/s**, with angular frequency **6.692 rad/s**. Inspect the
   14 m/s point and play the unstable mode's phase to see the rotor precession.

For a forced response, choose **Frequency response**, fixed frame, and declared
controls. `power.2` and `power.3` are test couples of one N·m about the mount's
y/z axes. Inspect tip-node rotation y/z to see the direct and cross-axis
amplitude and phase. Engine 1's setting remains zero in this reference.

The mount is a one-metre, massless beam with equal bending rigidities
`EI=5 N·m²`. Its root is clamped and tip translation is pinned. Finite axial
stiffness avoids redundant axial support reactions; torsion and shear use the
documented rigid limit. The rotor's transverse inertia is `0.2 kg·m²` per axis,
with intrinsic angular momentum `Hx=-1.8 kg·m²/s`. The propeller has three
constant-chord blades, radius 0.5 m, chord 0.06 m and rotation rate 180 rad/s
about its −x thrust direction. Blade section lift and profile drag are zero at
the base state, so thrust and shaft torque are zero. Small transverse motion
still creates aerodynamic forces and moments. Negative `Rdisk` disables the
jet. Reported moments use the fixed rotor pin as their reference.

The radial inflow-angle integrals are evaluated at 10 m/s and held fixed during
the speed sweep, as specified by this Engine type 2 input. Thus the boundary is
for the documented frozen-coefficient propeller model. It is not a measured
rotor limit or a full blade-resolved prediction. Refining the structural mesh
changes the mount's rotational stiffness toward its continuum value `4EI/L`;
the four-interval boundary is not a mesh-converged value.

Verification uses an independent four-state gyroscopic model, direct azimuthal
blade-force quadrature, complex torque-response matrices, spin reversal,
coordinate rotation, changed time units, 4/8/16-interval refinement and a checked
flutter bracket. The source-hashed studies are `docs/validation/whirl.json` and
`whirl-wasm.json`.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-whirl.py
npm run build
node scripts/test-whirl-wasm.mjs
```

The numerical kernel is unchanged in this benchmark increment. The new example,
browser workflows and independent checks establish an additional verified use of
its coupled engine/structure/inertia equations. Nonlinear rotor transients,
powered/preloaded mounts, ASWING executable agreement and experimental whirl
validation remain open.

## Projects and saved cases

Open **Project & saved cases** below the ASW file buttons. Enter a case name and
choose **Save as new case** to retain the current workbench inputs. A project
can hold different ASW configurations and multiple conditions for each model.
Select a case and choose **Load case** to restore editable inputs. **Update case**
replaces that selected case with the current inputs; **Rename case** and
**Remove case** manage the list. **Undo project edit** restores the preceding
saved list, including after a page reload. **Undo load** restores the previous
workbench inputs during the current session.

Each case contains the exact applied `.asw` text and filename, applied per-beam
mesh, flap/engine settings, Fourier counts, atmosphere and pose, operating
constraints (including custom equations and weighted control costs), derivative
selection, time/modal/frequency settings, gust definitions, controller definitions,
forcing tables and initial profiles. A loaded equilibrium and its enabled state
travel with the case. To save a computed equilibrium for later reuse, first
choose **Use computed equilibrium**, then save or update the case.

Inactive analysis settings are retained too: switching from a stored trim case
to time or frequency response keeps its prepared forcing and response settings.
All values remain in the ASW input units. Display unit selections, including
altitude units, are restored without applying their conversion twice.

Saved cases persist in browser storage for the current site address. Reloading
the page restores the case list; **Load case** applies the desired configuration.
**Export project** downloads all saved cases. **Export current case** captures
the current inputs directly in a one-case project, without requiring browser
storage. Use this when moving work to another browser or when storage is
unavailable. **Open project** replaces the saved case list; it leaves the current
workbench in place until a case is loaded. The preceding project remains
available through **Undo project edit**.

Apply or reload pending ASW, property-table and node drafts before saving or
loading cases. Loading first inspects the saved model and mesh, then restores
the inputs and checks that no saved field was dropped or changed. Invalid
models, unsupported fields and edits made while the inspection is pending stop
the load. A failed application restores the previous inputs. Another tab cannot
silently overwrite newer saved cases: reload the saved project, then save the
current workbench inputs again.

**Save computed solution** creates a separate, named result record after a
calculation. It retains the full steady result, time history, eigenmode set or
frequency grid, the exact calculation request and source, editable configuration,
and any current ROM, stability sweep, flow survey and Bode comparison curves.
Updating or removing a case leaves its saved solutions intact. Rename or remove
solutions independently; **Undo project edit** also restores removed solutions.

**Open solution** inspects the source and restores saved numerical values and
result selections without rerunning the analysis. **Undo load** restores the
preceding workbench, including its computed solution when opening a solution.
Editing analysis inputs invalidates the displayed result. Opening a project
only changes the saved lists; choose **Load case** or **Open solution** afterward.
Loading an editable case clears computed results as before.

Each result records SHA-256 hashes of the exact numerical source modules loaded
by its worker and its Python/Pyodide/NumPy/SciPy versions. A canonical content
checksum covers values, requests, configurations, supplementary data and views;
imports and browser-store reads check it before adopting a project. These checks
detect changed data; they are not a signature, a physical-validity certificate
or a substitute for inspecting an external result. A different recorded numerical
version is displayed explicitly. New calculations use the currently loaded kernel.

Live frequency-refinement handles cannot survive a worker replacement and are
omitted from archives. All existing samples and gaps remain available; run a
fresh analysis to add frequencies. Physical time checkpoints remain part of the
saved history and can launch continuation through the usual consistency checks.
Continued histories retain the numerical origin of each earlier snapshot range;
archives identify histories containing different recorded numerical versions.
An imported equilibrium remains subject to source, mesh, controller and
physical-consistency validation when used for a new analysis.

**Export project** includes all named cases and saved computed solutions. The
portable format is `openswing-project`, version 2, with at most 200 cases and
200 solutions, 64 MiB per project and 8 MiB of ASW text per configuration.
Version-1 projects upgrade with an empty solution list. This is an OpenSwing
archive; it does not parse ASWING `.set`, `.pnt` or binary `.state` files. The
[ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
documents separate settings and operating-point saves; exact legacy-file
interoperability remains open.

Project checks can be reproduced with:

```sh
node --test tests/projects.test.mjs tests/solutions.test.mjs
npm run build
npm run test:browser -- tests/browser/projects.spec.js tests/browser/project-controller.spec.js tests/browser/solutions.spec.js
```

## Published straight-wing lift and drag comparison

The SA-1 study imports the unchanged straight-wing model from the
[ISAE validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation)
and compares it with archived ASWING 5.96 results and the repository's experimental
series attributed to Applin, NASA TM-110148 (1995). Five spatial meshes and two
PG Mach choices distinguish numerical resolution from model/reference differences.
The model and data are fetched separately; they are not included in the MIT source
or offline-app archives. No parameters are fitted to the measured polar.

At approximately 18° incidence, the experimental drag coefficient is 0.15,
while both the archived ASWING result and OpenSwing are approximately 0.096–0.098.
That difference remains after mesh refinement. Separate deep-stall probes expose
multiple-root selection at 60° and failed convergence at 90°. These are explicit
validation/robustness gaps, not claims of a validated deep-stall envelope.

See [the SA-1 study](docs/validation/sa1.md) for pinned sources, setup conflicts,
reproduction commands, full numerical differences and the SVG/PDF figures.
To inspect a case in the browser, fetch the references, open
`reference/isae-sa1/SA_1.asw`, select rigid aerodynamics, set speed 47.9 and
alpha 18.091, and choose fixed PG Mach 0 under Atmosphere. Density comes from
the file's sea-level value 1.2256. Run with 200 and 400 intervals to compare
spatial resolution, then choose automatic PG Mach to inspect the separate
compressibility sensitivity. The actual model import and selected solves also
have an offline browser workflow.

## Stalled circulation branch study

The **Section stall parameters** controls expose the published dimensionless
leakage factor `K_s` and transition width `delta_cl`, with unchanged defaults
40 and 0.05. Cases and computed archives retain them; older cases restore those
defaults. Saved-equilibrium time launches use their saved parameters. The
[parameter study](docs/validation/stall-parameters.md) checks the infinite-span
limit, finite-wing sensitivity, consistent units and zero-leakage equivalence.

Select **Stalled rectangular wing · branch study**, rigid aerodynamics, speed
47.9, alpha 60, zero sideslip and 96 intervals. The model supplies sea-level
constants and symmetric section stall limits. The automatic circulation solver
uses arclength continuation near stall. The report shows its accepted steps,
final physical residual and **zero final regularization**; the complete path
is retained in exported JSON. Negative incidence can be compared directly.
The numerical solver does not change the section stall or pressure-drag equations.

An original rectangular-wing study covers mirrored 60-degree cases on four
meshes, unit changes, pointwise/Fourier equivalence, comparison with the direct
solver in the measured-angle range, and a separately bracketed infinite-span
reference through 90 degrees. Selected 75/85-degree cases are checked at three
continuation step sizes. The finite-wing 90-degree case remains unresolved.
Returned stalled roots are not guaranteed unique or physically stable, and the
study does not validate the empirical model against deep-stall experiments.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-stall-circulation.py
npm run build
node scripts/test-stall-circulation-wasm.mjs
npm run test:browser -- tests/browser/stall-circulation.spec.js
```

See [the circulation study](docs/validation/stall-circulation.md), its native/WASM
records and the numerical notes for exact
settings and retained failures. The preceding SA-1 report records the older
solver's branch-selection failure; it remains a historical experimental study
with its original source hashes. The new continuation study uses an original
model with matching section parameters and does not overwrite the experimental
comparison or remove its documented discrepancies.

## Archived swept-wing comparison

The [SA-2 source audit and comparison](docs/validation/sa2.md) imports an unchanged
public ASWING case and compares mesh resolution, current/frozen influences (K/F)
and fixed/automatic PG Mach. The archived coordinates specify about 35.265°
sweep, despite the case's 45° title. The primary experiment has different chord
and tip geometry. Its first drag datum is missing, and its force coefficients
come from pressure measurements. The study preserves these distinctions and
provides separate pressure-only diagnostics without fitting parameters.

The 114-case study contains 104 computed cases and ten rejected fine-mesh cases.
Independent line integration confirms growing tip velocity under refinement;
the 400-interval higher-incidence cases exceed the local subsonic limit. Total
drag also differs from archived ASWING. A complete mesh-converged, experimentally
matched swept-wing validation remains open.

```sh
python3 scripts/fetch-sa2.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-sa2.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-sa2-tip.py
.venv/bin/python scripts/plot-sa2.py
npm run build
node scripts/test-sa2-wasm.mjs
npm run test:browser -- tests/browser/sa2.spec.js
```

For browser inspection, open `reference/isae-sa2/SA_2.asw`, choose rigid steady
aerodynamics, speed 49.9, alpha 10.5, beta zero, and fixed PG Mach zero. The input
provides density 1.2256. Compare 100 and 200 intervals, then toggle **Freeze
aerodynamic influences (K/F)**. At 400 intervals this case is rejected; the error
is retained instead of returning an apparently valid result. External reference
files are fetched separately and excluded from the distributed archives.

The [tabulated swept-wing study](docs/validation/weber-lifting-line.md) adds an
original [importable model](examples/weber-tabulated.asw) from the primary tip
table. Its zero-wind aerodynamic stations and integrated strip area are checked
independently; its normal-strip drawing differs from the measured root/tip
outline. Four independent vortex calculations agree with the implemented
discrete model. Sixteen packaged-WASM replays and an offline WebGL workflow pass,
including computed cases and explicit invalid-refinement rejections.

The inviscid matrix contains 30 computed and 96 rejected cases. Growing local
tip velocity still prevents a full-range mesh-convergence claim. This provides
a reproducible geometry and implementation check; manufactured sections,
tunnel conditions and a physically justified refinement treatment remain open.
Open the model in rigid mode at speed 49.6824, alpha 2.1, density 1.2256, fixed
PG Mach zero and with section stall disabled. Compare 24, 48 and 96 requested
intervals; mandatory table stations increase the actual counts to 70, 94 and
142. Higher requested resolutions expose the unresolved local-Mach rejection.


## Flexible-wing structural reconstruction

The [Durrant wing study](docs/validation/durrant-structure.md) reconstructs two
cantilevers from published stiffness and mass tables and checks their vacuum
modes against an independent energy-based beam model. The first nine frequencies
converge under refinement; at 32 requested intervals their maximum difference
is 0.767%. Search, tangent, gravity and source-property sensitivities are retained.

The thesis appendix contains materially different inputs, and the reported
zero-airspeed ASWING air-mass settings are unknown. Independent still-air inertia
makes the first bending frequencies close to the reported ASWING values, but
does not establish the original setup. Experimental flutter is reported at
structural failure rather than linear instability onset. This study therefore
adds structural verification and source evidence, while experimental/flutter
validation remains open. It changes no production equations or UI behavior.


The [low-positive-airspeed extension](docs/validation/durrant-low-speed.md)
adds published Case 4 section properties and verifies the approach to
independent still-air structural modes. Twenty native cases cover three
meshes and speeds from 1 to 0.001 m/s, plus tangent/search, lag-off and
time-unit checks. Six WASM replays and an offline browser workflow for both
wings pass. The study confirms retained air inertia and vanishing aerodynamic
damping in this finite-frequency limit. That historical study did not verify
exact zero airspeed. The later [primary ST-4 study](docs/validation/st4-primary-study.md)
checks a separate fixed-frame, zero-speed still-air modal path; the ordinary
flow solver's positive-speed guard is unchanged. Broader nonlinear rest launch,
slow aerodynamic roots and experimental flutter remain unverified.
