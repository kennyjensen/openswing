# ISAE validation coverage

## Current acceptance target: tested ASWING results

Completion requires reproducing tested ASWING cases using the same models
and operating settings. Experimental agreement is not required.
**P-1 reproduces all six stored CT curves (110 values).** The corrected-arc SA-3
comparison covers all 22 archived rows and seven outputs on three meshes.
All 66 solves converge; every 200-to-400 interval mesh check passes, but
reference differences remain. Fine-mesh CL / CD / CDi RMSE is
0.000344 / 0.000349 / 0.000000392. Pitching moment fails the coarser mesh check.

Frozen-influence Pazy curves remain close in selected outputs. AE-2's selected
displacement differs by 0.435% and sensor beta by −0.138°. An independent
field calculation rules out moving the receiver alone as a correction.
See the [reference status](isae-aswing-reference-status.md),
[SA-3 comparison](isae-sa3-accurate-arc.md) and
[AE-2 sensor diagnostic](isae-ae2-sensor-reference.md).

The historical 18 partial / 23 pending / 0 fully validated family tally below
is a study inventory, not the completion count for this revised target.
Experimental discrepancies and specimen-property corrections do not block
an otherwise established ASWING match. The new arc correction changes numerical
mesh construction, while model properties and solver tolerances remain unchanged.
The full project remains incomplete.

The [SA-3 velocity diagnosis](isae-sa3-velocity.md) verifies the sampled
kernels and rules out the tested curvature analogue as the main drag explanation.
The [full ST-3 static-output comparison](isae-st3-reference.md) now covers all
45 archived rows with the original signed weights. After accounting for printed
coordinate rounding, interpolated native output matches 269/270 structural
entries on all three meshes; the remaining tip moment is a 5.59×10⁻⁹ N·m
archived residual versus effectively zero. Another 90 conditional zero entries
are accounted for separately. The browser solve takes 3.68 s and agrees with
native output. This single static snapshot is close; the wider ST-3 family
and exact historical discretization remain incomplete.

The [accurate-arc correction](isae-sa3-accurate-arc.md) removes a confirmed
9.91% local interval-length error near the curved SA-3 tip. All 66 new native
states converge, but the archived drag gap remains. Old saved v0/v1 meshes keep
their original equations. The selected browser solve takes 8.72 s after 27.73 s
startup and agrees with native output; its project restores without solving.
Earlier P-1, ST-3, AE-1 and AE-2 numerical results retain their recorded source
versions; they are not newly rerun studies for the corrected arc kernel.

## Historical comparison record

The user has prioritized ISAE comparisons over further Daedalus Bode matching.

The [AE-2 low-aspect-ratio wing pilot](isae-ae2-pilot.md) now completes
six cold cases on three meshes with the unchanged literal model. All four
1% displacement mesh checks pass, with a maximum change of 0.0221%.
The finest result differs from the selected raw experimental displacement by
+166.2%; a separate archived ASWING control differs by +1.17%. Native solves
take 1.00–2.73 s; a selected browser solve takes 4.13 s after 29.32 s startup
and its saved project reopens without solving. Literal/report stiffness and historical setup differences
remain unresolved. This pilot is supplemental; AE-2's broader comparison
stays pending and coverage remains **18 partial / 23 pending / 0 fully validated**.

The [Pazy observable review](isae-ae1-observables.md) reconstructs 392 saved
mappings and preserves 184 unique measured scalars. Its 20,714-check arithmetic
audit passes. Chord-angle and sensor-elevation definitions do not explain the
twist mismatch; displacement projections change agreement modestly but do not
identify the exported Test 2 axis, baseline or filtering procedure. No model,
production default, fitted correction or family classification changes follow.

The [full frozen-influence Pazy comparison](isae-ae1-literal-frozen-curves.md) completes
196 airflow states at all 98 archived speed coordinates on two meshes, using
188 new cold solves and eight exact prior states plus two gravity baselines.
All 196 mesh checks pass. Fine-mesh displacement RMSE against archived ASWING
falls from 6.203/1.028 mm to **0.240/0.120 mm** at 5°/7°.
Experimental displacement agreement worsens; historical K/F remains unknown.
Independent saved-data audits pass 44,293 checks. One selected offline browser
solve takes 7.24 s after 25.29 s startup and agrees with native output; its
importable project restores without solving again. Production defaults stay
unchanged, and coverage remains **18 partial / 23 pending / 0 fully validated**.

The [conditional literal Pazy curves](isae-ae1-literal-curves.md)
complete 198/198 fresh cold states at 98 positive-speed coordinates on two meshes,
including independent gravity baselines. The predeclared 0.1% mesh-change gate
passes 196/196 checks. Fine-mesh differences from archived ASWING have
displacement RMSE 6.203/1.028 mm and sensor-elevation RMSE
0.04219/0.00822° at 5°/7°. These conditional comparisons retain the
historical setup uncertainties and experimental disagreements. The
[circulation correction](isae-circulation-finish.md) resolves a finishing-iteration
stall without changing the full-equation tolerance; the current browser case
takes 7.97 s, separately from 14.95 s startup. Original failures are retained.
Coverage remains **18 partial / 23 pending / 0 fully validated**.

The [full AE-1 Pazy sweep](isae-ae1-sweep.md) completes 186 states at all 92
supplied speed coordinates on two meshes. All 92 displacement mesh checks pass;
829,488 independent saved-data checks and three actual browser cases agree.
Experimental displacement and twist discrepancies remain. AE-1 moves to partial
numerical comparison, making the current source ledger **18 partial families,
23 pending and zero fully validated**. That sweep changed no production kernel
or hosted release. High-speed comparisons retain the published dynamic qualifications.

The [AE-1 lift-slope diagnostic](isae-ae1-section.md) adds six coupled states
on two meshes. A 2π/rad slope raises displacement and twist by about 2% but leaves
twist 8.25–16.04% below the three measurements; displacement agreement is mixed.
All three displacement mesh checks and 238,889 independent saved-data checks pass.
The [saved-load reconstruction](isae-ae1-loads.md) adds 71,043 checks without finding
a supported load-transfer or twist-output defect. Baseline coefficients and all
family classifications remain unchanged.

The [steady wall-root implementation](isae-ae1-wall-root.md) adds production
support for exact fully clamped lifting endpoints on an ideal solid image plane.
Eleven new regression cases pass; the derived native Pazy half-wing at 5°/30 m/s
has a fresh residual of 1.22e-14. The offline browser passes 693/693 checks
with a 7.83-second cold solve, separately from runtime startup. Strict physical crossing and unsteady-rate
rejection remain. The literal attachment error, setup/section assumptions and
experimental discrepancies remain open. Kernel count changes from 110 to 111;
historical studies keep their original source pins. Coverage is unchanged.

The [conditional literal Pazy comparison](isae-ae1-literal-pilot.md)
now compares two independent cold states using the ISAE model with only two
proven load-null, out-of-range Weight rows removed. At 5°/30 m/s, baseline-subtracted
tip displacement is 0.777% above the archived ASWING output and sensor-3 elevation
is 0.680% above it. The no-flow sag differs by 51 nanometres, near the archive's printed resolution.
The native case runs take 0.82/1.62 seconds; all 272 case/provenance checks pass (26 numerical gates and 246 pin checks). These are
conditional source-output comparisons with declared transverse gravity, not new
experimental acceptance. The historical mesh and complete operating state remain
unidentified; the subsequent full-curve and mesh studies are reported above. The primary-property
zero-gravity experimental studies keep their separate setup and results.

The [2026-10-25 corrected SA-6 comparison](isae-sa6-single-aileron.md) completes
966 states using the primary tables' separate single-aileron procedure instead
of simultaneous controls. Pooled roll RMSE improves 2.73%; yaw RMSE worsens
5.33%. Large-deflection discrepancies remain, with separate up/down measurements
now exposing the errors. Three transcription corrections and one unresolved
primary-table inconsistency are recorded. No family classification changes.

The [local SA-6 diagnosis](isae-sa6-local.md) adds 21 retained states and an
independent reconstruction of 3,444 strip loads. It identifies the calculated
stall-drag contribution to large downward-aileron yaw and retains the separate
circulatory discrepancies. Retrieved Clark-Y flap data supports an additional
finite-wing benchmark, not a direct replacement section polar. No coefficient,
equation, acceptance threshold or family classification changes.

The [R5 batched-circulation study](isae-ae3-batched-circulation.md) completed the matched 320-to-640-interval AE-3 20O-05 derivative comparison. All 40 execution checks and 276 saved-result audit checks passed, but the control derivative changed by **2.1591607%**, failing the unchanged **1% mesh-convergence gate**. The 320-interval derivative was reused after an exact full circulation-block comparison; the 640-interval derivative used the intended analytic circulation method. Nonlinear finite-control consistency has been checked on the [320-interval mesh](isae-ae3-320-finite-control.md), but has not been checked on the 640-interval mesh. The isolated candidate remains uninstalled; no production source promotion occurred. At that stage, coverage remained 17 partial, 24 pending and 0 fully validated.

The [R4 study](isae-ae3-full-mesh.md) remains a failed method-identity attempt: its completed 640-interval API call fell back to centered circulation derivatives. The earlier input-limit failure, three historical output-parity failures and all five earlier mesh failures remain. The [R3 study](derivative-sparse-refinement.md) retains its independent 320-interval accuracy checks.

The [saved-equilibrium solver optimization](seeded-corrector.md) and [final rank check](final-equilibrium-rank.md) pass selected native, WebAssembly and browser checks. They change no family classification or mesh-convergence verdict.

This is a coverage and failure ledger, **not a full-suite pass**. Parsing does not establish mesh construction or validate physical predictions. Every case remains short of complete experimental validation.

Earlier numerical studies retain their original source hashes. The [parser audit](reference-compatibility.json), [modal source audit](dense-staircase-transition.json), [point-static source audit](structural-static-transition.json), and [distributed-static source audit](distributed-static-transition.json) document the changes. These studies are not presented as fresh numerical reruns. The [distributed static workflow](distributed-static.md) contains literal-file solves and point-load controls. The [SA-6 study](isae-sa6.md) adds primary aileron comparisons, and the [SA-10 study](isae-sa10.md) adds winglet/tip-sail polars and matched-lift drag, with literal input conflicts, failed states and local-flow growth retained.

The [SA-12 study](isae-sa12.md) adds all six ground-effect polars, exact measured-angle calculations, three meshes, independent image-velocity checks and offline browser/WASM replays. Pose/datum and equivalent-flap section limitations remain. The completed [SA-11 comparison](isae-sa11-comparison.md) adds 5,304 states and 166 matched-lift requests with rejections and missing roots retained. The [SA-14 consolidation](isae-sa14-comparison.md) maps all116 digitized points,180 original polar rows and426 load-export rows, with conditional incidence geometry, high-angle errors and the swept-force defect retained. The [ST-2 comparison](isae-st2-comparison.md) adds77 Pazy static measurements,16 modal states, explicit setup conflicts and independent/runtime checks. The [primary ST-4 comparison](st4-primary-study.md) adds conditional vacuum/still-air comparisons with primary measurements and independent references. With the full AE-1 sweep, eighteen families now have completed quantitative studies of part of their scope; 23 await completed studies. No family is fully validated.

The [corrected primary Pazy study](pazy-loaded-comparison.md) audits CONM2 inertia signs against original Nastran mass matrices and adds225 static states,26 modal states,28 independent nonlinear references, all77 measured static rows and10 WASM/browser replays. The [earlier primary conversion](pazy-primary-comparison.md) is explicitly superseded. A small intrinsic extension–torsion term remains projected and bounded. Numerical agreement and mesh convergence do not resolve the experimental discrepancies or establish a full physical pass.

The earlier SA-12 downloads contained 13 partial families and 28 pending; the endpoint-repair release contained 15 and 26, and the pre-primary-ST-4 release contained 16 and 25. These counts are historical. The current workspace ledger has 18 partial families and 23 pending; it does not certify a new application release. The [SA-13 conditional diagnostics](isae-sa13.md) and primary Pazy supplement did not increase their historical counts.

| Case | Literal models parsed / total | Current evidence | Work remaining |
|---|---:|---|---|
| SA-1 | 1 / 1 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa1-current.json) | Resolve near-stall drag deficit and deep-stall branch selection; recover exact ASWING startup/discretization settings. |
| SA-10 | 6 / 6 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa10.md) | Resolve literal joint/geometry conflicts, primary setup and uncertainty, archived moment reference, near-stall drag and growing junction velocities. All six variants are mapped; one explicit joint reconstruction and failed states are retained. |
| SA-11 | 4 / 5 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa11-comparison.md) | Completed 5304-state sweep and 166 matched-lift requests retain 4077 rejected states and 128 missing roots. Resolve swept/junction flow, literal geometry, archived normalization/discretization and measurement uncertainty; PG alone does not resolve shocks. |
| SA-12 | 2 / 2 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa12.md) | All six polars and 75 lift/71 drag measured points compared across three meshes; resolve archived pitch/PG/discretization, plain-wing angle datum, equivalent flap section properties, near-ground slot effects and remaining measured discrepancies. |
| SA-13 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| SA-14 | 4 / 4 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa14-comparison.md) | All116 digitized points,180 polar rows and426 load-export rows are mapped. Resolve swept-force mesh behavior, high-angle/stall errors, original incidence/geometry/section-polar provenance, archive settings, moment reference and measurement uncertainty. |
| SA-15 | 1 / 7 | Import checked; physical comparison pending | Resolve variant parsing and map joined-wing units, trim and measured load/moment conventions. |
| SA-2 | 1 / 1 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa2-current.json) | Reconstruct the primary 45-degree planform, reconcile pressure-only force reduction, and resolve finer-mesh branch failures. |
| SA-3 | 1 / 1 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa34.json) | Reconcile experimental versus archived span/area; resolve failed branches and discretization/startup settings. |
| SA-4 | 1 / 1 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa34.json) | Resolve the numerous finer-mesh continuation failures and the experimental/archived geometry mismatch. |
| SA-5 | 1 / 1 | [Numerical comparisons; setup/discrepancy limits remain](isae-sa5.json) | Recover the CFD geometry, reference area and force-axis integration convention; this is a CFD comparison, not an experiment. |
| SA-6 | 7 / 7 | [Separate-aileron experimental comparison; discrepancies remain](isae-sa6-single-aileron.md) | Correct combined-test procedure and separate up/down targets are now compared. Resolve finite-deflection section/control properties, omitted fuselage, model/control geometry, remaining moment discrepancies and measurement uncertainty. |
| SA-7 | 2 / 2 | [Numerical comparisons; setup/discrepancy limits remain](isae-tandem.json) | Match tandem/canard geometry, per-surface coefficients, pressure correction and recorded trim settings. |
| SA-8 | 2 / 2 | [Numerical comparisons; setup/discrepancy limits remain](isae-tandem.json) | Reconstruct airframe inclusion and match the distinct CFD fore/hind/total lift series. |
| UA-1 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| UA-2 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| AP-1 | 2 / 2 | Import checked; physical comparison pending | Recover propeller RPM, input power and radial lift coordinates before comparing the slipstream-loaded wing. |
| AP-2 | 2 / 2 | Import checked; physical comparison pending | Map each engine lateral/vertical position, power and measured lift-to-drag condition. |
| P-1 | 0 / 0 | [Archived propeller curves reproduced; measurement differences remain](isae-p1.json) | Quantify measurement uncertainty; resolve nominal/true diameter and assess CdA independently of its calibration data. |
| P-2 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| P-3 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| P-4 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| P-5 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| ST-1 | 0 / 10 | [All literal models rejected; input audit completed](isae-st1-input-audit.md) | Resolve nine unterminated Engine blocks, ten undefined sensor frames and four surplus multiplier rows using explicitly reviewed derived inputs; preserve literal rejection. Recover the producing ASWING version/settings and verify beam, load, fixture and measurement definitions before physical comparison. |
| ST-2 | 6 / 6 | [Numerical comparisons; setup/discrepancy limits remain](isae-st2-comparison.md) | 77 measured static rows compared using simplified and corrected primary properties. The corrected primary study adds225 static states,26 modal states,28 independent nonlinear references and10 WASM/browser replays. Resolve literal attachments, exact load/fixture geometry, intrinsic extension-torsion representation, loaded-modal reference, experimental discrepancies and uncertainty. Earlier primary inertia conversion is explicitly superseded. |
| ST-3 | 8 / 9 | [Modal and static comparisons, including literal static/UI support; experimental discrepancies and torque/source conflicts remain](isae-st3-static.md) | Resolve static/modal experimental discrepancies, source properties, torque conversion and measurement/setup uncertainty; extend dense rank robustness beyond checked spectra. Literal signed static files now have a checked no-airflow UI workflow. |
| ST-4 | 32 / 33 | [Conditional primary vacuum/still-air comparisons; physical discrepancies remain](st4-primary-study.md) | 252 vacuum and 252 air states, 672 independent references, and 72 complete printed before/after triplets compared; six incomplete triplets retained. Resolve unreported zero-speed density, pylon inertia/offsets, fixture/in-plane stiffness, physical mode identity, higher sixth/seventh-mode mixing and remaining measured discrepancies. One literal missing-End file remains rejected. |
| ST-5 | 36 / 38 | [Literal and reconstructed rigid-joint comparisons; experimental discrepancies, attachments and custom link joint remain](distributed-static.md) | Three literal rigid-joint load cases now solve across five meshes. Resolve out-of-range attachments and rejected syntax, implement the custom link joint, and reconcile reference scaling, spline/geometry differences and experimental setup/uncertainty. |
| ST-6 | 0 / 0 | No archived model; reconstruction pending | Recover model and operating/load/measurement setup from the report and primary source. |
| AE-1 | 1 / 1 | [Full exported speed sweep; physical discrepancies remain](isae-ae1-sweep.md) | All 186 states and 92 displacement mesh checks complete, with selected browser replays. Resolve displacement/twist mismatch, section data, measurement axes/uncertainty, ideal-wall/setup assumptions and high-speed dynamics; literal attachment error and unsteady/general wall-root support remain; the scoped steady fully clamped root is implemented. |
| AE-2 | 4 / 5 | [Six-case literal pilot complete; broader comparison pending](isae-ae2-pilot.md) | Four displacement mesh checks pass, but one raw measured point differs by +166.2%. Extend the separate video/strain-derived comparisons across incidences and layups; resolve literal/report stiffness, speed/atmosphere, datum and uncertainty. The separate archive control differs by +1.17%; it is not an experimental pass. |
| AE-3 | 6 / 6 | [320-to-640 derivative checks pass; 1% mesh gate fails](isae-ae3-batched-circulation.md) | Resolve the 20O-05 matched 320-to-640 mesh-convergence failure (2.1591607% versus the unchanged 1% gate) and perform nonlinear finite-control consistency checks on the 640-interval mesh. Resolve the separate 20O-04 convergence failure and experimental amplitude/incidence/sign, section-control and fixture/stiffness matching before driven-roll and reversal validation. The R5 execution and saved-result audits pass, but the isolated source remains unpromoted and all historical failures are retained. |
| AE-4 | 5 / 5 | Import checked; physical comparison pending | Resolve Pazy attachment stations, then reconstruct loaded and unloaded flutter sweeps and distinguish linear onset from limit-cycle response. |
| AE-5 | 1 / 2 | Import checked; physical comparison pending | Match the low-aspect-ratio wing supports, laminate, base deformation and measured flutter boundary. |
| AE-6 | 32 / 33 | Import checked; physical comparison pending | Zero-area models now import for structural/vacuum analysis. Recover a documented positive aerodynamic reference area and reproduce the exact pylon masses, gas mixtures, hanging preload and flutter conditions; ST-4 numerical checks do not validate aeroelasticity. |
| AE-7 | 5 / 6 | Import checked; physical comparison pending | Reconstruct the low-aspect-ratio nonlinear time-response settings and compare limit-cycle amplitude/frequency with time-step and mesh refinement. |
| FFWT-1 | 0 / 5 | All literal models rejected | Resolve documented legacy input semantics before reproducing the recorded loads, constraints and comparison quantities. |
| FFWT-2 | 1 / 53 | Import checked; physical comparison pending | Resolve rejected inputs and reproduce free-roll constraints, hinge motion and time-history sampling. |
| FFWT-3 | 0 / 6 | All literal models rejected | Resolve documented legacy input semantics before reproducing the recorded loads, constraints and comparison quantities. |
| FFWT-4 | 2 / 9 | Import checked; physical comparison pending | Resolve rejected hinge inputs and reproduce each recorded gust, support condition and root-moment reduction. |
| FFWT-5 | 1 / 7 | Import checked; physical comparison pending | Resolve nonmonotone joint tables and reconstruct the equilibrium branch and flutter sweep. |

SA-9 is absent upstream. The 279-model total also includes numerical-convergence directories outside these case folders.

Exact file paths and import errors are retained in [the inventory](isae-suite-inventory.json) and [the machine-readable coverage ledger](isae-coverage.json).

The [exact-endpoint source transition](endpoint-source-transition.json) records the terminal-knot interpolation repair and completed regression accounting. Earlier studies retain their original solver hashes; none is relabelled as a fresh physical rerun on the repaired source.

The [sparse modal adjoint audit](modal-adjoint.md) checks a faster left-vector recovery on all 26 saved corrected Pazy modal matrices and three fresh offline browser cases. Physical equations and finite-root classification are unchanged. Historical studies retain their original source pins; this numerical optimization adds no fully validated family.

The [zero-reference/ST-4 audit](zero-reference.md) accepts 64 additional literal inputs for structural/vacuum use, giving177 parsed and102 rejected models. It checks81 modal states against independent energy and continuous beam solutions, plus three WASM and three offline browser cases. Experimental setup and source discrepancies remained at that stage; ST-4 was supplemental numerical evidence and the historical 16/25 family totals were unchanged.

The [primary ST-4 study](st4-primary-study.md) completes conditional experimental
comparisons without declaring physical validation. At 32 intervals the first
three air frequencies are within 0.4712% of independent continuous references,
with minimum kinetic modal assurance 0.999913. Their mean absolute experimental
discrepancy is 9.264–9.296%, with a maximum of 54.867%. Density 1.225 kg/m³ is
assumed because primary zero-speed density is unreported; flutter mixtures are
not substituted. Sorted triplets assume the reported modes are the reduced
model's lowest three, without asserting physical mode correspondence. Higher
sixth/seventh-mode mixing remains. The 176 selected native checks, one JavaScript
check, three WASM replays and three fresh offline browser checks are numerical
and workflow evidence. The new exact-zero-speed still-air path is limited to
stationary fixed-frame modes; it adds no nonlinear rest-launch or flutter pass.
