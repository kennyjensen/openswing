# SA-6 through SA-10 investigation

Updated 2026-11-01. The user has now redirected current work to
[UA-1 and UA-2](isae-ua-harmonics-20261101.md). This document retains the steady
investigation and its open comparisons. Its target is
agreement with the archived ASWING calculations at the existing provisional
3% tolerance, with the numerical validity gates unchanged. Experimental
agreement is a separate question.

The [SA-7 efficiency-convention audit](isae-sa7-wake-convergence-20261031.md)
finds that replacing wake lift with total lift worsens both remaining errors
from 3.54% to 3.62%. Conditional native wake-lift inference separates a 0.595%
high lift magnitude from a 2.265% low CDi; their ratio explains the efficiency
failure without either individual coefficient exceeding 3%. Native input and
discretization differences remain; no new solve or accepted gain follows.

The [SA-10 exact geometry/parameter audit](isae-sa10-geometry-parameter-20261101.md)
reconstructs all six retained Louvered source geometries analytically, matching
within 7.22e−16 m. A piecewise change from the original arbitrary t parameter
to material arc leaves the physical mesh and source points invariant. This
closes the parameter/arc-length hypothesis for this sample; native corner
endpoint construction and force quadrature remain the unresolved questions.

The [SA-10 pair decomposition](isae-sa10-drag-pairs-20261101.md) localizes
the positive coarse Louvered drag gap to central-wing/bent-tip interactions.
Wind-parallel quarter-chord offsets strongly affect those interactions, while
a wind-normal-plane control gives near/Trefftz equality pair by pair. All six
saved states have independent scalar checks; no new solve or adopted correction
follows. The next geometry question is native endpoint construction at the
duplicated corner nodes, together with its force quadrature.

The [SA-10 near-field/Trefftz reporting comparison](isae-sa10-drag-reporting-20261101.md)
recovers all 36 remaining drag/CD checks across the retained three-model
scope, giving a diagnostic 1,124/1,134 with ten strict-zero failures left.
The native output convention is unverified, and neither production forces
nor registered counts change. A six-state bound/wake decomposition independently
reproduces the saved field and shows cancellation between both contributions.
The next question is why native and current near-field drag differ: reporting,
corner source/receiver geometry, or finite-mesh integration. No new solve runs.

The [SA-6 control-sequence test](isae-sa6-native-control-sequence-20261101.md)
uses the literal 35%-chord driver's F1=4,...,44 order and each previous
circulation as the next seed. It reaches the same roots as the cold controls,
with no fallback, gains or losses: 66/66 static and 343/396 state checks,
including 36/66 pitch-rate checks, on the retained fine mesh. Independent
scalar verification covers all 462 comparisons and the full eleven-state
seed chain. This initialization hypothesis does not resolve the discrepancy.

The [SA-6 common sampling-location bound](isae-sa6-rate-location-bound-20261101.md)
shows that even arbitrary common x/z offsets at both rate-sampling points
cannot pass all pilot q outputs with the retained equilibrium and equations.
An exact five-inequality certificate proves a minimum worst error of 1.41125
times tolerance; at least one nonzero output must differ by 4.234%. All 384
independent finite-derivative checks pass. The broader fixed-location-only
branch is closed without adopting inferred offsets or running aircraft solves;
native force/stall linearization and input parity remain unresolved.

The [SA-6 rate-sampling decomposition](isae-sa6-rate-receiver-split-20261101.md)
finds that moving only the rotational-velocity control-point sample improves
the pilot from 24/48 to 38/48 pitch-rate checks, including all eight CLq/Cmq
values per channel. It loses one Clq check, and seven CXq checks still fail
(median 28.29%, maximum 96.56%). Moving only the force-point sample loses
14 checks without gains. Neither diagnostic is extended or adopted. Independent
equation/source checks verify the decomposition without an aircraft solve;
the native frozen-influence rate convention remains unresolved.

The [complete SA-6 roll/yaw comparison](isae-sa6-span-native-20261101.md)
matches **616/616** checks across all 14 native series and both meshes, with
maximum error **1.927%**. This closes the table coverage gap under explicit
gain/strength/incidence hypotheses and a separate 10-inch span reconstruction.
Both literal-deck failures and the competing 8° span-incidence results remain
in the evidence. The scalar audit verifies all 1,056 decisions; no production
default or registered count changes. The unresolved SA-6 numerical target
remains the post-stall state derivatives, particularly pitch rate. See the
[compact all-case table](ISAE_STATUS.md) for registered counts and errors.

The [current SA-6 level-flight comparison](isae-sa6-level-input-comparison-20261101.md)
matches all 220/220 roll/yaw coefficients for five configurations under the
fixed printed-identity gain hypothesis and strength20. Median errors are about
0.34%, maximum 0.885%; the same-strength literal baseline gives 138/220. The
strength40 pilot has two losses despite a net gain and is not extended. All
208 cold calls and independent field/source checks complete serially. This is
evidence for the combined input hypothesis, not authenticated native settings,
changed production defaults or resolution of post-stall pitch-rate errors.
The other two level-flight span variants remain outside this current scope.

The [SA-6 additional native tables](isae-sa6-native-tables-20261101.md)
provide 220 author-labelled ASWING moment values outside the paired raw-export
scope. Ten exact printed response identities suggest that three level-flight
configurations used control gains different from their supplied decks. The
inference is conditional; no deck or equation changes. A dedicated reader
passes ten tests, and an independent audit verifies all 308 native selections
and 2,244 comparisons with the older cached study. Missing native setup, the
10-inch geometry mismatch and post-stall span-incidence ambiguity remain
explicit. This opens additional reference coverage without promoting historical
predictions into current validation or changing registered counts.

The [SA-6 matrix-precision audit](isae-sa6-matrix-conditioning-20261101.md)
finds that single-precision replays of all 88 saved systems retain exactly
2,780/3,168 state and 282/528 pitch-rate matches. Maximum coefficient change is
1.63e−6; the double-precision residual error bound is 2.53e−13. Independent
scalar checks verify all outputs and native decisions. This excludes saved
linear-solve accuracy as a remedy, while leaving the native rate/stall model
and producing settings unresolved. No new aircraft solves or registered gains;
the numerical replay finishes in 1.66 seconds with one BLAS thread.

The [SA-6 public-history audit](isae-sa6-source-history-20261101.md) excludes
later committed changes to the four paired models, 44 compared native matrix
files and retained driver: all 637 populated file checks match. It recovers
no earlier correction to the driver filename/model mismatch or native settings.
The receiver-location and apparent-mass hypotheses were already evaluated;
their retained results are reused, not repeated or counted as new evidence.
SA-6's unresolved native rate/stall response remains the numerical target.

The [rigid steady browser control](fourier-wake-ui-20261101.md) now connects
the continuous Fourier reference to single points and angle stacks in source.
It retains default outputs, gives explicit unavailable reasons, and preserves
the saved setting. Twelve JSON and thirteen JavaScript checks pass. Browser
runtime verification remains pending under the current host-stability limits;
this adds no registered comparison gains.

The [continuous Fourier wake diagnostic](fourier-wake-nonparallel-20261101.md)
now supports angled straight traces, shared tips and crossings. Nineteen wake
tests pass, including independent logarithmic-energy controls, and 58 SA-7
reference integrals remain unchanged to roundoff. On 20 computed SA-10
Fourier states, continuous integration changes CDi by only 0.019–0.391%, with
no pass/fail changes; 12 rejected states remain rejected. Failed CDi errors
are typically 5.72%, maximum 9.22%, after the change. This rules out the
tested wake-output quadrature replacement as a standalone correction for
that sample. No aircraft solves, default changes or registered gains follow.

The [SA-7 near-aligned-wake audit](isae-sa7-near-coplanar-wake-20261101.md)
separates a coarse mutual-quadrature defect from circulation at 18°. Exact
integration of the retained sheets gives a −0.020418 CDi defect, 69% of the
N20 discrepancy. A smooth Fourier wake removes most of that localized error
but leaves six CDi failures, 3.12–3.97% low, in a 197/203 diagnostic. Physical
controls prohibit replacing only the mutual term. The native representation
remains unresolved; no production change, registered gain or new solve follows.

The [SA-7 reported-count comparison](isae-sa7-reported-node-count-20261101.md)
tests total/per-wing readings of the report's 40 circulation nodes. Twenty
intervals per wing bring the −5° efficiency error to 0.42%, and give 199/203
over all 29 angles at strength 40. Four CDi/efficiency errors remain, up to
11.49%. The literal native angle sequence and previous-state seeds reproduce
the independent-start results without fallback. This supplies a plausible
finite-mesh explanation for the low-lift error, while the native node positions
and stall-region wake outputs remain unresolved. Registered counts are fixed;
all serial processes have finished and browser tests remain suspended.

The [SA-7 efficiency-definition audit](isae-sa7-efficiency-definition-20261101.md)
shows that the last two strength-20 failures combine smaller circulation-lift
and induced-drag errors. Carrying mutual cores into Trefftz output produces
406/406 counterfactual matches, but violates exact cancellation of opposite
wakes. The independent physical control prevents adopting that apparent gain.
The documented result remains 404/406; no registered count or production
equation changes, and no new aircraft solves are used.

The [SA-8 native-body source follow-up](isae-sa8-native-body-report-20261101.md)
connects an author-reported constant-section doublet issue in SA-14 with the
stored SA-8 body geometry. Exact re-scoring confirms the prior qualified
body-flow omission at 244/252 versus 220/252, with no new solves. This supports
a native-code explanation for part of the full-aircraft mismatch; it does not
authenticate its producing setup or explain the isolated-wing drag. Production
retains the published nonzero crossflow doublet, and registered counts stay fixed.

The [SA-10 failure diagnostics](isae-sa10-source-diagnostics-20261101.md)
now distinguish converged circulation from invalid local flow in the error
report. Existing cached coefficients identify dominant vortex sources and
physical ray distances, with coincident wake strengths combined first. Eight
targeted tests and five saved rejected-field replays pass; no new aircraft
solve or registered pass is introduced. The sharp-junction discrepancy remains
unresolved, and browser verification remains suspended.

The [SA-10 zero-state audit](isae-sa10-zero-resolution-20261101.md)
isolates the ten strict zero-incidence failures in the strength-20 three-model
scope. Zero circulation satisfies the existing residual gate and all 42 native
printed intervals; the tightly converged solutions retain small nonzero loads
from the asymmetric stall law. This makes stopping precision a possible
explanation, without recovering the native rule or promoting any passes.
Six prescribed evaluations and six targeted tests finish serially. Production
equations and full comparison counts remain unchanged.

The [SA-6 stall-width sensitivity](isae-sa6-stall-width-20261101.md)
tests fixed half/double widths around the published 0.05 value. On the
eight-state pilot, state matches fall from 253/288 to 180/288 or 140/288;
both variants also lose static and pitch-rate matches. All 16 cold bases and
independent equation checks finish in one serial process. Neither meets the
predeclared extension rule. No production setting or registered count changes.

The [SA-8 circulation-independent drag bound](isae-sa8-drag-energy-bound-20261031.md)
excludes a standalone circulation/stall-strength correction for the fore-wing
−4° drag on cosine 40/64/128 grids. Even arbitrary circulation matching native
CDi and efficiency within 3% gives CD ≤ 0.0105641, versus native 0.0120774.
Six bounds, positive-definite matrix inequalities and 216 manufactured vectors
are independently verified; no new nonlinear solve is used. Historical force,
profile-law, geometry and reporting conventions remain possible explanations.
Production and registered counts are unchanged.

The [SA-6 inertia-compatible mesh follow-up](isae-sa6-inertia-mesh-rates-20261031.md)
tests all 14 candidates retaining the required control-break nodes at the
15%-chord/F1=4° operating point. All six statics pass for every candidate,
but CXq/CLq/Cmq/Cnq fail on every grid. CLq stays 4.43–5.67% high; the tested
finite grid family cannot supply a standalone correction. Fourteen cold
bases and independent field/tangent reconstructions finish. No candidate
meets the extension criterion; production and registered counts are unchanged.

The [SA-6 velocity-reference audit](isae-sa6-velocity-reference-20261031.md)
checks the specific rate-derivative omission documented in ASWING 5.85.
Two coordinate-transformation regressions pass for pointwise and Fourier
circulation; the production reference term is already present. All four paired
SA-6 decks have zero velocity references, and the retained script does not
override them. Native moment headers do not authenticate native velocity
references. No production or registered count changes follow; browser tests
remain suspended.

The [SA-7 lift-force receiver audit](isae-sa7-force-receivers-20261031.md)
rules out three output-location substitutions for the historical negative-drag
anomaly. On eight cold cases, the documented force passes 20/20 sampled full
aircraft outputs and 9/20 historical fore-wing outputs. Control-point/beam-axis
velocities reduce those to 12/11/11 and 8/8/7, with zero gains. All 160 decisions
and 1,536 strip loads are independently verified; the full-sweep extension
criterion fails. No production or registered acceptance change follows.

The [SA-6 source-inertia follow-up](isae-sa6-source-inertia-20261031.md)
verifies the existing source endpoint operator and distinguishes it from the
legacy Glauert-sampled mass report. Both retain 2,288/2,904 tensor matches at
3% on the existing meshes; all non-tiny cells pass. Absolute printed inertias
narrow the prior 57 ratio-compatible grids to 22, still without authenticating
a native mesh. The previous modified-40 pilot narrowly misses one absolute
inertia, in addition to losing two pitch-rate checks. Twelve geometry
assemblies and 48 independent matrix reconstructions complete without an
aerodynamic solve. Production and registered counts stay unchanged; browser
jobs remain suspended. The [eight-case mesh pilot](isae-sa6-native-mesh-20261031.md)
and its 253→256/288 state result remain separately qualified.

The [JVL rotation-rate source audit](isae-sa6-jvl-rate-20261031.md) rules out
adding its on-wing trailing-leg forces as an explanation for SA-6 pitch rate.
They cancel exactly in all 88 saved states; adding them would spoil all 88
currently passing `CYp` checks. An independent scalar reconstruction verifies
the result without new solves. The native local stall/rate discrepancy remains.

In the [SA-7 PG-Mach comparison](isae-sa7-pg-mach-20261031.md),
using the actual flight Mach 0.20575527 leaves the three-condition sample
at 20/21 and worsens the −5° efficiency error from 3.54% to 4.13%. All six
cold solves and independent checks finish. No gain warrants extending this
setting test to the full polar. The SA-10 tip-sail force receivers are also
verified to lie on their own bound segments to roundoff; that suspected
placement error is absent. Production and registered counts stay unchanged.

The [SA-10 frozen-influence comparison](isae-sa10-frozen-influence-20261031.md)
All 35 cold calls finish. At default strength 40, the sampled comparison
falls from 47/105 to 14/105; at strength 20, it falls from 89/105 to 28/105.
All twelve nonzero-incidence tip-sail states fail local-flow validity.
Thirty independent high-precision fields and five zero-incidence controls
verify the results. The alternate F interpretation is not a remedy; production
and registered counts remain unchanged.

The [SA-10 tip-sail Fourier comparison](isae-sa10-tip-fourier-20261031.md)
All 36 new calls finish: 21 computed states and 15 local-Mach rejections.
At strength 40, 20/40 modes reduce the fine-mesh sample from 20/42 to
10/42 or 12/42, with no gains. All coarse 25° Fourier runs are subsonic,
but all refined counterparts are rejected. Independent modal/force checks
and 24 high-precision field reconstructions verify the result. No added
junction constraint, core change or accepted-count change follows.

The [SA-8 profile/projection audit](isae-sa8-profile-projection-20261031.md)
For the isolated wing at strength 20, no constant profile coefficient passes
even the −3° to +4° range. At −4°, the force magnitude is too small for any
pure lift/drag reporting rotation to fix both outputs. Six fresh cold solves
verify the profile-force sensitivity to roundoff. The section coefficients
are independently corroborated by the authors' paper. This narrows the drag
discrepancy but adds no registered passes or production changes.

The [SA-6 rate-output and Jacobian audit](isae-sa6-rate-output-audit-20261031.md)
All 88 saved states rule out two apparent-mass output conventions and five
incomplete stall linearizations as a complete explanation. Omitting induced
speed gains six raw matches but fails the full tangent at every state, so
none is accepted. Sixteen cold perturbation solves verify the independent
apparent-load calculation and complete pitch-rate response to 3.49e−8.
The qualified state scope remains 2,780/3,168; production equations and
registered counts are unchanged.

The [SA-10 CM output-reference correction](isae-sa10-moment-origin-20261031.md)
Native CM now uses an explicit body-origin output following steady equations
221/225; existing file-reference moments and constraints remain intact.
The complete saved default scope improves from 1,083/2,268 to **1,256/2,268**,
with 173 gains and no losses. Failed fine-mesh CM error is typically 3.96%,
maximum 9.92%. Twelve cold solves reproduce the saved loads to roundoff;
138 targeted tests pass. The separate strength-20 three-model result is now
**1,088/1,134**, with every CL, CDi and CM check passing. Stall strength remains
unverified; coarse drag, strict zero outputs, joints and local-flow validity
remain unresolved. This updates the earlier origin-moment hypothesis below.

The [SA-7 Fourier/refinement follow-up](isae-sa7-fourier-refinement-20261031.md)
Twenty and forty circulation modes retain the 3.54% −5-degree efficiency
error at 64/128/256 intervals. Both pass 39/42 sampled native checks, with no
gains or losses. All twelve cold solves finish; independent section loads,
weighted residuals and continuous-wake integration verify the retained
calculation. The remaining low-lift error is not resolved by these mode
counts or the tested wake reporting.

The [SA-8 source-history audit](isae-sa8-source-history-20261031.md) also
checks all 14 reachable commits returned for the retained main revision.
The six comparison files are unchanged in all 13 populated trees, including
earlier directory paths. No alternate deck or ASWING settings file is
recovered; historical XFOIL files are distinguished from ASWING inputs.
This supplies no correction to the isolated-wing drag discrepancy.

The [SA-6 stall-speed follow-up](isae-sa6-leakage-speed-20261031.md)
rejects two alternate local-speed definitions.
Using control-point or uniform-freestream speed in the leakage law reduces
the sampled state comparison from 253/288 to 190/288 or 154/288, with no
gains. Independent cold calculations reproduce the production control within
2.31e−13. All 72 final nonlinear calls finish; the one coarse derivative
stencil failure decreases fourfold at half the step, where all checks pass.
Both alternate definitions are rejected; defaults and registered counts stay
unchanged.

The [SA-6 rate decomposition and Fourier follow-up](isae-sa6-rate-fourier-20261031.md)
also rejects simple convention changes.
Exact certificates rule out a standalone rate scale or x/z velocity-reference
shift at all 88 saved states. Independent section loads reproduce the saved
pitch-rate outputs within 2.23e−15. Forty Fourier modes improve the sampled
state comparison from 253/288 to 257/288, but pitch rate stays 24/48; 20 modes
lose two static checks. All sixteen cold bases and analytic responses finish.
No production or registered acceptance change follows from these diagnostics.

The [SA-6/SA-10 corner and kinematics audit](isae-sa6-sa10-corner-kinematics-20261031.md)
also rejects two standalone corrections.
A complete zero-length corner horseshoe cancels to 5.86e−13 of speed;
72 independent and 144 production field vectors rule out its omission as
the louvered refinement fix. A shared-vertex bend still has a 1/d local bound
velocity. Two material-point rotational-velocity interpretations worsen
the sampled SA-6 derivatives from 253/288 to 245/288 and 247/288. Neither
is adopted; no new equilibrium or registered acceptance gain is claimed.

The [SA-10 Louvered Fourier/refinement audit](isae-sa10-louvered-basis-20261031.md)
finds that neither 20 nor 40 modes resolves the coarse drag difference. Pointwise
400-interval refinement reaches local normal Mach 2.52/3.17 at 15°/25°,
despite converged circulation; independent 60-digit integration reproduces
the bend velocities. Passing 200-interval drag checks are therefore not
evidence of mesh convergence. All 18 new calls/replays finish; defaults and
registered counts remain unchanged.

The [SA-10 stall and tip-junction follow-up](isae-sa10-stall-junction-20261031.md)
completes all 162 states of the three simpler models. Strength 20 now passes
1,088/1,134 with the corrected origin-moment output (932/1,134 with the old
file-reference mapping), with every CL, CDi and CM
check passing. Remaining differences in that scope are coarse louvered drag and
zero-incidence outputs. Independent integration reproduces three tip-sail
Mach rejections despite converged circulation; the original root field grows
stronger under refinement. Native strength remains unverified. The later
output correction changes reporting and comparison counts; physical loads
from this investigation remain unchanged.

The [SA-8 body-volume isolation](isae-sa8-body-volume-20261031.md)
raises the full-aircraft strength-20 diagnostic from 220/252 to 244/252 by
omitting body-induced velocity while retaining body forces and current wake
geometry. Independent exact integration verifies the original production
field, so physical volume effects remain implemented. The eight remaining
failures are at −4°: fine-mesh CL 5.50%, CDi 10.40%, CM 7.74%. An additional
40-interval run does not resolve them. All 54 new solves and four targeted
regression checks complete; registered counts stay unchanged.

The [complete SA-8 strength-20 diagnostic](isae-sa8-full-comparison-20261031.md)
passes **432/504**: full aircraft 220/252 and isolated wing 212/252. The
isolated wing passes every output except total drag, whose failed fine-mesh
CD errors have median 11.29% and maximum 15.66%. Full-aircraft failures are
confined to negative incidence. All 72 outcomes finish; 61 new solves and
11 pinned reuses. Sixteen additional frozen-influence and 40-interval
samples supply no general fix. The native coefficient is still unverified,
and the registered baseline remains unchanged.

The [SA-6 frozen influences with stall strength 20](isae-sa6-frozen-stall-20261031.md)
passes **528/528 static checks** across all four paired models and both meshes,
with maximum nonzero error 0.946%. Frozen influences alone give 388/528 versus
the registered 290/528. The native stall coefficient is unverified, so this
remains a separate hypothesis. The [complete derivative follow-up](isae-sa6-frozen-derivatives-20261031.md)
passes 528/528 F1 and 2,780/3,168 state checks; pitch-rate differences remain.

Follow-up: the [stall-strength and local-force investigation](isae-sa6-sa10-stall-strength-20261031.md)
reaches 404/406 on the complete SA-7 aircraft polar at strength 20, with only
two -5° efficiency checks remaining. The native strength is unverified, and
the same change worsens SA-6 with current influences, so this is a separate
diagnostic and the baseline below is unchanged.

The [low-lift wake follow-up](isae-sa7-wake-convergence-20261031.md) retains
SA-7's efficiency mismatch under cosine refinement and independent continuous
wake integration. Modified spacing's coarse pass disappears at 256 intervals.
Independent numerical integration also verifies 240 sampled induced-velocity
vectors. Neither mesh choice supplies a reliable correction to that last error.

| Case | Current registered scope | Main unresolved issue |
|---|---:|---|
| SA-6 | 290/528 static checks | Roll is typically 3.46% outside the reference among failed fine-mesh checks; yaw 23.7%. Control/state derivatives and mass tensors remain separate registered supplements. Three models have no paired native export. |
| SA-7 | 395/812 | Current fore-only geometry conflicts with the archived output; the separately recovered historical model is a qualified additional pairing. Total-aircraft results are much closer than the combined headline errors suggest. |
| SA-8 | 373/504 | Tandem interaction near stall, induced drag, and fore-only total drag remain outside tolerance at some conditions. |
| SA-9 | Absent upstream | No archived case exists; no synthetic pass or replacement case is assigned. |
| SA-10 | 1,256/2,268 | Origin-CM output correction included. Remaining failed fine-mesh CM is typically 3.96%; stall, interacting-tip results and the original joint-domain conflict remain. |

These complete registered counts include the SA-10 output-only reanalysis,
and exclude the separate strength-20 diagnostics. They include both declared meshes. The
[full status ledger](ISAE_STATUS.md) retains all case families and the
separate SA-6 and SA-7 supplements.

The [selected full plan](../../artifacts/isae/sa6-sa10-focus-20261031/plan.json)
contains 661 jobs across SA-6/7/8/10, including the qualified historical SA-7
fore-wing pairing. SA-9 is listed here as absent; the runner correctly rejects
it as an executable family. This plan has not been executed in full.

The [spacing pilot](../../artifacts/isae/sa6-sa10-focus-20261031/spacing-plan.json)
predeclares 60 outcomes: original cosine versus modified-cosine spacing at
the finest declared mesh, with two conditions for each source model. It keeps
section properties, solver equations, native targets and acceptance unchanged.
All 60 outcomes are now terminal: 56 valid cold solves and four original-input
blocks. Each returned state passes circulation convergence and independently
reconstructed force and moment checks. All 28 fresh cosine results reproduce
the earlier registered predictions within 2e-10 scaled error. This pilot does
not replace the registered comparisons.

## Completed diagnostics

| Case / pairing | Pointwise cosine | Pointwise modified cosine | Fourier K20 / K40, cosine |
|---|---:|---:|---:|
| SA-6 | 28/48 | 28/48 | 28/48 / 28/48 |
| SA-7, current files | 13/28 | 13/28 | 13/28 / 13/28 |
| SA-7, historical fore | 8/14 | 8/14 | 8/14 / 8/14 |
| SA-8 | 24/28 | 24/28 | 24/28 / 24/28 |
| SA-10 | 37/84 | 39/84 | 32/84 / 32/84 |

These are small, predeclared samples at the finest mesh, not full-family counts.
The [spacing results](../../artifacts/isae/sa6-sa10-focus-20261031/spacing-report.md)
recover only SA-10 Louvered drag and CD at 20°: error falls from 7.46% to 2.87%.
There are no sampled losses. This does not justify changing the default mesh.

The [Fourier comparison](../../artifacts/isae/sa6-sa10-focus-20261031/basis-report.md)
uses the published sine series and weighted residual, equations (63) and (201),
with 20 or 40 modes per lifting beam. It finishes with 54 valid solves, four
original-input blocks, and two local-Mach rejections. Independent scalar
quadrature reproduces the reported weighted residual within 9.43e-18; the
largest converged weighted residual is 2.10e-13. Local residuals are retained
separately and need not vanish for a truncated series.

Neither mode choice recovers a sampled check. Both lose four finite drag/CD
checks for TS_80_60_40. At 20°, TS_60_40_80 is rejected at local normal Mach
1.61 for K20 and 1.38 for K40, losing one additional previously passing check
per choice. The validity gate is retained. The first harness attempt had a
NumPy-boolean JSON serialization error; its failed outputs and termination
receipt are preserved separately. The corrected completed run changes only
that serialization, not the numerical setup.

## Differences now isolated

The [model-level baseline](../../artifacts/isae/sa6-sa10-focus-20261031/baseline-review.md)
shows that **SA-7's complete aircraft passes 395/406 checks**. The remaining
eleven are efficiency at -5° on both meshes (3.54% high), and induced drag at
19–24° (3.13–3.92% low; not every mesh/angle fails). At those high angles,
CL is also 0.95–2.24% low. The mismatched current fore-only geometry contributes
0/406 and should not obscure how close the complete aircraft is. The recovered
historical fore pairing remains separate at 246/406; its archived negative
drag values remain unexplained.

For **SA-8**, the complete aircraft passes 211/252 and the fore-only model
162/252. At zero incidence, fore-only CD is 0.01164096 versus 0.0127966
(9.03% low), whereas CDi is 0.001313724 versus 0.00131605 (0.177% low).
OpenSwing near-field and Trefftz induced drag agree to 2e-18 at that state.
Its remaining reported drag is CDp=0.01032724. The native difference
CD−CDi=0.01148055 is an inferred remainder, not an independently archived
profile-drag channel. This excludes the near-field/Trefftz difference as the
explanation at this state. The complete-aircraft CD error there is only 0.048%.

For **SA-10**, all current models specify Xmom=0.05 m. The implemented
[origin-moment reporting](isae-sa10-moment-origin-20261031.md) distinguishes
the total reference moment in equation (187) from the aerodynamic origin
moment in equations (221/225). The ASWING comparison uses the origin output,
gaining 173 registered checks with no losses: **1,256/2,268** now pass.
File-reference outputs and solver references remain available unchanged.
Twelve cold solves verify the reporting change; native discretization and
stall settings remain unconfirmed.

The [source-history audit](../../artifacts/isae/sa6-sa10-focus-20261031/source-history.md)
checks nine retained public Git trees, including the initial empty repository.
All 24 SA-8/SA-10 model, driver and table files have identical blobs across
the eight populated snapshots, including directory renames. No matching saved
`.set` file was found in those case paths. A later public file edit therefore
does not explain these discrepancies; unpublished/default settings remain
unknown.

## Next work

Reconcile the remaining SA-7 circulation/geometry and stall-setting differences,
and the SA-8 fore-wing non-induced drag. The full-aircraft body-flow
contribution is now isolated and independently verified against the equations.
The reported native constant-section doublet issue supplies a specific lead
for its omission; the producing setup and residual −4° interaction remain
unresolved. Preserve the documented body field.
Frozen influences alone lose high-incidence checks. The report's stated
airframe omission and its 40-node mesh do not authenticate the retained
producing setup.
Independent local-force reconstruction
and the SA-7 field/wake checks pass; they do not authenticate the native setup.
For SA-6, investigate the remaining incidence/roll/pitch-rate derivatives;
static and F1 checks all pass under the fixed, unconfirmed hypothesis.
For SA-10, origin-moment reporting is implemented and included in acceptance.
The ten tiny zero-incidence failures have a possible stopping-precision
explanation; further work should prioritize the nonzero-incidence Louvered
drag and tip-junction fields. Neither spacing nor the tested Fourier
resolutions supplies a general correction. The original joint-domain conflict
remains blocked. Comparison tolerances and literal section properties stay fixed.

The feedback extension was left unfinished when the user changed focus. Its
[handoff](../../artifacts/isae/source-airflow-feedback-20261031/HANDOFF.md)
records the retained edits and partial tests; no browser build or package was
made for that work.
