# SA-1–SA-5: modified cosine spacing and remaining failures

Updated 2026-10-31. Modified cosine spacing resolves the registered SA-2 drag
failures and most SA-5 failures at the provisional 3% tolerance. It barely
changes SA-1, preserves SA-3's passing results, and worsens SA-4's aggregate
score. This candidate is therefore not established as a universal mesh default.

The [complete wake-sampling follow-up](../../artifacts/isae/aerofuse-reference-qualification-20261031/report.md)
rejects geometric-midpoint sampling as an SA-4 correction: 42 CDi/efficiency
matches are lost and none gained (160/168 to 118/168). All losses are on the
N18 CD sweep, with typical errors 3.68% for CDi and 5.71% for efficiency.
At 7.06°, CDi worsens to 6.83–7.81% low. The study holds saved circulation
fixed and does not establish native quadrature. The existing Glauert choice,
production equations and registered/spacing-only scores remain unchanged.

The [local-equation and adjacent-seed follow-up](../../artifacts/isae/sa4-endpoint-local-branch-20261031/report.md)
does not resolve the remaining 7.06° CDi discrepancy: translated endpoints
remain 6.18–6.67% low with cold full-local closure. Convergence improves
from 34/42 to 39/42, including six recoveries and one new 6.55°/N156 failure.
All 336 planned outcomes and both independent audits are complete. The
registered and spacing-only rows below remain unchanged.

The [complete endpoint-construction follow-up](../../artifacts/isae/sa4-endpoint-solves-20261031/report.md)
now re-solves the two earlier fixed-circulation hypotheses. Both give 570/588
in the qualified SA-4 setup, including 294/294 drag-table checks. Translated
nodal endpoints preserve all SA-1/2/3/5 modified-spacing pass counts; the
interval-constant construction loses eight SA-3 drag checks (3.03–3.16% low).
All 552 cold calls and independent field/load audits finish. The remaining
SA-4 7.06° CDi errors are 6.34–6.79% low for the translated construction.
Native endpoint provenance remains unproved, so production and the registered
and spacing-only tables below remain unchanged.

The [complete pointwise follow-up](../../artifacts/isae/sa4-input-angle-pointwise-full-20261030/report.md)
limits the later SA-4 geometry hypothesis: all accepted local equations converge,
but fine-grid cold solves at 4.60°/5.13° fail. The full comparison is 556/588,
versus its K40 counterpart's 570/588. At 7.06°, CDi still differs by 6.44–6.88%
with local residuals near roundoff. The native discrepancy therefore persists
beyond the truncated-basis approximation. No production/default change.

The subsequent [complete SA-4 prescribed-geometry study](../../artifacts/isae/sa4-input-angle-full-polar-20261030/report.md)
reaches **570/588** across both tables, versus 562/588 for the retained original
geometry. All 84 cold calls pass the existing numerical gates, with eight gained
and no lost checks; the separate CD table passes 294/294. Its input-knot angle,
chord-measure and Eq.48 construction remains an isolated hypothesis. CL-table
local defects reach 3.99 and one normal Mach reaches 0.99797, so the scalar
improvement does not establish resolved native flow. The 7.06° CDi error is
still 6.50–6.89% low. Default and spacing-only counts below are unchanged.

The [named mesh option](modified-cosine-option-20261030.md) now exposes this
same distribution as **Modified cosine in arc length** in the node editor,
and `spacing: "modified-cosine"` in the API. All twelve saved meshes reproduce
exactly. Ordinary cosine remains the default; the historical comparisons below
retain their original scope and counts.

The earlier [SA-4 endpoint-construction diagnostic](../../artifacts/isae/sa4-endpoint-construction-20261030/README.md)
retains every adjacent-strip influence and changes only bound endpoints at
fixed circulation. Both alternatives affect the near field, but all 168
altered configurations fail the original projected-residual gate despite
remaining subsonic. This is evidence of geometry sensitivity, not a solved
replacement or additional native matches. The complete candidate stays
562/588; the baseline and spacing-only counts below remain unchanged.
The subsequent [source review](../../artifacts/isae/sa4-source-geometry-review-20261030/README.md)
confirms shared adjacent wake origins in all 84 original states. Separated
starts are a consequence of the diagnostic endpoint shifts. The available
AVL/JVL source does not authenticate those shifts as ASWING conventions;
twelve new exact-filament regressions pass without changing production.

**Subsequent reporting correction:** the [exact-zero efficiency convention](isae-sa5-zero-efficiency-20261029.md)
has now been implemented and all 48 SA-5 counterparts freshly rerun. SA-5
passes **158/168 default** and **166/168 modified**, gaining four reporting
checks in each arm with finite force outputs unchanged within roundoff.
The table below includes that reporting correction; the controlled-comparison
counts retain the original spacing-only experiment. Current five-case
totals are **1,190/1,288 default** and **1,208/1,288 modified**.

| Case | Default cosine | Modified cosine | Result and remaining error |
|---|---:|---:|---|
| SA-1 | 146/154 | 146/154 | Same eight CDi failures at 14.097–18.091°; about 3.13–4.67% low. |
| SA-2 | 50/70 | 70/70 | All checks pass. Maximum total-CD error falls from 10.79% to 1.179%. |
| SA-3 | 308/308 | 308/308 | All checks continue to pass. |
| SA-4 | 528/588 | 518/588 | Six solver failures remain, with one recovery and one regression. Five coarse-mesh CD/drag pairs newly fail at 3.01–3.56% high. |
| SA-5 | 158/168 | 166/168 | All modified-grid total-drag checks pass. At 18°, CDi remains 3.31–3.35% low; exact-zero efficiency is now reported correctly. |

These are scalar output checks, including both declared meshes and repeated
dimensional/normalized quantities. In the original spacing-only experiment,
the diagnostic total was 1,204/1,288, versus 1,186/1,288 for the baseline.
There were 35 gained checks and 17 lost checks;
the aggregate improvement must not hide the SA-4 regressions. The current
modified-grid remainder is 38 finite mismatches and 42 outputs from six failed
solves. The default-mesh ledger in [ISAE_STATUS.md](ISAE_STATUS.md)
incorporates the reporting correction and lists spacing diagnostics separately.

Of the **80 unpassed modified-grid checks, 70 belong to SA-4**, eight to SA-1
and two to SA-5. SA-4 therefore remains the largest immediate task: 42 output
slots come from its six failed solves and 28 are finite reference mismatches.
SA-1 and SA-5 form the separate high-angle circulation/induced-drag task.
SA-2 supplies a successful spacing comparison, and SA-3 supplies a passing
geometry control. These output counts include repeated dimensional and
normalized quantities; they are not 80 independent physical failures.

## Controlled comparison

All 184 counterparts were fresh cold solves, with the original interval counts,
physical inputs, reference targets and numerical gates. Only node placement
changed. There were 178 completed, numerically valid solutions and six SA-4
solver errors; no worker retries or timeouts. All 184 processes were reaped. The 1,602
checks attached to returned solutions passed. Failed solves contribute no
reference matches. Production aerodynamic code and mesh defaults were unchanged.

The candidate follows the [SA-2 coordinate reconstruction](sa2.md#mesh-reconstruction-the-principal-drag-discrepancy):
`u = sin((2j/N − 1) asin(q))`, `eta = 0.7u + 0.3u³`, where `q` is the largest
binary32 value below one. It maps `eta` into material arc length, then uses the
production arc inverse to recover beam parameters. Exact endpoints, the
centerline, mandatory stations and actual interval counts were preserved.
The existing Glauert receiver construction was retained.

The material-arc extension to curved axes remains a diagnostic assumption.
A subsequent [independent CASEI coordinate comparison](isae-scn-curved-spacing-20261029.md)
supports it over direct parameter mapping: maximum station error falls from
9.393 mm to 0.079 mm with natural splines or 0.062 mm with zero-third
endpoints. Neither reproduces every printed station within 0.05 mm. Native
ASWING source has not authenticated this as the universal generator. In SA-4,
material-arc and linear beam-parameter fractions differ by as much as 6.47%,
so that distinction matters. Matching straight/swept-wing stations alone does
not settle the curved-wing recipe; CASEI provides additional, qualified evidence.

## Common themes

**SA-4 circulation representation and spacing interact.** A subsequent
[fixed-K40 comparison](../../artifacts/isae/sa4-modal-spacing-20261030/report.md)
matches all six formerly failed angles at N80 with either spacing rule. At
N160, cosine matches five angles and modified spacing matches all six (42/42).
For the six modified N160 states, CL/CDi/Cm errors are below
0.341%/0.356%/0.055%; total CD is 0.722–2.990% high. This uses the documented
weighted-residual formulation and a fixed, report-supported mode-count
hypothesis. It changes the discrete approximation, not merely the solver seed.
The original spacing-only table above still uses pointwise circulation.

This is not a general remedy: 3.59° fails the local Mach gate at N160 with
both spacing rules, all four N320 calls fail that gate, and the 7.06°
modified N160 control retains CD/CDi errors of −5.441%/−6.370%. Accepted
weighted roots can retain large interval residuals; the six modified N160
states have local normalized residual maxima of 1.00–4.00, despite projected
residuals below 1e-14. No pointwise or mesh-convergence claim follows.
All 36 calls finish without timeout; independent saved-data checks pass.
Production defaults and registered scores remain unchanged.

The subsequent [full SA-4 lift-polar count/K40 comparison](../../artifacts/isae/sa4-modal-nodecount-20261030/report.md)
combines the source-supported node-count interpretation with the same fixed
40-mode formulation. All 21 native primary rows are tested on modified
80/160-interval controls and retained 78/156-interval candidates. The candidate
returns all 42 valid solutions and passes **276/294**, versus **262/294** for
the controls: 14 gains, no losses. It recovers 3.086° on the coarse mesh and
3.59° on the fine mesh. Every nonzero angle except 7.06° passes all seven
outputs on both candidate grids. At 7.06°, CD remains 4.39–6.19% low, CDi
6.34–6.83% low, and efficiency 6.53–7.12% high. Zero-incidence discrepancies
account for the other ten unpassed checks, with fine-grid CL/Cm differences
of about 4.93e-6/4.15e-6 absolute.

This supports a count/representation interaction, but not resolved local flow:
candidate projected residuals are below 1.64e-14 while local interval residuals
reach 3.31764. Maximum local normal Mach is 0.87140. The 3,833-check independent
audit passes and all 16 previous controls reproduce. The source-backed 78 count
remains a historical hypothesis; 156 is its refinement, not a recovered native
I160 mesh. The 588 repeated diagnostic outputs reuse 147 primary-table cells
and exclude the separate CD-table scope, so they must not be merged with the
registered whole-SA-4 denominator of 588. The original spacing-only table and
production defaults remain unchanged.

The [complete separate drag-table follow-up](../../artifacts/isae/sa4-drag-polar-20261030/report.md)
now closes that coverage gap. All 21 drag-table rows run on N18/N36 with
K=min(40,N), a prospective cap consistent with the retained primary K40 setup.
The 42 new CD candidates pass **286/294**; together with all 42 retained
primary candidates they pass **562/588**, with all 84 solves valid. Four fresh
pointwise controls are additional comparisons, excluded from that combined
score. The original direct scalar sampling is retained throughout; no best-row
substitution from the nodal-alpha experiment is included.

The complete CD scope exposes eight failures absent from the earlier selected
subset: drag and CD at N36 incidences 7.12392°, 7.60807° and 8.10951°, and at
N18 incidence 10.098°. Their CD errors are **3.07–3.19% high**. Thus the
earlier recovery of five coarse drag states does not generalize to every row
or refinement. All new CDi comparisons pass, while the primary 7.06° CDi
deficit and small zero-incidence discrepancies remain. All four current
pointwise controls and seven historical sampled states reproduce to roundoff;
the independent audit passes 4,062 checks. Fresh local residuals stay below
1.924e-14 and normal Mach below 0.262779. These eight new mismatches are
converged output differences, distinct from the primary truncated basis's
unresolved local flow. Historical meshes/mode counts remain unverified, and
registered scores and production defaults are unchanged.

The [saved-force decomposition](../../artifacts/isae/sa4-drag-decomposition-20261030/findings.md)
then reconstructs all 84 candidate states without another flow or solver call.
The four failed CD-table states have 0.61–1.23 percentage points of total-CD
error from Trefftz CDi and 1.84–2.47 points from the combined CD−CDi remainder.
The latter is not identified native profile drag. The curved-interval
span-vector difference accounts for only 1.18–1.85% of OpenSwing's
near-field/Trefftz gap in these states. Refinement near 7–8° chiefly changes
circulation drag; by 10.098°, reduced tangency drag dominates the total change.
For primary K40 states, the Eq.70 tangency term includes substantial local
residual and signed cross contributions; full-rank CD-table states have those
terms at roundoff. Thus the two cohorts retain different numerical limitations.
The 2,268 arithmetic checks pass, with strip forces reproduced to 2.67e-15
scaled error; the independent spline/force reconstruction passes 12,850 checks.
No production correction or changed pass count follows; the next
source-based discriminator separates bound and trailing-wake interactions at
unchanged saved states, which requires per-source fields absent from these exports.

That [bound/wake reconstruction](../../artifacts/isae/sa4-vortex-drag-decomposition-20261030/findings.md)
is now complete for all 84 states. There are 84 primary and 84 independent
prescribed-circulation field evaluations, with zero nonlinear solves or new
meshes. The 4,032 primary and 18,694 independent checks reproduce saved
velocities, drag and shared-node wake cancellation. At the four CD failures,
same-half different-strip interactions account for 76.2–79.3% of the internal
near-field/Trefftz gap, versus 20.5–22.8% own-strip and less than 1% opposite-
half work. The half-infinite-wake span-vector term is only 0.46–0.71% of the
gap. Positive bound work and larger negative longitudinal-ray work cancel
substantially; this is not a missing-drag correction or a native component
comparison. The current kernels reproduce independently, leaving distributed
force integration as a more specific source-review target. The candidate
score and all production equations remain unchanged.

The [all-state pair-separation calculation](../../artifacts/isae/sa4-vortex-drag-decomposition-20261030/interpretation-review.md)
then passes 1,596 saved-arithmetic checks. Adjacent strips account for 71–73%
of the internal near-field/Trefftz gap in the four failed CD states, but also
dominate that gap in passing states. This narrows the force-sampling review
to local adjacent intervals without establishing a correction or attributing
the native total-drag error. No new field evaluation or solve is performed.

The next [adjacent-interval derivation](../../artifacts/isae/sa4-adjacent-asymptotics-20261030/README.md)
finds an explicit curvature term proportional to interval length under the
documented receiver sampling. Independent algebra and saved refinement
ratios agree. Comparing the formula with all 84 retained states gives median
interior coefficient errors of 7.43→2.81% for the N18/36 drag-table pair and
1.46→0.979% for the N78/156 lift-table pair. These are separate angle cohorts;
tip-inclusive agreement remains much poorer. A term that decreases
per pair can still accumulate over more pairs, so refinement alone need not
remove this contribution. This is not a proof of the global limit or the
native drag error. No receiver, equation or reference count is changed.
Independent synthetic kernel checks pass 62/62 scenarios (496 two-interval
evaluations); the saved prediction review passes 3,716 checks. Removing the
negative term would increase drag, opposite the needed change at the four
remaining positive CD-table errors.

The [public-history audit](../../artifacts/isae/sa4-input-history-20261030/report.md)
finds one SA-4 model version across all 14 reachable commits. The three literal
section-angle entries of −0.1° and the current small nonzero lift reference
already coexist at the first data commit, so no later tracked input edit
explains the zero-incidence discrepancy. A different early root-level output
table exists, but its producer/settings are unidentified and its force
normalization differs. It is retained as historical evidence, without replacing
the current targets or establishing how ASWING sampled the input properties.

The subsequent [section-angle sampling diagnostic](../../artifacts/isae/sa4-alpha-node-sampling-20261030/report.md)
changes only how the original alpha spline is sampled: node values are
interpolated to the existing Glauert material midpoint. All 20 calls at five
selected angles are valid, with **55/70** nodal versus **52/70** direct checks.
Three zero-incidence comparisons improve on N78: lift, CL and Cm. Absolute
CL/Cm errors fall to 9.61e-8/6.38e-8, but efficiency remains 5.31% high and tiny
CDi fails its unchanged strict tolerance. N156 gains no checks and its small
zero-incidence errors increase slightly; 7.06° CDi remains 6.34–6.83% low.
The other selected angles (0.29°, 3.59°, 7.56°) retain all seven matches on both
meshes. The original alpha table and all other properties/geometry remain
unchanged. Although node mapping is documented, using Eq.154's position weights
for scalar alpha remains a hypothesis. This mixed refinement result does not
authenticate native sampling or justify a production change.

**SA-4's remaining 7.06° induced-drag discrepancy tracks span efficiency.**
The [saved-state factorization](../../artifacts/isae/sa4-modal-spacing-20261030/loading-factorization.md)
finds Trefftz lift within 0.141% of the native value inferred from Eq.211,
while efficiency is 6.64–7.25% high and CDi is 6.28–6.81% low across the
four K40 spacing/mesh states. The factorization closes to roundoff. This is
a different pattern from the SA-1/SA-5 circulation-lift deficit described
below. The native inference assumes zero Trefftz sideforce and positive lift;
saved OpenSwing circulation and sideforce satisfy symmetry to numerical
precision. It does not recover the native circulation distribution.

The [native table/figure check](../../artifacts/isae/sa4-modal-spacing-20261030/native-706-feature.md)
also confirms that 7.06° has a localized efficiency dip and drag increase:
relative to interpolation between its neighboring native rows, e is 6.16%
lower and CDi 6.19% higher, while inferred CLi differs by only 0.055%.
The archived MATLAB figure contains the same CL point, so it is not a local
transcription error. A separate drag-table sequence has no analogous dip,
but uses different angles and NODE/I20 instead of I80. Native branch and
discretization sensitivity therefore remain relevant questions; this does
not establish that the reference is invalid. Its failed comparisons remain.

The subsequent [K40 warm-start comparison](../../artifacts/isae/sa4-modal-sequence-20261030/report.md)
does not recover that feature. All four same-mesh paths pass a strict identity
at 6.55°, then converge directly at 7.06° and 7.56° without fallback. Every
warm 7.06° result retains 3/7 reference matches; every warm and cold 7.56°
result passes 7/7. Across all eight warm/cold pairs, maximum scaled circulation
difference is 1.93e-12 and maximum scaled coefficient difference is 4.01e-14.
All 16 calls are valid, with 68/84 repeated output comparisons passing.
This rules out a material effect from the tested initialization change; it
does not prove uniqueness or native branch identity. The archive's figure
corroborates the 7.06° point, but no native residual history establishes its
convergence. Its driver requests 8.06°, which both the table and figure omit;
the reason is undocumented. References and registered counts remain unchanged.

**Approaching SA-4 from lower angle also reaches a continuation limit.**
The [current-equation upward sequence](../../artifacts/isae/sa4-current-ascent-20261030/report.md)
adds six valid intermediate states from 3.64875° to 3.69532°. All 22 calls
finish without timeout; 15 residual failures cause the step to fall below
the fixed 0.0001° minimum. The seven accepted states, including the identity
control, retain maximum residual 1.44e-13 and maximum normal Mach 0.93136.
No published reference target is reached. Together with the descending path
below, this shows why simply taking smaller angle steps has not filled the
middle interval. It does not establish nonexistence of other roots or native
branch identity. Spacing scores and production defaults remain unchanged.

**Local asymmetric branch switching is not yet a supported SA-4 remedy.**
The [subsequent local-event refinement](../../artifacts/isae/sa4-local-events-20261030/report.md)
adds four valid states near 5.6608927843° and narrows the common even/odd
sign bracket 1,000-fold. Cross-parity coupling grows, leaving distinct
full-system events unresolved. A fifth candidate satisfies the equations but
exceeds the fixed predictor-correction bound; it is not physically validated
or accepted. Independent saved curvature projections also bend toward higher
angle for both directions. This supports testing the lower-angle solution
branch next, without establishing that no other lower-angle roots exist.
No published reference point or new passing check is added.

**SA-4's tracked solution path turns near 5.6609°.** The
[physical-angle arclength diagnostic](../../artifacts/isae/sa4-alpha-arclength-20261030/report.md)
continues beyond the descending-angle limit with eight full-state corrections.
All nine saved states satisfy the original physical gates, with maximum
residual 7.65e-14 and section-normal Mach below 0.789. Angle decreases and
then increases as the continuation moves forward. This supports a turning
path as an explanation for why successively smaller downward steps stopped
helping. Both even and odd reflection blocks change determinant sign in the
same unsampled interval; the experiment does not establish a simple full-system
fold, native branch identity or absence of other lower-angle roots. All 857
independent saved-data checks pass. No new reference target is reached, and
the default and spacing-diagnostic counts above remain unchanged.

**Smaller angle steps recover a second failed default-grid SA-4 point.**
The [adaptive descending follow-up](../../artifacts/isae/sa4-adaptive-descending-20261029/report.md)
revalidates 6.55°, then reaches 6.10° through a valid 6.325° intermediate.
All 7/7 outputs at 6.10° pass, with maximum error 1.283%, residual 6.87e-14
and maximum normal Mach 0.840. The same equations, default mesh and direct
solver are retained. Descent then stops near 5.66095° at the declared minimum
step; 5.57° remains failed and lower targets are not attempted. Intermediate
angles have no reference scores. This strengthens the initialization finding
without changing the spacing comparison or registered cold-start counts.

**Initialization can recover a failed SA-4 point without changing physics.**
The [descending-angle diagnostic](../../artifacts/isae/sa4-descending-alpha-20261029/report.md)
revalidates the known 7.06° solution, then recovers 6.55° on the default
160-interval mesh with all 7/7 outputs passing. Maximum reference error is
1.862%, residual 7.55e-15 and section-normal Mach 0.604. The next 6.10° step
fails and all lower points are skipped. This establishes an admissible matching
root at one failed cold-start point; default scores and the broader spacing
conclusions remain unchanged.

The subsequent [fresh-Jacobian trust-region test](../../artifacts/isae/sa4-trust-region-20261029/report.md)
changes step direction in weak modes but does not recover the three difficult
SA-4 cold starts within 1,000 residual evaluations each. It still makes
measurable progress at the budget; this is distinct from the damped Newton
stagnation. No valid equilibrium or reference pass is added.

The latest [Armijo Newton diagnostic](../../artifacts/isae/sa4-damped-newton-20261029/report.md)
finds that shorter, residual-decreasing steps still do not recover the three
difficult SA-4 cold starts. Step fractions collapse to approximately 1e-14
while residuals remain large. The low-angle control retains 7/7 checks.
Thus the tip coupling is not resolved by simple monotone damping; these
diagnostics add no registered matches and do not establish that no root exists.
The saved terminal matrices are severely ill-conditioned even after column
scaling; appreciable merit gradients distinguish this from demonstrated
stationary nonzero residuals. Changing the weak Newton direction is a separate
remaining solver investigation from merely shortening it.

The later [full-Newton comparison and tip localization](../../artifacts/isae/sa4-full-newton-20261029/report.md)
find that undamped iterations also fail at the three difficult SA-4 cold starts.
Across all 42 saved directional trials at six earlier failed states, at least
99.49% of squared nonlinear departure lies in the curved-tip samples. The
linear flow terms cancel, leaving the full smooth stall-leakage composite,
which includes circulation-dependent local speed. That identifies the next
equation-level question without establishing a stall-function defect or adding
reference passes.

The [exact SA-4 curvature split](../../artifacts/isae/sa4-stall-speed-curvature-20261029/report.md)
then distinguishes the section-law term from speed-norm curvature. The former
dominates close to the failed states, but their full-step remainders are
comparable and partly cancel. The scalar-law term itself still depends on
local speed through the section lift coefficient; the evidence does not
justify tuning stall parameters or blaming one independent physical cause.
In fact, its speed-denominator contribution has 1.58–6.12 times the
curvature-weighted amplitude of the circulation-numerator contribution across
the six saved directions. They partly cancel. The common difficulty within
these SA-4 states is the coupled circulation, local-speed and section-law
response; this finding does not establish the cause of SA-1/SA-5 drag errors.

The [SA-4 direct-solver scaling check](isae-sa4-pointwise-scaling-20261029.md)
does not recover any of its six rejected direct calls, despite improving
initial matrix conditioning. Fresh Jacobian checks at all six endpoints
pass; full Newton steps increase residual merit, while sufficiently small
steps decrease it. This points to a nonlinear step-selection difficulty
in these states, with no established solver remedy or new reference passes.
It does not explain SA-1/SA-5's separate converged high-incidence drag deficit.

The subsequent [SA-4 rejected-field capture](isae-sa4-tip-resolution-20261029.md)
reproduces the extreme tip speed independently and localizes it to a wake
filament 4.58 micrometres from the force receiver. Increasing the Fourier count
reduces the outermost spike but moves the largest speed inward, while local
residuals remain large. This reinforces the separate tip-resolution issue;
it supplies no new passing registered result or justification to remove a gate.

The [fixed-circulation refinement](isae-sa4-tip-resolution-20261029.md#fixed-circulation-refinement)
then isolates this effect from nonlinear branch selection: the captured
40-mode tip Mach grows from 1.44 to 11.92 as intervals increase from 160 to
1,280 with all Fourier coefficients unchanged. The fixed 80-mode field also
crosses Mach one at 1,280. A local filament derivation predicts the growth.
These are prescribed fields, not new equilibria or a proof that all default
SA-4 failures share this mechanism; registered counts remain unchanged.

The later [independent finite-wing checks](isae-finite-wing-oracles-20261029.md)
pass all 198 modal field checks against continuum integrals. An 800-panel
SA-5 closure replay finds no percent-scale velocity discrepancy; its one tiny
retained mismatch is explained by receiver-coordinate reconstruction in a
targeted precision study. These are equation checks, not new ISAE passes.

**Near-field total drag is sensitive to spacing.** SA-2 improves dramatically
while its Trefftz CDi was already within 3%. At fixed 100/200 intervals, every
registered SA-2 output now passes. Thus the earlier 98-interval diagnostic's
success was not merely a panel-count effect. Fine-mesh total-CD errors are
+0.0400%, +0.0602%, +0.0624%, +0.0165% and −1.1304% over the five incidences.

SA-5 shows the same distinction: spacing changes total drag much more than
Trefftz induced drag. At 18°, fine-mesh CD moves from −3.34% to +1.02%, while
CDi moves only from −3.38% to −3.35%. All total-drag checks pass, but refinement
still changes them materially: at 14°, modified-grid CD error is −0.329% on
200 intervals and +2.333% on 400. Passing 3% does not establish mesh independence.

The subsequent [SA-5 root-loading study](isae-sa5-root-loading-20261029.md)
finds that 72–76% of the additional induced-velocity lift lies within the
inner 10% of the half-span. At 18°, cross-grid circulation transfers reproduce
98.58–100.01% of its spacing change through the mesh/transfer term, while
Trefftz lift scarcely changes. This attribution applies to that lift term,
not total drag; prescribed cross-grid fields are not equilibria. The 400-interval
modified state reaches section-normal Mach 0.97923 near the sharp root.

**Small loading differences produce larger induced-drag differences.** SA-1's
fine-grid high-incidence CL deficit is about 1.75–2.67%, while CDi is about
3.15–4.68% low on the baseline. The quadratic loading dependence accounts for
this amplification; changing spacing or doubling the baseline mesh barely
changes the remaining CDi errors. SA-5 retains a similar high-incidence CDi
deficit after its total-drag checks improve.

An [earlier explicit K40 comparison](sa1-discretization-followup-20261027.md)
also left SA-1's high-angle CDi essentially unchanged: at 18.091° and N400,
K40 gave 0.064092181882 versus pointwise 0.064092182069. That uses an older
kernel and default cosine spacing, but prevents treating the SA-4 K40 recovery
as evidence of a common modal remedy. The reviewed SA-5 comparisons remain
pointwise in the original spacing table. Neither case's shell driver
authenticates a historical Fourier count.

The new [SA-5 mode/spacing study](../../artifacts/isae/sa5-modal-spacing-20261030/report.md)
tests that hypothesis with 32 valid cold solves: 14° and 18°, both meshes and
spacings, and pointwise/K20/K40/K80 circulation. No representation recovers
the 18° CDi failures. On the finest modified mesh, CDi errors are −3.3501%
pointwise, −3.5715% at K20, −3.3634% at K40, and −3.3556% at K80.
At 18°, K40→K80 changes CDi by at most 0.00964%, while the inferred native
Trefftz-lift deficit remains 1.85–1.99% across all states. This strengthens the
loading-deficit finding without proving which native section or load
construction differs. The eight pointwise controls reproduce exactly, and
all 1,171 independent saved-data checks pass. The overall 182/224 diagnostic
score repeats 14 native cells and adds no registered passes. K20 loses the
coarse default CL/lift pair as well. Local residuals up to 0.1102 in truncated
roots and near-root normal Mach up to 0.97923 preclude treating agreement of
integrated outputs as resolved local flow.

The [full-polar SA-5 PG comparison](../../artifacts/isae/sa5-pg-spacing-20261030/report.md)
tests the remaining documented compressibility choice on the same modified
meshes. All 48 cold solves are valid. PG=V/a reduces 18° CDi errors to
2.63–2.68% low, recovering both remaining high-angle checks, but introduces
eight failures elsewhere: Cm at 1° on both meshes (5.05–6.08% low), and
N400 CD/dimensional drag at 10°, 12° and 14° (3.36–3.66% high). Its
full-polar score is therefore **160/168 versus 166/168 with PG=0**.
The historical PG setting is unknown; choosing a different setting for
selected rows would not reproduce one consistent native polar. All 2,922
independent checks pass. Maximum local normal Mach reaches 0.99031, so
integrated agreement still does not establish mesh convergence. Production
equations, defaults, gates and registered counts are unchanged. The linked
[source context](../../artifacts/isae/sa5-pg-spacing-20261030/source-context.md)
also records older SA-1 PG comparisons: the highest-angle CDi discrepancy
remains above 4%, so this is not an established common remedy.

The [saved-section audit](../../artifacts/isae/sa1-sa5-failure-themes-20261029/section-stall.md)
confirms that the current smooth stall correction is appreciable in these
states, even though every exported hard-limit `stalled` flag is false.
SA-1's maximum section cl ranges from 1.0934 to 1.1501 at the failing angles;
SA-5 reaches 1.0986 at 18°, against literal model CLmax=1.2. The smooth law has
nonzero tails below that cap. This makes section closure and local-velocity
definitions a useful next comparison against the published equations. It does
not prove a stall-law error or justify tuning the cap to the reference outputs.

**SA-4 combines numerical failures, finite force differences and small
zero-incidence loads.** Modified spacing recovers 6.55° at 160 intervals but loses 2.62°
at 80 intervals. Failures at 4.06°, 4.60°, 5.13°, 5.57° and 6.10° on 160
intervals persist. These failed solutions remain excluded from error statistics.
At the converged 7.06° fine-mesh state, total-CD error improves from −8.09% to
−5.31%, but CDi changes from −6.07% to −6.29% and efficiency stays about 6.60%
high. Near-zero-incidence CL and Cm differ by only about 5e-6 and 4e-6 in
absolute terms, despite large relative percentages. These are separate issues.

**Zero-lift efficiency is an output convention issue.** SA-5's four unavailable
values have CL=CDi=0. ASWING prints zero; at the time of this spacing-only run,
OpenSwing returned unavailable for the undefined ratio. The later correction
above implements the native exact-unloaded convention and recovers these four
checks without altering a force equation or tolerance.

Subsequent [independent section-limit checks](isae-sa1-sa5-loading-audit-20261029.md)
pass all 12 synthetic states, including smooth stall, sweep, dihedral and PG
transformation; they find no section-law defect. The [SA-4 solver audit](isae-sa4-solver-audit-20261029.md)
improves Jacobian use without changing its failed states and identifies large
tip-wake velocities. The remaining source questions concern native curved-axis
meshing and force sampling, alongside the high-angle circulation difference.
SA-2's mesh evidence does not authenticate a universal geometry recipe.

The later [Eq.48 rigid-geometry study](source-rigid-arc-measure-20261029.md)
recovers SA-4 at 4.06° on 160 intervals, but fails on 320 intervals and worsens
one coarse SA-3 moment comparison. It therefore remains a separate diagnostic.
That audit also exposed a zero-strain interval-length defect in the optional
source structural operator, which has been corrected and checked in native and
offline WASM. The ordinary rigid SA cases do not use that operator; their
registered scores and the spacing comparison above are unchanged.

The [node-count and interior-frame follow-up](isae-sa4-frame-allocation-20261029.md)
provides a more specific SA-4 finding. Keeping modified spacing but interpreting
the requested node counts as 78/156 and 18/36 nonzero intervals improves a
selected failure/control subset from 70/140 to 87/140. The five newly failing
coarse drag pairs all recover, and the 6.10° fine solve passes; five solver
failures remain. This fixed interpretation is supported by root-break rules
and public SCN listings, but the exact historical SA-4 nodes remain unknown.
No full candidate score is inferred from the subset. A separate frame test
recovers one state and loses another. The source also contains three −0.1°
zero-lift-angle entries near each tip, so its small zero-incidence loads must
not be dismissed as pure roundoff. Production defaults remain unchanged.

The subsequent [spline endpoint comparison](isae-sa34-spline-endpoints-20261029.md)
rules out switching between the two existing endpoint policies as a standalone
fix: 20 fresh paired calls change the selected SA-3/SA-4 score from 45/70 to
42/70, with an additional SA-4 failure. SA-1/SA-2/SA-5 geometry changes only at
roundoff level. Independent CASEI box-coordinate comparisons do not identify
one historical spline caller. The full spacing counts above are unchanged.

The acceptance helper also received a boundary correction so that exactly 3%
passes when the relative limit equals an originally strict absolute limit.
All 423 helper/runner/summary tests pass. Independent replay verifies identical
complete acceptance views for all 3,179 baseline and 184 diagnostic jobs;
this correction changes none of the reported scores. The original run pins
and strict evidence remain preserved in the
[policy verification receipt](../../artifacts/isae/sa-three-percent-20261029/analysis/policy-boundary-terminal-receipt.json).

Evidence: [paired results](../../artifacts/isae/sa1-sa5-modified-cosine-20261029/report.json),
[every check and failure transition](../../artifacts/isae/sa1-sa5-modified-cosine-20261029/per-check-analysis.json),
[execution receipt](../../artifacts/isae/sa1-sa5-modified-cosine-20261029/terminal-receipt.json),
[baseline failure analysis](../../artifacts/isae/sa1-sa5-failure-themes-20261029/baseline-failure-themes.md),
and [section-law audit](../../artifacts/isae/sa1-sa5-failure-themes-20261029/section-stall.json).
