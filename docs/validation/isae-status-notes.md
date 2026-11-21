# ISAE comparison notes

The current registered counts and failed-error summaries are in [ISAE_STATUS.md](ISAE_STATUS.md). The latest [SA-6 roll/yaw comparison](isae-sa6-span-native-20261101.md) covers all 14 native series under its stated hypotheses.

The material below preserves the previous status-file narrative and supplemental scopes. Its earlier study summaries describe their original coverage; they are not additional independent reference data. The original 42-row main table has moved to the top-level status file without any row changes. The exact previous file is [retained](../../artifacts/isae/sa6-span-native-20261101/ISAE_STATUS.before-compact.md).

Updated 2026-11-01. The full project and historical reproduction remain unfinished.

**SA tolerance: 3%.** Continuous references use `max(original absolute tolerance, 0.03 × abs(reference))`.
References with magnitude at most `1e-8` retain their original strict comparison.
Numerical convergence and physical-validity checks are unchanged. Non-SA rows retain their earlier results and tolerances.

Verified default SA scopes: **6,094/15,226 checks**; including the separately listed supplements: **9,861/22,232**.
The [3,179-job SA rerun](../../artifacts/isae/sa-three-percent-20261029/analysis/summary.md) supplies the baseline; SA-5 includes its later reporting correction, and SA-10 includes the [origin-CM reanalysis](../../docs/validation/isae-sa10-moment-origin-20261031.md).
A check is one archived scalar output. Counts include both declared meshes, failed solves and blocked comparisons;
they do not mean that an entire case family is validated. SA-9 is absent upstream.

Current priority: [SA-6–SA-10](../../docs/validation/isae-sa6-sa10-focus-20261031.md).
Browser verification of the latest moment reporting is [pending](../../artifacts/isae/sa10-browser-origin-20261031/HANDOFF.md)
after UserLAnd disconnects; automatic browser-test retries are suspended. Counts below are unchanged.
The [current SA-6 level-flight comparison](../../docs/validation/isae-sa6-level-input-comparison-20261101.md)
matches **220/220** roll/yaw values across five configurations, eleven controls
and two meshes under the fixed gain-ratio/strength-20 input hypothesis. Typical
errors are 0.34–0.35%, maximum 0.885%. At the same strength, literal deck inputs
give 138/220; their failed errors are typically 7.83% (25c) and 10.40% (30c).
The default-strength pilot improves 21/40 to 31/40 but loses two checks, so it
is not extended. All 208 small serial calls and independent field/source checks
finish. Native settings remain unverified; this qualified scope does not alter
the registered default counts or resolve post-stall pitch-rate errors.
The [SA-6 native-table catalogue](../../docs/validation/isae-sa6-native-tables-20261101.md)
adds 220 author-tabulated ASWING moment references beyond the raw-export scope.
Ten exact printed response pairs suggest different level-flight control gains
in three configurations; the supplied decks are retained. Re-scoring the old
saved study gives 22/22 level-flight matches for 15c, 20/22 for 20c, but only
4/22 for 30c (failed errors typically 10.01%, maximum 11.76%). These are qualified
historical comparisons, not current-production validation. Ten reader tests and
2,244 independently verified scalar comparisons finish without aircraft solves.
Native run metadata and the 10-inch model's geometry conflict remain unresolved;
all registered counts below are unchanged.
The [SA-6 matrix-precision audit](../../docs/validation/isae-sa6-matrix-conditioning-20261101.md)
replays all 88 saved state systems. Single precision changes coefficients by at
most 1.63e−6 and changes no decisions: the qualified result stays 2,780/3,168,
including 282/528 pitch-rate checks. Saved linear-solve error is far smaller
than the native gaps. Failed fine-mesh pitch-rate errors remain typically
20.81% (CXq), 18.84% (Cnq), 3.84% (CLq) and 3.96% (Cmq). The replay takes 1.66
seconds without aircraft solves; all 6,336 old/new decisions are independently
verified. This adds no registered passes or evidence about native precision.
The [SA-6 public-history audit](../../docs/validation/isae-sa6-source-history-20261101.md)
finds all four paired models, 44 native matrices and the retained driver
unchanged across 13 populated commits (637 file checks). The driver's
15%-chord filename has always loaded the 35%-chord model in that history.
No alternate input or producing setting was recovered. The qualified state
result remains 2,780/3,168; existing errors and registered counts are unchanged.
The [rigid steady browser control](../../docs/validation/fourier-wake-ui-20261101.md)
now exposes the optional continuous-wake comparison in source, including angle
sweeps and saved settings. Twelve JSON-boundary and thirteen JavaScript checks
pass. Rendered/WASM verification and refreshed bundles remain pending; this
interface work adds no ISAE passes or new aircraft comparisons.
The [continuous Fourier wake diagnostic](../../docs/validation/fourier-wake-nonparallel-20261101.md)
now supports arbitrary straight-trace orientations, shared tips and crossings.
Nineteen targeted tests pass; all 58 SA-7 reference integrals still agree to
roundoff. On 20 valid saved SA-10 Fourier states, CDi changes only 0.019–0.391%,
with no pass/fail changes. Failed CDi errors have median 5.72%, maximum 9.22%;
failed efficiency errors have median 8.36%, maximum 8.55%. All 12 rejected
Fourier states remain rejected. This explicit diagnostic leaves default
outputs and registered counts unchanged. The saved-state replay takes 3.62
seconds without aircraft solves; the post-stall discrepancies below remain.
The [SA-7 near-aligned-wake audit](../../docs/validation/isae-sa7-near-coplanar-wake-20261101.md)
isolates a large coarse-grid mutual-quadrature error at 18°, where wake traces
are only 2.025 mm apart. Its magnitude accounts for 69% of the N20 CDi
discrepancy. A consistent smooth-wake reconstruction reduces that error from
11.10% to 3.12%, but gives 197/203 over the full polar, with six CDi failures
3.12–3.97% low. It is not adopted. Independent high-precision and energy
controls verify the diagnosis; no new aircraft solves or registered gains.
The [SA-7 reported-count check](../../docs/validation/isae-sa7-reported-node-count-20261101.md)
tests the report's ambiguous 40-node count. Twenty intervals per wing reduce
the −5° efficiency error from 3.54% to 0.42%, and give 199/203 checks across
the full polar at strength 40. Four CDi/efficiency failures remain, with median
error 7.36% and maximum 11.49%. Following the native angle sequence gives the
same result. This is a separate coarse-mesh diagnostic, not an authenticated
native mesh or a registered gain. All small serial processes have finished.
The [SA-7 efficiency audit](../../docs/validation/isae-sa7-efficiency-definition-20261101.md)
checks all 58 saved strength-20 states. A counterfactual that carries mutual
cores into Trefftz reporting gives 406/406 scalar matches, but fails exact
opposite-wake cancellation by producing spurious induced drag. It is not adopted
or counted as validation. The documented result remains 404/406 in that
separate diagnostic; registered results below are unchanged. No new solves ran.
The [SA-8 source follow-up](../../docs/validation/isae-sa8-native-body-report-20261101.md)
finds an author-reported ASWING issue with constant-section body doublets in the
SA-14 discussion. SA-8's stored body has that geometry, and the previously
saved body-flow omission improves its qualified full-aircraft result from
220/252 to 244/252. All 252 comparisons were re-scored against native tokens.
This supports a legacy-code explanation but does not authenticate the SA-8 run.
The published body physics is retained; isolated-wing drag remains unresolved.
The new [SA-10 failure diagnostics](../../docs/validation/isae-sa10-source-diagnostics-20261101.md)
identify the dominant bound/wake sources and circulation residual in local-Mach
rejections using existing cached coefficients. Eight targeted tests and five
saved-field replays pass, including independent high-precision source checks.
The invalid junction flows remain rejected; no registered passes are added.
Browser verification and refreshed distribution bundles remain pending.
The [SA-10 zero-state audit](../../docs/validation/isae-sa10-zero-resolution-20261101.md)
finds that zero circulation meets the current residual gate and all 42 printed
outputs at the six zero-incidence states. More tightly converged solutions
retain tiny loads from the asymmetric stall law. Stopping precision is a
possible explanation for ten failures, not an authenticated native setting;
computed results and pass counts remain unchanged. Six targeted tests pass.
The [SA-6 stall-width pilot](../../docs/validation/isae-sa6-stall-width-20261101.md)
tests half/double the documented transition width on eight existing pilot
states. State matches fall from 253/288 to 180/288 or 140/288, with static
losses as well. All 16 cold solves finish and independent equation checks pass;
neither alternative qualifies for extension or changes a registered result.
The [SA-8 drag bound](../../docs/validation/isae-sa8-drag-energy-bound-20261031.md)
shows that arbitrary circulation matching native CDi and efficiency within 3%
cannot recover the fore-wing −4° total drag on the tested 40/64/128 grids:
CD ≤ 0.0105641 versus native 0.0120774, at least 12.53% low. This excludes
circulation/stall-strength changes alone under the stated geometry and force
conventions. Six independent bounds pass verification, without new nonlinear solves.
The [SA-6 inertia-compatible mesh follow-up](../../docs/validation/isae-sa6-inertia-mesh-rates-20261031.md)
tests all 14 candidates that retain required control-break nodes at one native
operating point. All pass static outputs; none passes CXq, CLq, Cmq or Cnq.
CLq remains 4.43–5.67% high (median 4.95%); Cmq error median 5.34%, maximum
6.34%. These repeated diagnostic comparisons add no registered passes.
The [velocity-reference audit](../../docs/validation/isae-sa6-velocity-reference-20261031.md)
finds that the rate-derivative term corrected in ASWING 5.85 is already present.
Two independent coordinate-change tests pass; the four paired SA-6 decks have
zero velocity references. This adds no registered passes or change to error percentages.
The [SA-6 reference audit](../../artifacts/isae/rigid-origin-derivatives-20261031/sa6-reference-audit.json)
confirms zero moment references in all 44 native exports; the SA-10 translation cannot fix those derivative errors.
The latest [SA-6 source-inertia audit](../../docs/validation/isae-sa6-source-inertia-20261031.md)
verifies the endpoint integration and retains 2,288/2,904 tensor matches at
3%. All non-tiny tensor cells pass; tiny native residuals remain failures.
Absolute tensor evidence narrows the mesh candidates to 22 without recovering
the native mesh. The earlier mesh pilot's five derivative gains and two losses
remain a diagnostic; registered counts and production defaults are unchanged.
SA-10's corrected origin-moment output gives **1,256/2,268**, gaining 173
checks with no losses in the saved default scope; twelve cold solves verify it.
Separate strength-20 setup diagnostics remain qualified, as listed below.

Recent SA-10 investigations add **no registered passes**:
[tip-sail Fourier modes](../../docs/validation/isae-sa10-tip-fourier-20261031.md)
reduce the sampled default-strength result from 20/42 to 10/42 or 12/42;
[frozen influences](../../docs/validation/isae-sa10-frozen-influence-20261031.md)
reduce the five-model sample from 47/105 to 14/105. All 71 new requests finish,
including recorded local-Mach rejections. Independent field/equation checks
verify the outcomes; neither option supplies a general correction.
Detailed investigation history is in [docs/STATUS.md](../../docs/STATUS.md).

Latest [SA-7 force-receiver audit](../../docs/validation/isae-sa7-force-receivers-20261031.md):
eight retained cold cases give 20/20 sampled full-aircraft and 9/20 historical
fore-wing force matches with the documented calculation. Every control-point
or beam-axis alternative loses matches and gains none. Historical fore-wing
CD error in this sample is typically 159.18%, maximum 427.91%; the archived
negative drag remains unresolved. The separate strength-20 full-aircraft result
remains 404/406; its [Mach follow-up](../../docs/validation/isae-sa7-pg-mach-20261031.md)
does not resolve the remaining −5° efficiency error.

**Typical error** means the median absolute percentage error among failed, finite,
numerically valid checks on the finest declared mesh for each state. A failed fine
solve is never replaced by a successful coarse result. Tiny references are reported
in absolute units; failed or blocked solves have no percentage error.



**SA-1–SA-5 spacing-only diagnostic:** all 184 counterparts have finished.
Only node placement changes; interval counts, physical settings and numerical gates
remain fixed. Counts below are separate from the default-mesh baseline above.

| Case | Default cosine | Modified cosine |
|---|---:|---:|
| SA-1 | 146/154 | 146/154 |
| SA-2 | 50/70 | 70/70 |
| SA-3 | 308/308 | 308/308 |
| SA-4 | 528/588 | 518/588 |
| SA-5 | 158/168 | 166/168 |

SA-5 is refreshed by 48 additional calls after the exact-zero reporting correction;
the other four rows retain the completed spacing comparison. Current verified totals
are **1,190/1,288 default** and **1,208/1,288 modified**.

[Results, error magnitudes and remaining failure themes](../../docs/validation/isae-sa1-sa5-spacing-20261029.md).
The candidate reproduces public straight/swept-wing station evidence; its extension
to curved axes is still a diagnostic. Production mesh defaults are unchanged.


Supplemental scopes from the same fresh run:

| Case / scope | Passing checks at 3% | Original strict passes |
|---|---:|---:|
| SA-6 / sa6-f1-rigid | 194/528 | 88/528 |
| SA-6 / sa6-mass-rigid | 2,288/2,904 | 1,760/2,904 |
| SA-6 / sa6-state-rigid | 1,039/3,168 | 528/3,168 |
| SA-7 / sa7-historical-fore-wing | 246/406 | 0/406 |

The SA-7 historical pairing reuses the same fore-wing target values with a recovered
historical model; it is a separate comparison, not additional independent reference data.
The SA-6 supplements cover control derivatives, state derivatives and mass/inertia
tensors under their recorded setup qualifications.

All 616 remaining SA-6 mass/inertia failures are zero/tiny-reference residuals;
its non-tiny tensor comparisons pass at 3%. These residuals retain their original
absolute tolerance and remain failures in the count.

**SA-2 inferred-mesh diagnostic:** a separate five-state fresh rerun passes
**35/35 at 3%**, versus 9/35 at printed precision. All 75 numerical checks pass;
maximum output error is 1.281%, and median CD error is 0.001109%.
[Evidence](../../artifacts/isae/sa2-inferred-native-three-percent-20261029/acceptance-report.json).
This mesh was inferred from public node coordinates; the production mesh default
and the standard SA-2 denominator are unchanged.

The non-SA qualifications and earlier investigations remain in the
[previous ledger](../../artifacts/isae/sa-three-percent-20261029/ISAE_STATUS.before-three-percent.md). In particular,
P-1 covers recorded thrust values using archived power inputs; ST-3 covers one
static snapshot, with a separate 269/270 coordinate-rounding comparison.
AE-1 errors refer to absolute Earth-Z positions, not sag-subtracted deflection.
These scopes do not establish whole-family validation.

Use `--relative-tolerance 0` with the suite runner to restore strict acceptance.
Original strict job files are retained; policy changes affect reference acceptance only.


## Status narrative retained on 2026-11-03

# ISAE comparison status

<!-- ST5-ROLLER-20261103 -->
The [four original ST-5 roller cases](isae-st5-roller-20261103.md)
now complete all **12 solves and 12 fresh residual checks**, with **14,708/25,920
qualified matches**; the 960 unresolved reaction-display entries remain required.
Initial printed-node grids have median twist errors **0.00012–0.00062%**; finer
grids move away from the archived values, supporting a historical discretization
contribution without proving exact original nodes. Finest median deflection/twist
errors are **0.247–0.315% / 0.376–0.603%**; only **21/56 mesh checks** pass.
The literal type-2 joints match rotation and carry zero force while translating
freely. One offline browser case passes **1,205 checks**, full native parity and
exact save/reopen. The original rigid baseline remains unchanged. No physical
equation or archived accuracy gate changed; ST-5 is still incomplete.
<!-- /ST5-ROLLER-20261103 -->

<!-- ST6-COLUMN-SUPPLEMENT-20261103 -->
The [analytical column supplement](isae-st6-column-supplement-20261103.md)
passes **19/19 synthetic cases** and **2/2 converged browser cases**. Final pole
errors are **0.0122–0.0312%**; the critical-load bracket center is **0.01004%**
above Euler. Coarse mesh failures and the corrected JSON-output memory failure
remain recorded. Full mode shapes, independent matrix residuals and saved-project
restoration pass. This verifies a clamped/free column, **not** the original ST-6
fixed-fixed experiments or native ASWING output. ST-6 still has no native target;
all original family counts and all production solver equations are unchanged.
<!-- /ST6-COLUMN-SUPPLEMENT-20261103 -->

<!-- ST5-MESH-EXTENSION-20261103 -->
The [ST-5 refinement study](isae-st5-mesh-extension-20261103.md)
now passes **56/56 mesh checks** across all four supported load cases on
304/256 versus 608/512 beam intervals. Maximum changes are **0.0326–0.0387%**
against the unchanged **0.1%** limit. Eight cold solves and fresh residual checks
pass. One actual browser solve takes **22.04 s**, passes full native parity over
264,567 numeric fields, and restores saved results byte-for-byte; the saved-only
recovery session passes 1,201/1,201 audit checks. The initial request-metadata
check failure is retained; no solve was repeated or accuracy gate relaxed.
The application now admits 1,024 intervals per beam; only input limits and UI
controls changed, with 42 focused tests passing and retained meshes unchanged.
Archived-ASWING differences persist: finest per-case median Z/twist/bending-moment
errors are **0.295–0.411% / 0.794–0.980% / 0.644–1.024%**.
The original **13,833/25,920** strict scalar score and failed coarse mesh pairs
remain recorded separately from this refinement supplement. Historical setup,
reaction-display identity, other configurations and whole-family validation
remain open. Other dated studies retain their recorded kernels; this change
alters no physical equations or default resolution.
<!-- /ST5-MESH-EXTENSION-20261103 -->

<!-- ST1-ST6-CURRENT-20261103 -->
The [fresh structural rerun](isae-st1-st6-current-20261103.md)
records all **101 current registered ST-1–ST-5 jobs**, preserving strict
tolerances, timeouts and unavailable comparisons. ST-6's 19 original files were
rechecked: no native ASWING target is identified. These are bounded comparison
results, not whole-family validation. The detailed table supersedes historical
ST counts for this current-kernel attempt.
<!-- /ST1-ST6-CURRENT-20261103 -->

<!-- ST4-TRANSFER-DIAGNOSIS-20261103 -->
The [independent ST-4 diagnosis](isae-st4-transfer-diagnostic-20261103.md) reproduces **93/93** selected
frequencies across the five runnable variants and three meshes, with maximum
relative difference **3.2412e-12**. Weight7d's worst mode approaches the
continuous beam with second-order error; its limit remains **0.8670%** below
the archive. This supports the implemented equations for the declared setup,
while leaving historical setup/mesh differences unresolved. Original ST-4
counts and mesh failures are unchanged; no new full modal solves were run.
<!-- /ST4-TRANSFER-DIAGNOSIS-20261103 -->


<!-- UA2-CURRENT-ASSESSMENT-20261103 -->
The [current UA-2 assessment](isae-ua2-current-assessment-20261103.md)
is sufficient to begin **ST-1 through ST-6**. Python and the actual browser each
pass **6/8 selected intervals**, including all four fresh intervals and all eight
aerodynamic waveform checks. All eight browser/Python comparisons pass
(maximum scaled difference **1.2475e-8**, limit 2e-8). Two legacy-checkpoint
acceleration failures remain at 2.87–2.89e-8 m/s², versus 2e-8; no gate was relaxed.
The 27 focused tests pass and all 136 public/dist modules match current source.
Native UA-2 agreement remains unverified.
<!-- /UA2-CURRENT-ASSESSMENT-20261103 -->

<!-- UA2-HARMONIC-MATRIX-20261103 -->
The [retained UA-2 harmonic matrix audit](isae-ua2-harmonic-matrix-20261103.md) passes **30/30**
independent frequency checks on 20/40 strips, plus four separate asymptotic
diagnostics. Maximum scaled complex lift difference is
**5.455e-11**, below **1e-8**.
Native ASWING agreement remains unverified (222 slots). The subsequent UA-2
assessment and completed ST-1–ST-6 comparison runs are linked above.
<!-- /UA2-HARMONIC-MATRIX-20261103 -->

<!-- UA1-CHART-BROWSER-COMPLETE-20261103 -->
The [retained UA-1 stalled browser comparison](isae-ua1-checkpoint-periodic-browser-20261103.md) passes
**13/13 gates**: **2,560 accepted steps, zero rejections, 2,561 unique states and
319 restart boundaries**. Fine lift/circulation/rate/pressure errors are
**0.01688% / 0.01152% / 0.03332% / 0.06629%**. Maximum scaled Python/browser difference is
**2.727e-09**, below **2e-8**. The Python two-grid
study passes 12/12 gates and the published harmonic benchmark retains 148/148.
This adds one equation-based browser supplement; native ASWING agreement,
broader UA-2 verification and full project completion remain open.
<!-- /UA1-CHART-BROWSER-COMPLETE-20261103 -->





Updated 2026-11-03. The full project and historical ASWING reproduction remain unfinished.

**SA tolerance: 3%.** Use `max(original absolute tolerance, 0.03 × abs(reference))`;
references with magnitude at most `1e-8` retain the original strict comparison.
Convergence and physical-validity gates are unchanged. Non-SA rows retain their earlier tolerances.

Verified default SA scopes: **6,094/15,226**; including the separately recorded
supplements: **9,861/22,232**. A check is one archived scalar comparison; counts
include both declared meshes, failed solves and blocked comparisons. They do
not establish whole-family validation. SA-9 is absent upstream.

The [UA-1 built-worker check](isae-ua1-incidence-periodic-browser-20261102.md) now passes **1/1 browser periodic checks and all 14 gates** at 9°, k=.94, A/c=.5 and 320 steps/cycle. All **2,561 snapshots** are audited; 2,560 steps converge without rejection. Periodic lift/circulation/rate errors are **0.01719%** / **0.03391%** / **0.01499%**; maximum scaled difference from the retained Python result is **3.616e-09**. The historical forcing-endpoint source difference is explicitly pinned. This adds runtime coverage for the existing case; broader physical conditions and native reference provenance remain unfinished; the current stalled supplement is linked above.

The [additional UA-1 periodic study](isae-ua1-periodic-a5-k047-20261102.md) **passes overall**, with **14/14 gates passing** at 5°, k=0.47, peak-to-peak A/c=0.5, with 160/320 steps per cycle. All **3,842 states** across two eight-cycle histories are audited. Fine periodic lift/circulation/rate errors are **0.02058%** / **0.02837%** / **0.01196%**. The initial checkpoint-verifier failure was isolated to one-ULP dimensional internal-moment rounding; the corrected audit limits only scale-converted internal fields to four ULPs and keeps other state fields exact. All 16 setup/audit tests pass. Production equations and physical accuracy limits are unchanged. This adds a physical condition in CPython; browser coverage for that condition, broader conditions and native-ASWING agreement remain unfinished; the current stalled supplement is linked above.

The [UA-1 stall/lag supplement](isae-ua1-stall-20261102.md) adds **72/72 passing instantaneous states** on two meshes. The first-cycle time study **passes**: **11/11 gates pass**, with fine lift/circulation/rate/pressure-drag errors **0.00868% / 0.00724% / 0.03068% / 0.02780%**. All 1,123 states on 160/320/640 steps are audited. The declared ±1.5 section limits exercise stall; they are supplemental settings, not recovered native UA-1 inputs. Production equations are unchanged. The repeated-stall comparison is reported below; Current UA-1 browser stall coverage is linked above; UA-2 stall and native agreement remain unfinished.

The [source time-matrix improvement](isae-ua-source-mechanics-20261102.md) uses exact endpoint-average derivatives for internal loads and reactions. All **13 Python tests** and **4 browser-reader tests** pass. A retained 40-step stalled segment uses 450 rather than 612 matrix-building residual evaluations; median solve time falls **10.6%** across three paired runs. The built worker passes a 16-step continuation comparison after correcting a retained signed-zero verifier failure; maximum scaled Python difference is **1.57e-9**. Physical equations and tolerances are unchanged. Scientific case counts are unchanged; the four-cycle stalled periodic comparison is reported below.

<!-- UA1-STALLED-PERIODIC-20261102 -->
The [UA-1 repeated-cycle stall study](isae-ua1-stall-periodic-20261102.md) **passes all declared gates**. Completed grids audit **3,842 states**, **158 BDF continuation boundaries**, with zero rejected steps. The finest completed fourth-cycle lift/circulation/rate/pressure-drag errors are **0.01688% / 0.01152% / 0.03332% / 0.06629%**. Its fourth/third-cycle change is at most **0.000019%**. Physical equations and tolerances are unchanged. This adds one supplemental equation-based case; Native stall agreement remains open; current browser verification is linked above. A retained fine-grid job timed out while saving its history; recovery uses 20-step jobs with the same physical grid.
<!-- /UA1-STALLED-PERIODIC-20261102 -->

The UA-2 transition assessment and supported ST-1–ST-6 runs are complete. Remaining structural work concerns mesh convergence, output definitions and unsupported original configurations. Continue with small serial jobs; see the [recorded sequence](isae-suite-backlog.md).
UA-1 passes **148/148 equation checks** across two small meshes, using the
verified peak-to-peak amplitude convention. Two supplemental
[time-refinement checks](isae-ua-time-20261101.md) also pass:
six small-amplitude runs, finest waveform errors **0.0602% and 0.0438%**.
Four additional [finite-amplitude checks](isae-ua-finite-heave-20261101.md)
pass at k=0.95 for A/c=0.05, 0.1, 0.3 and 0.5; finest errors are **0.0439–0.0502%**
against the nonlinear attached-flow equations. Four [periodic checks](isae-ua1-periodic-20261101.md)
also pass at k=0.95 for all four amplitudes: eight cycles, finest waveform errors
**0.0537–0.0603%**, amplitude errors **0.0281–0.0286%**, phase errors **0.0246–0.0269°**.
The exact [phase-average comparison](isae-ua1-phase-20261101.md)
now passes **12/12 curve checks** (six curves on two meshes, 1,200 lift samples)
at k=0.47/0.94 and mean labels 0°/5°/9°: maximum waveform error **0.00284%**
of oscillatory amplitude and phase error **0.000503°**. The mean-incidence
response comes from production derivatives. These are linear superpositions;
nonlinear periodic coverage at nonzero incidence and other frequencies remains incomplete.
The [nonzero-incidence follow-up](isae-ua1-incidence-20261101.md)
adds **96/96 instantaneous-state checks** and **1/1 first-cycle refinement check**
at 9°, k=0.94, A/c=0.5. Fine lift/circulation/rate errors are
**0.0548% / 0.0767% / 0.0619%**, with roughly fourfold improvement after
halving the timestep. All **242 time snapshots** are audited. Independent
nonlinear reference methods agree within **3.27e-11** of the relevant peak;
13 focused tests pass. Its 9.82% difference from the linear source waveform is
an approximation-level difference, not a native-reference failure.
The [inclined periodic time refinement](isae-ua1-incidence-periodic-refined-20261101.md)
now passes **1/1 checks** at 320 steps per cycle: periodic lift/circulation/rate
errors are **0.0172% / 0.0339% / 0.0150%**. The original 160-step circulation
error **0.1273%** remains recorded as a failure of the unchanged **0.1%** gate.
Halving the timestep resolves that failure with unchanged production equations;
all mean-lift, phase, settling and refinement gates also pass. The comparison
audits 3,842 snapshots, reusing the 160-step history and adding 2,561 new samples.
All 32 new serial segments converge without rejected steps. The browser follow-up
above now verifies this same refined case. Broader conditions and stall remain unfinished.
The [inclined UA-2 checks](isae-ua2-incidence-20261101.md) pass
**64/64 instantaneous states** on 20/40 strips at 5°/9°, k=0.475/0.95;
the largest vector-force coefficient discrepancy is **1.56e-15**. Eight
independent reference pairs and seven focused tests pass. The
[40-strip follow-up](isae-ua2-incidence-n40-20261101.md)
now brings inclined coverage to **2/2 first-cycle time checks and 1/1 mesh check**
at 9°, k=0.95, on 20/40 strips. Fine lift/circulation/rate errors are
**0.0127% / 0.0234% / 0.0161%** on both meshes. The maximum lift change between
meshes is **0.0425%**, below the declared 0.1% limit. The independent reference
predicts the same mesh change. All accuracy, motion and convergence gates pass;
halving every time interval reduces the waveform errors almost fourfold.
The two comparisons audit **1,204 snapshots**, including 602 new 40-strip samples.
At 40 strips, first-step rate error is **0.1295%** (limit 1%), and position
error is **0.0429% of heave amplitude** (limit 0.1%). All 38 new serial segments
converge without rejected steps. These are one physical condition on two meshes.
The original uniform-grid failure (rate error 1.53%, first-step error 10.6%)
and the first gradual-grid refinement-ratio failure remain recorded in the
[20-strip startup report](isae-ua2-incidence-nested-20261101.md).
Production equations remain unchanged. Broader conditions remain unfinished;
the periodic mesh follow-up is reported below.
The [inclined periodic comparison](isae-ua2-incidence-periodic-20261101.md)
now passes **1/1 cases and all 17 accuracy gates** at 20 strips, 9°, k=0.95,
A/c=0.5. At 640 steps/cycle, periodic lift/circulation/rate errors are
**0.00379% / 0.00845% / 0.00348%**, with almost fourfold reduction from the
320-step grid. Position error is **0.0349% of heave amplitude**; the coarse
0.1385% result remains above the unchanged 0.1% fine-result limit.
Amplitude error is 0.00182%, phase error 0.00140°, and the largest final-cycle
change is 0.000605%. All **7,922 unique snapshots** are audited in 28 small batches.
The original [checkpoint rounding bug](isae-ua2-time-endpoint-fix-20261101.md)
is repaired. A later 45-second timeout is preserved; recovery used 32-step
jobs on exactly the same physical grid. All 107 completed jobs converge with
zero rejected steps. Physical equations and acceptance limits are unchanged.
The [built browser replay and distribution checks](isae-ua2-time-endpoint-wasm-20261101.md)
also pass, covering one actual continuation step, desktop/mobile startup and
identical solver/runtime bytes in the app and download archives. The completed full-period
browser follow-up is reported below; broader conditions remain open.
The [40-strip periodic extension](isae-ua2-incidence-periodic-n40-20261101.md) now passes **18/18 gates**, adding **1/1 inclined periodic case and 1/1 periodic mesh check**. Inclined periodic coverage is **2/2 meshes at one condition**. At 40 strips, periodic lift/circulation/rate errors are **0.00379% / 0.00845% / 0.00348%**. The 20-to-40-strip lift change is **0.0432%** over the cold history and **0.0495%** over the eighth cycle, both below 0.1% and closely matching the independent reference changes. All **5,281 new snapshots** are audited; all 330 jobs converge without rejected steps. The fine temporal grid, equations and limits are unchanged. This adds spatial evidence, not a new 40-strip temporal-order result.
The [eight-cycle built-worker comparison](isae-ua2-incidence-periodic-browser-20261101.md) now passes **1/1 runtime checks and all 17 accuracy gates** at 20 strips, 9°, k=.95, A/c=.5. Periodic lift/circulation/rate errors are **0.00379% / 0.00845% / 0.00348%**; maximum scaled Python difference is **5.162e-9**, below 2e-8. All **5,281 snapshots** are audited in 42 serial batches, with zero rejected integration steps. The original producer exit 1 at its final cutoff-checkpoint assertion is preserved. A corrected assessment verifies the retained final output and its accepted BDF2 history without rerunning the trajectory; 10 focused verifier tests pass. Solver equations and physical limits are unchanged. The subsequent workbench check below covers full-history UI use; broader conditions and native provenance remain unfinished.
UA-2 also passes [four lift time-refinement and two mesh checks](isae-ua2-time-20261101.md)
on the reconstructed AR10 wing: finest lift errors **0.0410–0.0556%**, mesh
changes below **0.05%**. Four additional [local startup checks](isae-ua2-startup-20261101.md)
pass with a refined variable-step grid: first-step rate errors fall from
**10.6–16.1% to 0.066–0.517%**, and rate waveform errors are **0.050–0.064%**
of each strip's reference peak. Production equations and app defaults are unchanged.
The expanded [independent nonlinear grid](isae-ua2-amplitude-grid-20261101.md)
passes **16/16 time-refinement and 8/8 mesh checks**, covering all four amplitudes
at k=0.475/0.95 on 20/40 strips. Fine lift errors are **0.0503–0.0724%**, per-strip
rate errors **0.0503–0.0654%**, and mesh changes **0.0447–0.0496%**. Its vortex
integrals and loads are derived independently of production. All **5,152 snapshots**
are audited; the counts include the earlier A/c=0.5, k=0.95 pilot.
The [eight-cycle periodic pilot](isae-ua2-periodic-20261101.md)
passes **2/2 periodic and 1/1 additional mesh checks** at A/c=0.5, k=0.95.
All **4,004 snapshots** are audited: fine lift error **0.0680%**, local-rate
error **0.0592%**, amplitude error **0.0279%**, phase error **0.0235°**, and mesh
change **0.0467%**. Additional fine-grid diagnostics are circulation error
**0.148%**, third-harmonic amplitude error **0.245%**, and position error
**0.546% of heave amplitude**; those quantities have no separate acceptance
gate in this pilot. Six focused tests pass. Other periodic amplitudes,
frequencies and incidences remain unfinished.
The [discrete-equation audit](isae-ua2-discrete-audit-20261101.md)
reproduces all four saved trajectories with normalized state/load differences
below **7.66e-10**. Motion integration dominates the lift error: fine-grid
motion and circulation-integration components are **0.0608% and 0.00816%**
of peak lift (their signed waveforms add; their maxima do not). The independent
motion equations also reproduce the accumulated position drift. Six new
focused tests pass. This diagnostic adds no native or periodic pass counts.
Its **222 native-comparison slots stay blocked**: the saved curves reproduce
a corrected 2D formula, so native 3D provenance is unresolved. Neither family is complete.
Earlier [SA-6–SA-10 work](isae-sa6-sa10-focus-20261031.md) is retained.
The [qualified SA-6 roll/yaw comparison](isae-sa6-span-native-20261101.md)
now passes **616/616** checks across all 14 published native series, maximum
error **1.927%**. This uses explicit gain/strength/incidence hypotheses and a
separate 10-inch span reconstruction. Native setup remains unverified;
post-stall derivative failures and the registered baseline counts below remain.
SA-6-specific browser/WASM verification remains pending; the general app bundles have been refreshed.
The runner now defaults to one worker and supports [small resumable batches](isae-small-serial-runs.md).

The [SA-6 sampling-location bound](isae-sa6-rate-location-bound-20261101.md)
rules out any common fixed pair of kinematic sampling points as a complete
pitch-rate remedy under the retained equations: at least one pilot error must
reach 4.234%. No production change or registered gain follows.
Following the [native control order with sequential initialization](isae-sa6-native-control-sequence-20261101.md)
also leaves all matches unchanged; it reaches the same converged solutions.

The [SA-10 drag-reporting diagnostic](isae-sa10-drag-reporting-20261101.md)
recovers all 36 remaining drag/CD checks in the retained three-model sample:
**1,088/1,134 → 1,124/1,134**, with ten strict-zero failures left. It combines
Trefftz induced drag with integrated profile drag. Native justification remains
unverified, so the production calculation and registered counts stay unchanged.
The [pair decomposition](isae-sa10-drag-pairs-20261101.md)
localizes the coarse Louvered gap to central-wing/bent-tip interactions and
shows strong sensitivity to their relative quarter-chord offsets.
An [exact geometry audit](isae-sa10-geometry-parameter-20261101.md)
rules out a parameter/arc-length mix-up for those six saved states.
SA-7's [remaining efficiency checks](isae-sa7-wake-convergence-20261031.md)
are not resolved by substituting total lift for wake lift: the error increases
from 3.54% to 3.62%, so that output change is not adopted.

**Typical error** is the median absolute percentage error among failed, finite,
numerically valid checks on the finest declared mesh for each state. A failed
fine solve is not replaced by a coarse result. Tiny references use absolute
units; failed or blocked solves have no percentage error.

The [full-history storage audit](isae-ua2-history-storage-20261102.md) measures **4.22 GB** of ordinary snapshot JSON: the existing 64 MiB JSON-project limit is exceeded at **84 states** in this fixture, and the structural-size guard at **160**. Exact metadata sharing now passes all 330 segment comparisons and 660 endpoint-checkpoint comparisons; actual-app continuation/export passes for 33 states. That earlier metadata-sharing increment did not provide complete-history persistence; the archive workbench follow-up is recorded below. Scientific/native pass counts are unchanged.

The [complete-history workbench check](isae-ua2-archive-ui-20261102.md) now opens and plots all 5,281 lift samples in 0.95 s from the indexed archive. Full-state selection/playback, 33-state archive save/open/continuation, distribution CSVs, small JSON projects and runtime Undo load pass. All 66 focused tests pass. A first unindexed-quantity scan still takes 96.1 s with progress. Large project attachments and automatic durable segment storage remain unfinished. All 136 scientific modules and native comparison counts are unchanged.

The [time-plot follow-up](isae-ua2-time-ui-20261101.md) retains all 5,281 plotted samples and reduces median plot-only scrub time from 58.5 to 1.4 ms on this host. A complete 17-state segment also passes actual-app desktop/mobile replay and value-preserving JSON export. Full physical-history memory, loading and archive saving remain unverified; scientific/native pass counts are unchanged.


The SA-6 mass/inertia scope, SA-7 historical fore-wing pairing, SA-1–SA-5
spacing diagnostics and ST-3 rounding qualification are in the
[supplemental notes](isae-status-notes.md). Those notes also
preserve the investigation history and evidence links.

Use `--relative-tolerance 0` with the suite runner to restore strict acceptance.
