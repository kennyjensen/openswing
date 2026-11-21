# Durrant Case 4 instability study — historical kernel

**All modal roots, crossings and portability results below use the kernel before
its apparent-rate self-influence correction. They are retained diagnostic
evidence, not current-kernel flutter predictions.** Independent loaded-tangent
and quarter-chord-axis checks exposed a singular own-bound contribution to the
apparent pitch-rate load. The correction is now integrated and changes these
roots. In four prescribed diagnostic cases it leaves the nonlinear bases
unchanged; at the 25% wing's N8, 24 m/s point the formerly growing matched mode
becomes damped. Those probes do not locate a corrected flutter boundary or
establish agreement with the published values. The full loaded-wing validation
remains unresolved.

The study extends the existing structural and low-positive-speed reconstructions
to loaded aeroelastic modes near the reported instability boundaries. It has not
established experimental validation.

The reference is Matthew Durrant's 2024 thesis,
[Aeroelastic Instability of Reduced-scale High-altitude Pseudo-satellite Wings](https://doi.org/10.6084/m9.figshare.26317378.v1).
Tables 4.5–4.6 on printed page 80 (PDF page 93) were checked against the rendered
page. The numeric transcription in `durrant-flutter-reference.json` retains all
four published ASWING aerodynamic cases, every experimental destruction speed,
failure labels and missing measurements. The PDF's pinned hash and the source
page inspection hash accompany those data.

The pilot uses the unambiguous Case 4 aerodynamic table: dCLda=2π/rad,
CLmax=1, CLmin=−0.3, alpha=4°, Cm=−0.1 and zero Cdf/Cdp. Tables 3.8–3.10
print positive CLmin values for their nominal unstalled lower bounds; those
signs are not silently corrected. Main-table structural and inertia properties
are retained, with no concentrated instrumentation masses. The incompatible
appendix model and its Weight-record ambiguity remain separate source gaps.

The vertical wing points along +z, its chord is +x and its normal is −y. Hence
the specified geometric incidence is body beta, with body alpha zero. The pilot
uses 4.17°, density 1.225 kg/m³, gravity along −z at 9.805 m/s², and fixed PG
Mach zero. The thesis does not establish all original mesh, gravity, PG or wake
settings; these are explicit reconstruction choices requiring sensitivity checks.

The published Case 4 boundaries at this incidence are 33.21 m/s for the 25%
spar wing and 24.58 m/s for the 75% spar wing. The initial probes use 28/36 and
20/28 m/s respectively, with eight requested uniform intervals plus the required
mass-distribution breaks. Each point solves a new nonlinear loaded equilibrium
and linearizes the complete continuous residual. Local full-descriptor searches
retain weak inertia and verify both left and right original-pencil residuals.
They do not classify the entire finite spectrum.

Before a critical-speed result can be trusted, the work must establish a matched
mode and a sign bracket, refine the speed and spatial mesh, vary differentiation
step and search settings, and examine the unresolved source/setup sensitivities.
Failures and unstable equilibria remain outcomes rather than being removed from
the comparison. No stiffness, mass, aerodynamic coefficient or numerical rank
threshold is adjusted to fit the published speeds.

Linear growth-rate crossing and structural destruction are distinct observables.
The thesis reports subcritical limit cycles below destruction and distinguishes
flutter, divergence and combined failures in its tables. The individual
destruction measurements cannot be treated as repeated measurements of the
linear eigenvalue crossing or converted into a validation tolerance without
additional evidence.

The evidence archive preserves the former inverse-actuator kernel and every
study input. The full ASWING goal and experimental validation remain open.

## Recorded finite-speed evidence

Five fixed plans have completed with recorded zero process exits: four pilot
points, ten interior-speed/tangent/mesh cases, six explicit setting/unit
sensitivities, six additional mesh points, and seven wider speed-path points.
All 33 computations retain converged nonlinear bases and left/right
original-pencil backward errors below 1e-9. These residual checks verify the
computed discrete equations; they do not independently validate the physical
model or establish the entire finite spectrum.

At the published comparison speeds, reducing the centered differentiation step
from 1e-5 to 1e-6 changes the matched oscillatory roots by at most 4.80e-10 in
the magnitude-scaled complex metric. Changing the input time unit from one
second to 0.1 second changes the checked physical roots by less than 6.55e-11.
The unit case rescales source stiffness/weight, speed, gravity and eigenvalue
search shifts consistently and converts returned eigenvalues back to 1/s.
Two shifted searches are retained at each diagnostic point. They agree on
the matched oscillatory roots but can return different real roots, so no
complete-spectrum stability conclusion is drawn.

The historical kernel produced an oscillatory unstable interval for the 25% spar wing that the initial two
endpoint probes missed. At 24 m/s the sampled mode is
3.90533 + 167.89435 i per second, while the corresponding mode at 28 m/s is
−5.49659 + 155.56651 i per second. Mechanical-shape matching resolves a
destabilizing crossing between 20 and 24 m/s and a stabilizing crossing between
26 and 28 m/s. The 75% wing has a resolved matching bracket between 22 and
22.2 m/s. A local full-descriptor search still does not prove that these are
the first instabilities over every speed or exclude unreturned unstable modes.

An independent postprocessor matches complex displacements and chord-scaled
rotations using a trapezoidal jig-span metric. Shapes on different meshes are
linearly interpolated onto their union of stations. One-to-one assignment
requires modal assurance above 0.8 and both competing-assignment margins above
0.1. Boundary refinement additionally requires matching to both bracket
endpoints, recovery of the selected root with a second shift, relative speed
bracket width below 1e-4 and normalized growth below 1e-6. Thresholds are not
adjusted to match the thesis.

The nine planned speed-boundary refinements are complete:

| Wing | Requested intervals | Transition | Computed speed (m/s) | Frequency (Hz) |
|---|---:|---|---:|---:|
| 25% spar | 8 | Destabilizing | 23.55465 | 26.88190 |
| 25% spar | 16 | Destabilizing | 23.67665 | 26.98752 |
| 25% spar | 32 | Destabilizing | 23.71845 | 27.00060 |
| 25% spar | 8 | Stabilizing | 27.60998 | 25.14318 |
| 25% spar | 16 | Stabilizing | 27.43336 | 25.30340 |
| 25% spar | 32 | Stabilizing | 27.38060 | 25.33258 |
| 75% spar | 8 | Destabilizing | 22.18472 | 19.01759 |
| 75% spar | 16 | Destabilizing | 22.53207 | 18.76477 |
| 75% spar | 32 | Destabilizing | 22.63777 | 18.66475 |

Requested counts 8, 16 and 32 become 10, 18 and 34 actual elements after
the required mass breaks. From N16 to N32, the 25% destabilizing and stabilizing
speeds change by 0.1765% and 0.1923%, respectively; the 75% destabilizing speed
changes by 0.4691%. These are measured mesh trends, not an established continuum
error bound. The published Case 4 values remain 33.21 and 24.58 m/s.
The historical 25% unstable pocket and lower 75% crossing persist across those
meshes. The self-field correction invalidates using this table as current
physical predictions; published agreement remains unresolved.

Static deformation supplies a useful diagnostic. For the 25% wing at
33.21 m/s, the saved tip chord angle about body z is −12.5585°. A separate
straight-beam approximation with uniform pitching-moment density predicts
−12.5361° from

`theta_tip = rho * U^2 * chord^2 * Cm * length^2 / (4 * GJ)`.

This approximation omits offset circulatory torque, bending/finite-rotation
transport and local Mach correction. It helps explain the large washout but is
not an independent solution of the full loaded equilibrium. The local lift
coefficient approaches the lower limit, and the smooth leakage law affects
the tangent before the literal stalled-section flag becomes true. Disabling
stall, freezing influences, and using the conflicting Nea=0.005 m are recorded
as different model/settings sensitivities. None is silently substituted for
the main-table reconstruction or accepted as a calibration.

Four packaged-WASM replays pass: the 25% unstable and damped cases, the 75%
unstable case, and its consistently rescaled time-unit equivalent. They compare
728 physical base values and 14 complex roots across the retained shifted
searches. Maximum scaled differences from native are 3.71e-13 for base values
and 7.53e-11 for roots. Mechanical mode shapes and growth signs agree. The
comparison window is explicitly 0.1–40 Hz, separate from all-root stability or
experimental validation.

Two independently recorded offline browser workflows now pass, one per wing.
Each imports the reconstructed ASW source and exact mesh, checks the physical
equilibrium and retained low-frequency roots, exports modal CSV, and verifies a
healthy WebGL context and mobile layout. Four matched complex roots differ from
native by at most 2.78e-9 per second in any component. Both desktop and mobile
captures for each wing were inspected. All 58 numerical module hashes match the
historical pre-correction kernel. These are browser portability checks, not independent flutter
validation.

The original combined browser workflow was interrupted, and an earlier retry
timed out on its second solve. Those outcomes remain recorded. Splitting the
workflow retained every per-wing assertion and the original 240-second solve
deadline; each wing now starts on a fresh page. The combined sequential model
switch itself remains an incomplete workflow. The successful per-wing runs
were sequenced before heavier native jobs, without relying on process-pause
signals to establish resource isolation.

Interrupted boundary supervisors retain their original nonterminal records.
Their process identities were confirmed absent and all 66 study fingerprints
were unchanged before recovery. The final resumed supervisor recorded exit zero.
A separate auditor verified all nine completed boundaries across 88 retained
case records (including exact cached duplicates): case hashes, original-pencil
errors, both shifted searches, opposite-growth endpoints, shape matching and
both refinement tolerances. Maximum nonlinear base residual was 2.45e-13 and
maximum original-pencil backward error was 1.37e-14. All 58 production modules
match the historical pre-correction kernel. Its complete 1,216-test native
baseline is separately recorded; it does not cover the corrected kernel.

The [source audit](durrant-source-audit.md) supports the section-centroid inertia convention.
Independently integrating the published segment tables and their parallel-axis
terms gives whole-wing CG inertias within 0.030% of Table 2.21. The 75% segment
mass integrates to 0.0724994 kg versus the printed whole-wing 0.0726 kg; this
0.1386% inconsistency is retained without rescaling. The source explicitly says
the destruction-test wings were uninstrumented. Figure 4.10 covers all four
aerodynamic cases at 4.17 degrees physical incidence, with Case 4 solid; its
qualitative branch shape differs from the historical unstable pocket. The original
software beta input remains unavailable. None of these findings establishes the
exact input used for the published ASWING computation.

A completed independent section derivation covers both heave and pitch,
separated circulatory/rate loads and apparent-mass forces/moments, with
axis-change virtual work, energy and special-axis checks. Twenty native
prescribed-motion configurations and 100 frequency samples agree with an
independent finite-wing section transfer to 2.67e-10 scaled component error.
A separate energy-based unloaded wing model, without production imports,
recovers the two low native roots with N32 differences 0.0181% and 0.0132%
using the documented global Glauert aerodynamic sampling. Arithmetic-point
and intermediate quadrature variants remain recorded. This unloaded analogue
has zero camber, Cm, body incidence and gravity, with stall disabled; it is not
a published Case 4 calculation. Its historical native comparisons and independent-reference WASM replay are
complete; see `durrant-unloaded.md` for source scopes and current replay status.

Four loaded N8 diagnostics at 24 m/s retain the original baseline and alter
one physical effect at a time. Disabling stall or gravity retains the matched
unstable mode: growth changes from +3.90533/s to +3.92048/s or +3.87731/s.
Setting Cm to zero nearly removes the large static twist. Setting section
camber and body incidence both to zero retains negative twist and produces
negative section lift. In these last two cases the original unstable mode is
unmatched in both local searches; returned damped roots do not establish that
the same branch stabilized or that the full system is stable.

The source explicitly lacks measured deformation near flutter. The static bench
test spans comparable twist angles, but it is a different load case. An
independent reconstruction now reproduces the saved N8 static wrenches, local
elastic-axis torsional constitutive balance and three twisting-work profiles.
Across the baseline, Cm=0 and zero-incidence variants, strip forces agree within
8.77e-15 N and root force/moment balances within 1.03e-12 N and 3.27e-13 N m.
The imposed Cm is the dominant source of baseline mean twist. These checks
retain finite-rotation bending transport and distinguish discrete interpolation
from a continuum virtual field; they establish no loaded mesh-convergence or
unsteady-tangent result. See `durrant-loaded-equilibrium.md`. The subsequent loaded-tangent and near-axis checks found the own-bound
self-field defect summarized above. Source/setup ambiguities and the
distinction between linear instability and experimental destruction remain
necessary parts of any eventual validation.

## Portable historical evidence

`durrant-flutter-records.zip` preserves 261 original paths as 253 hashed
content objects: source snapshots, five fixed plans, four boundary runs,
completed and interrupted terminal records, numerical results and portability
artifacts. The archive index retains original paths as provenance; it does not
require those paths to exist. `durrant-flutter-records.json` pins the ZIP.

```sh
.venv/bin/python scripts/audit-durrant-flutter.py --archive docs/validation/durrant-flutter-records.zip --output /tmp/durrant-history-audit.json
.venv/bin/python scripts/plot-durrant-flutter-history.py --output /tmp/durrant-history-figures
```

The auditor verifies archived kernel and study sources directly, every case
hash, terminal fixed-plan/final-resume exits, exact reused payloads, and all nine
mode-matched brackets at their original tolerances. An optional `--kernel-root`
requires that checkout to match the historical kernel; the corrected checkout
is expected to fail that comparison. No archive member is extracted or executed.
The plotter uses the repository's pinned matcher and labels all figures as
pre-correction evidence. The former plot and report remain in the archive.
