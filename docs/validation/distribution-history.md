# Sampled time-history distributions

The ASWING 5.97 [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
“Time-Marching Calculation,” describes `SS`/`CC` overlays of distributions across
all stored time snapshots and `WW` output of all spanwise distributions.
OpenSwing now exposes that workflow in the Span loading and Structure tabs.
This is a workflow implementation, not a claim that its CSV is ASWING's legacy
`WW` byte format or that the underlying aircraft solution has ASWING parity.

## Browser behavior

After a time solve, the **Time distribution view** selector provides:

- **Current snapshot**: the existing distribution at the selected computed state.
- **All snapshots**: a trace for every stored snapshot, with the currently
  selected state highlighted. Traces are not decimated.
- **Sampled envelope**: signed minima and maxima at each material station,
  retaining each extremum's snapshot index, time, step and forcing side.

Select an overlay trace or envelope point (click, or keyboard focus and Enter
or Space) to inspect that actual snapshot. Selection also updates the 3D state,
metrics, structural/load plots and time scrubber, and pauses playback. It does
not launch an analysis or mutate a stored result. Saved computed solutions
retain the chosen view and quantity.

**All snapshots CSV** includes all beams and snapshots in the selected data
family: structural section loads/strains, aerodynamic strips, or concentrated
body shoulder forces. Its values use raw input units and dimensionless strains,
independent of the displayed stress conversion. The structure export includes
all existing section CSV quantities and the absolute torsional shear stress.
Strip exports include total, apparent and circulation-rate forces and moments
where available. Each row records a zero-based snapshot index, time, time step,
forcing side and zero-based station ordinal within its beam. Select a shoulder
force quantity to export the separate concentrated-force family.

**Envelope CSV** includes the selected beam and quantity, with explicitly named
display units (including microstrain or converted stress), both signed extrema,
their snapshot metadata and available/total snapshot counts. Tied values retain
the first stored snapshot. Duplicate times and distinct forcing sides remain
distinct; coincident spatial stations retain their separate ordinals.

## Physical meaning and limits

Structural quantities retain their recovered local material axes. Aerodynamic
force per length uses each snapshot's current strip length and body-axis force;
switching the geometry view to Earth axes does not rotate these quantities.
Concentrated shoulder forces remain impulses in force units, separate from
force per length. The envelope can combine extrema from different times and is
not itself an equilibrium or a simultaneous loaded shape.

Only finite numeric samples contribute. Null, absent, nonfinite and nonnumeric
values remain missing, never zero; incomplete envelopes report the missing
count, and all-missing stations have blank CSV extrema. Plotted curves break at
missing values. Matching uses the ordered material parameter stations (and
interval endpoints for structural rows), never current deformed position.
Different grids are rejected explicitly; no spatial interpolation is invented.
The full raw history CSV remains available even when grids cannot be compared.

A sampled extremum is not a bound between time steps or spatial stations.
Element midpoint samples can miss support and concentrated-load peaks. Refine
both time and spatial resolution. The existing BDF initial-reaction limitation
also applies: an envelope does not repair a nonconvergent initial transient.

## Independent checks

`tests/distribution-history.test.mjs` checks signed extrema and event-side ties,
an analytical spatially varying sinusoid whose unsampled continuous peak is
larger than its sampled maximum, missing data, doubled stations, changed grids,
current-length normalization, separate force impulses, unit conversion and
complete multi-beam CSV exports. Inputs are frozen to detect mutation.

`tests/browser/distribution-history.spec.js` runs the original instrumented
spring through the packaged WebAssembly kernel while offline. The beam has
length 2 m, EA = 1000 N and material damping time 0.02 s, with a 2 kg tip mass.
Thus k = 500 N/m and c = 10 N s/m. It starts at q(0) = 0.02 m, qdot(0) = 0,
with zero gravity and no applied engine force. Added shell coordinates only
provide recovery locations; they do not alter the mechanics.

The independent reference uses wd = sqrt(243.75) rad/s:

```
q(t) = .02 exp(-2.5 t) [cos(wd t) + (2.5/wd) sin(wd t)]
qdot(t) = -.02 (250/wd) exp(-2.5 t) sin(wd t)
mechanical axial strain = q(t)/2
internal axial force = 500 q(t) + 10 qdot(t)
```

Three-stage Radau IIA advances 0.4 s at steps 0.04 and 0.02 s. Displacement,
mechanical strain and total internal force are checked at every accepted
snapshot; the finer step must reduce displacement error by more than a factor
of 20. Refinement branches from the same computed initial checkpoint, preserving
its completed physical state. Independently, the linear discrete reference uses
the Radau stability function
`R(z)=(1+2z/5+z²/20)/(1-3z/5+3z²/20-z³/60)`
at the analytical poles `-2.5 ± i sqrt(243.75)`. This distinguishes expected
time-discretization error from a kernel defect. Envelope minima are
compared with the analytical values sampled at those actual times, rather than
with a different continuous-time extremum. Browser checks also cover selection,
raw/display-unit exports, result immutability, missing data, grid rejection,
archive restoration without new analysis and desktop/mobile layout.

The existing `time.spec.js` flap-forced free-flight workflow checks aerodynamic
force-per-current-length extrema and complete history export. The existing
`body-shoulders.spec.js` checks the separate force-impulse envelope against its
analytically checked sinusoidal gust history. The solution-archive regression
continues to cover steady, time, modal and frequency restoration.

Run:

```sh
node --test tests/distribution-history.test.mjs tests/frequency-overlays.test.mjs tests/frequency-comparison.test.mjs tests/projects.test.mjs tests/solutions.test.mjs
npm run build
npm run test:browser -- tests/browser/distribution-history.spec.js tests/browser/time.spec.js tests/browser/body-shoulders.spec.js tests/browser/solutions.spec.js
```

## Recorded verification

All **45 JavaScript tests passed**. The browser batch passed all ten existing
workflows and both independent spring grids. Its dedicated history workflow
then failed an assertion requiring exactly zero torsional stress: the computed
residual was about 1e-16 MPa. The export correctly preserved it. The corrected
assertion checks the actual raw-to-MPa conversion and a physical near-zero
residual tolerance. The dedicated workflow subsequently **passed** using the
retained numerical histories, imported through the public solution archive
path after matching their provenance to a live worker. Every physical reference
check runs again on every retained sample during replay. No production code or
numerical results changed for this test correction. The earlier failed batch
remains recorded as failed, rather than being relabelled as a pass.

The first browser attempt had also used an overly tight continuous-time
threshold for the coarse grid. Its measured error matched the independent
Radau stability-function prediction within about 5.3e-14 m. The test now checks
that discrete reference directly and separately checks time-step convergence.

| Step (s) | Snapshots | Maximum displacement error (m) | Maximum strain error | Maximum force error (N) | Displacement discrepancy from discrete reference (m) |
| --- | --- | --- | --- | --- | --- |
| 0.04 | 11 | 6.19207e-7 | 3.09604e-7 | 3.11729e-4 | 9.04051e-14 |
| 0.02 | 21 | 2.00112e-8 | 1.00056e-8 | 9.91023e-6 | 9.61384e-15 |

The displacement error decreases by **30.943×** when the step is halved.
Errors in the first three columns use the continuous analytical solution at
actual snapshot times. The last column isolates numerical differences from
the independent discrete method. The signed sampled strain range is about
-0.00604566 to +0.01; this is not a continuous-time bound.

[The machine-readable record](distribution-history.json) retains both sampled
histories, physical errors, 179 source identities, four tested asset hashes,
both browser-batch outcomes and screenshot hashes. Desktop and mobile
structural envelopes and the corrected mobile shoulder plot were inspected.
The release audit separately checks the final downloadable archives, exact
source/runtime/build identity and the unchanged native/WASM study provenance.

The [retained numerical fixture](distribution-history-fixture.json) contains
the two unmodified exported histories and their original source identities.
It is original OpenSwing benchmark output and is included in the source archive.
To replay that recorded output through the public archive path, run:

```sh
OPENSWING_HISTORY_REPLAY=docs/validation/distribution-history-fixture.json npm run test:browser -- tests/browser/distribution-history.spec.js
```

The default command above performs fresh physical solves.
The recorded fixture SHA-256 identifies the actual retained data used here.
No unverified replay is accepted when its source or numerical provenance
differs from the loaded worker. Reconstructed UI cases do not relabel the
origin of the numerical results.

The native numerical kernel is unchanged. This does not close the full
ASWING/aircraft/experimental validation requirement.
