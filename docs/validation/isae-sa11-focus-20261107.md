# SA-11: current comparison and pre-stall focus

2026-11-07. The complete registered SA-11 scope passes **163/4,592 comparisons
at 5%**. All 656 jobs have outcomes: 47 valid states, 281 local-Mach rejections,
and 328 original normalization blockers. There are no solver timeouts or
allocation failures. No production aerodynamic equation changes in this study.

The user has deferred post-stall repairs and moved the active focus from SA-10
to SA-11. All original comparison rows remain counted; this priority change
does not remove stall rows or unavailable references from the denominator.
SA-10 remains 1,610/2,268 at 5%.

On 2026-11-08 the user designated AVL as authoritative and prioritized SA-11
over further SA-2 work. The [actual winglet conversion audit](isae-sa11-avl-conversion-20261108.md)
now compares four one-row native AVL/OpenSwing cases using the SA-11 geometry.
Vortex-force lift differs by at most 0.40% and drag by 1.95%; both reproduce
large junction velocities that grow with span refinement. The audit identifies
beam-versus-bound-line normals and force directions, plus different interpolation
of the lower winglet's incidence. These linear controls do not validate stalled
sections or the archived transonic results; primary counts remain unchanged.

The [archived-speed baseline comparison](isae-sa11-avl-baseline-20261108.md)
then finds the same pre-stall lift/CDi bias in native AVL and production
OpenSwing. At 240 m/s and 0°/1°, the independently supplied section slope 6.34
reduces both solvers' lift/CDi errors below 0.5%, while all production states
remain below stall and local Mach limits. Matched vortex lift/drag agree within
0.026%; total drag and the native producing inputs remain unresolved. This
independently supports an input mismatch without changing the primary score.

The [drag-sampling isolation](isae-sa11-drag-sampling-20261108.md) explains why
the shared native grid increased total drag: on identical endpoints, moving
the receivers accounts for 93.45–93.95% of the change in near-field vortex drag.
Across three grids/sampling choices, Trefftz drag varies below 0.30% for each
fixed section-input set. Six states are retained, all pre-stall and below the
Mach guard. The original archive's sampling remains unknown; no default,
force-law change or new primary pass follows from this sensitivity diagnostic.

The [upper-winglet incidence check](isae-sa11-winglet-incidence-20261108.md)
finds a concrete source conflict: ISAE Figure 40 specifies −4° upper twist,
whereas the supplied `.asw` specifies +4°. At the archived 1°/240 m/s condition,
the figure-derived sign reduces native AVL CL/CDi errors from 4.12%/12.17% to
0.53%/0.31%. OpenSwing circulation agrees with native AVL within 0.075% for
that alternative, but both fields still imply a local section-normal Mach
near 1.57 at the junction. This is evidence about the input, not an accepted
production state. All original models and the primary 163/4,592 score remain.

The [21-angle follow-up](isae-sa11-winglet-polar-20261108.md) confirms this
finding for every archived row from 0° to 5°: report-derived −4° gives native
AVL lift errors of 0.510–0.560% and CDi errors of 0.289–0.332%. Its production
circulation differs from native AVL by at most 0.0813%, with at least 10.54
stall-transition widths of margin. All 42 retained production states still
fail the local Mach guard. The comparison plot and full data are saved;
the next priority is the local junction velocity and force/moment treatment.

The [archived-speed current-wind check](isae-sa11-winglet-current-wind-20261108.md)
then retains sixteen comparisons over two angles, twists and meshes. All
still fail the local Mach check. Direct integration reproduces their worst
fields within 9.49e-10 m/s: the 1° maxima remain wake-dominated at the winglet
root, while the finer 5° current-wind maxima move to a bound-vortex interaction
at the main-wing center. Those last two cases also cross local stall limits.
ISAE Part I p. 21 notes excessive-refinement velocity singularities after
elliptical-wing loads converge at practical resolution; the next check is
the documented practical resolution range, without fitting the archived answer.

The [practical-resolution sweep](isae-sa11-practical-resolution-20261108.md)
now completes eighteen fixed checks: pointwise 20/30/40 intervals per logical
beam and Fourier 20/30/40 modes on two independent structural meshes. All
still fail local Mach. The published sine projection reconstructs the saved
states, and all six current-wind Fourier circulations agree with separate
linear tangency solves within 2.9e-12 relative error. No default change or
load-convergence claim follows. The remaining interpretation questions are
native connected-surface/mode domains and local junction velocity treatment;
the pointwise failures remain separate evidence that a mode change alone is
insufficient.

The [surface-grouping and command audit](isae-sa11-command-grouping-20261108.md)
distinguishes structural beam groups, zero-core physical groups and the
common coordinate used in loading plots. None establishes a merged native
Fourier domain. Across the 17 archived shell files, ten contain `kk`/`mm`
before solving and seven omit them; no startup sidecar is retained. The
manuals document the single-letter options but do not authenticate the
doubled-command interpretation. No solver change or new pass follows; the
local junction velocity and native producing setup remain the focus.

The [native chord/span refinement](isae-sa11-native-chord-refinement-20261108.md)
adds six native AVL checks at 1°/240 m/s with the report-derived −4° twist.
Two/four/eight chord rows on 64/128 span strips retain lift/CDi agreement
within 0.369%/1.345%, but local root velocity spikes persist and grow with
span refinement. Near-field vortex drag changes by 6.30–12.55%. This rules
out the one-row representation as the sole source of the native junction
problem; it does not validate the local flow or supply a production repair.
The public-history follow-up checks all 65 SA-11 files and finds no older
replacement winglet input among the retained snapshots.

The [root-conformity control](isae-sa11-native-root-conformity-20261108.md)
aligns native shared-chord origins without moving the planform. Local Mach
improves but still increases from 1.09 to 2.86 on span refinement. The
[adjacent-bound analysis](isae-sa11-shared-bound-corner-20261108.md) then
predicts the strongest bound-source growth from its analytical corner limit
within 0.0005%. No neighboring source is dropped. Failure diagnostics gain
physical distance and shared-corner context; numerical predictions and the
primary 163/4,592 count remain unchanged.

The [authoritative reference library](aswing-authoritative-references.md)
records the user's 2026-11-08 instruction to treat the ISAE reports as primary
evidence. Part I, I.4.0, p. 35 explicitly reports local lift divergence at
SA-10's three-branch tip-sail junctions in ASWING. Its SA-11 discussion on the
same page describes MSES-derived airfoil inputs without specifying every value;
Table 2, p. 23 nevertheless labels SA-11 fully repeatable. These are separate
pieces of evidence to reconcile with the supplied files. The SA-10 statement
does not establish the cause of OpenSwing's SA-11 Mach rejection or remove the
requirement to reproduce the archived SA-11 results.

The [native AVL control](avl-native-controls-20261108.md) now supplies a working
unmodified-numerics finite-chord reference and 29 small serial outputs. It
confirms that the earlier all-edge induced-force diagnostic is not AVL's force
rule. In a simple continuous winglet, span refinement changes total lift by
0.0966% but increases peak strip normal force by 32.81%; integrated agreement
still cannot validate local junction flow. This does not establish a native
ASWING fix or add any SA-11 passes.

The [matched native field comparison](avl-matched-fields-20261108.md) then
checks nine one-row rectangle, swept and winglet controls at identical actual
bound/control receivers. Original near-field lift/drag agree within
0.000000571%; the small uniform difference follows from AVL's rounded
`1/(4*pi)` constant. Native AVL reproduces the sharp winglet's peak normal
speed growth from 1.43 to 8.50 times freestream over three grids. This supports
the elementary kernel and force arithmetic, while leaving actual SA-11
geometry, mode mapping and junction treatment unresolved. No production
equation, Mach guard, registered fraction or scope changes.

The subsequent [section-input diagnostic](isae-sa11-section-inputs-20261107.md)
finds that the baseline alone specifies `dCLda=7`, versus 6.34 in every other
SA-11 model. Using that independently specified slope reduces CL error to
0.124% and CDi error to 0.133% across four pre-stall states. The baseline also
has different pressure/friction inputs. Transferring both sets leaves CD
5.32–6.27% low at 1°; the native producing parameters remain unverified.
Original files, primary counts and production equations are unchanged.
The subsequent [frozen-influence check](isae-sa11-frozen-inputs-20261107.md)
leaves those transferred-input drag errors at 5.18–6.08%. All eight frozen/current
saved outputs satisfy the independently reconstructed load equations within
3.33e-16 normalized error. This toggle does not resolve the discrepancy.
The [spline-endpoint check](isae-sa11-spline-endpoints-20261107.md) excludes
endpoint conditions as an explanation for the baseline: its two-knot segments
are unchanged under either retained policy. For the original extension, the
alternative changes drag errors by only 0.289–0.315 percentage points across
four pre-stall states, preserving every sampled 5% decision. Twelve fixed
calls finish; no defaults or primary counts change.

The [winglet junction investigation](isae-sa11-winglet-junction-20261107.md)
reproduces the bundled examples' default-setting Mach errors. Independent
endpoint reconstruction agrees within 1.416e-15 m. The dominant upper-root
velocity remains even with nearly equal circulation across the junction;
AVL's tiny same-component core has negligible effect on the saved wake field.
Current-wind influences allow the upper model to compute at 30 m/s and 5 degrees
on N48/N96, but the local tip velocity still grows and the upper/lower model
still rejects. These diagnostic examples do not change the registered scope.
The [root-height follow-up](isae-sa11-winglet-root-height-20261107.md) excludes
closing the lower attachment's 70-micrometre gap as a sufficient fix: all four
temporary changed states have larger maximum local Mach and still reject.
The [explicit Fourier follow-up](isae-sa11-winglet-modes-20261107.md) finds that
five modes let the upper/lower model compute at low speed, but leave large local
flow residuals and 12.69% mesh sensitivity in total drag. Nineteen modes restore
Mach rejection on both meshes. Fourier truncation is not an established repair.
The [expanded winglet literature search](winglet-lifting-line-literature-20261107.md)
finds explicit connected/forked-surface treatment in DLR's manual and several
different treatments of singular self-induced velocity. It sets out separate
topology, force-field and unswept-junction controls; none is yet an ASWING fix.
The [further literature addendum](winglet-lifting-line-literature-addendum-20261107.md)
adds explicit sharp-junction evidence, corrected section-velocity formulations,
and distributed-vorticity winglet applications. It distinguishes those methods
from ASWING's shared-physical-index zero-core rule; no production change follows
from this search alone.
The [unswept junction control](unswept-winglet-junction-20261107.md) now finds
identical results under same-mesh logical partition and verifies fork fields
against independent Biot–Savart integration. A sharp, unswept, coincident-root
winglet still develops approximately inverse-distance bound-induced velocity.
This separates a sharp-corner singularity from the offset-root and swept-line
mechanisms; the native ASWING treatment remains unresolved.
The [finite-chord follow-up](winglet-finite-chord-20261107.md) independently
matches the one-row unswept control to roundoff. Added chord rows and a separate
fixed-circulation spreading control reduce the quarter-chord spike, while actual
vortex-edge maxima still grow under refinement. The different load definitions
are recorded explicitly; this is not an established ASWING repair.
The [generalized-field audit](winglet-generalized-fields-20261107.md) executes
pinned MachUpX geometry methods on the controlled winglet fixture. Connecting
the lifting line before applying the correction keeps prescribed-field peaks
near 1.11 times freestream over three grids; separate groups retain growth.
The saved circulation does not solve the generalized section equations, and
adjacent near-wake joint gaps remain. No production method or pass count changes.
The [nonlinear section-equation follow-up](winglet-generalized-solve-20261107.md)
now converges all nine variants. Connected generalized lift and drag change
only 0.152% and 0.454% across a fourfold refinement, while the uncorrected
variants retain growing velocities. Connected lift remains 4.30–4.57% below
the four-row finite-chord control; this is model comparison, not ASWING validation.
The [actual-geometry grouping audit](isae-sa11-generalized-topology-20261107.md)
then finds that offset quarter-chord roots and the three-branch upper/lower
attachment prevent a direct port of that connected-path treatment. At N96 the
upper/lower signed circulation imbalance is only 0.09756%, but its separated
root-origin field remains dominant. Twelve grouping checks, two translated
controls and eight exact root-field identities add no production changes or passes.
The [actual-root finite-chord comparison](isae-sa11-finite-chord-20261107.md)
retains ten independent linear solutions after exact overlap subdivision.
Quarter-chord spikes decrease in some cases, but force-edge velocities and
loads remain unstable under refinement; several upper/lower controls have
negative drag. No finite-chord replacement or new reference pass is established.
The [wake-direction isolation](isae-sa11-wake-direction-20261107.md) removes
that negative drag without changing geometry or the PG map. Upper/lower
two-row CL/CD change only 1.22%/0.20% across two span grids, but force-edge
speed doubles and chordwise refinement still changes drag by about 20.6%.
Local root and wake/body encounters remain unresolved; primary counts stay fixed.
The [fixed-circulation quadrature audit](isae-sa11-force-quadrature-20261107.md)
then proves nonzero logarithmic endpoint terms in this independent all-edge
force model and finds two interior wake/body intersections in the upper/lower
geometry. Twelve field evaluations show that more force quadrature cannot
repair that reference model; the root-edge growth matches an independent
analytic prediction within 1.18e-7 N. No production rule or pass count changes.
The [section-velocity equation audit](curved-section-velocity-20261107.md)
finds the current evaluation points consistent with the cited Drela equations,
but demonstrates logarithmic on-line bound-velocity growth even on smooth
curved controls. Eighteen prescribed fields match independent integration;
the published 3D-minus-2D correction has much smaller refinement changes.
Its linear section relation reduces to control-point tangency, while its force
velocity differs. It is not yet a treatment of the actual offset/forked roots
or an accepted production change.
The [actual-winglet section-velocity replay](isae-sa11-section-velocity-20261108.md)
then finds that the correction does not resolve the eight tested root/tip
states. Six local mappings retain the same valid/invalid classification, with
wake contributions 33.6–1,687 times the corrected bound contribution at the
primary maxima. Four current-wind native calls are recaptured and verified;
the original production equations and registered pass count remain unchanged.
The next target is the wake field, distinguishing fixed-location behavior from
maxima sampled progressively closer to a sharp endpoint.
The [fixed-probe wake comparison](isae-sa11-fixed-wake-probes-20261108.md)
finds that coarse upper-winglet force receivers coincide with fine-grid wake
origins, so direct comparisons there would be singular. At 504 fixed off-sheet
probes, many farther locations change little, but root-region interactions remain
sensitive; a main-wing wake ray accounts for most of two large changes. The
current-wind lower-winglet circulation integral changes by 14.87%, confirming
that the remaining discrepancy is not solely a moving velocity maximum.
No new circulation solves, production changes or primary passes result.

The [prescribed swept-wake control](swept-wake-limit-20261108.md) then confirms
logarithmic velocity growth at a fixed point on a straight swept line, matching
the analytic increment within 0.024% on both grid policies. Chordwise attached
legs remove that logarithmic term in this ideal field and approach an
independent finite principal-value reference within 2.524e-6 m/s. This identifies
a near-wake mechanism; consistent forces and the actual offset/forked-root
treatment remain unresolved. No SA-11 passes or production equations change.

The [solved attached-leg force control](attached-wake-forces-20261108.md)
then checks circulation and force accounting together on straight swept wings.
At the finest grid, attached-leg forces reduce a near-field/Trefftz drag
discrepancy from 8.278% to 0.848%. The quarter-chord field remains bounded over
the tested refinement, but attached-leg tip fields grow and the residual drag
gap persists at lower incidence. Boundary force sampling and endpoint behavior
need resolution before applying this alternative to the actual SA-11 roots.

The [continuous force-sampling audit](continuous-attached-drag-20261108.md)
then retains a roughly 1% drag deficit after reconstructing saved circulation
as continuous loading. Chordwise integration restores the global drag identity,
but the reconstructed Trefftz reference also changes by 1.27% at N128. This
isolates a sampling mechanism without proving the original discrete correction
or finite local forces/moments. All original SA-11 acceptance targets remain.

## Complete registered results

Each table has 41 archived rows, two registered meshes, and seven output fields.

| Original model | Mach label | Passing / required | Valid states / 82 | Remaining outcomes |
|---|---:|---:|---:|---|
| Wing alone | 0.70 | 14/574 | 14 | 68 local-Mach rejections |
| Wing alone | 0.75 | 0/574 | 0 | 82 normalization blockers |
| Wing alone | 0.78 | 0/574 | 0 | 82 normalization blockers |
| Wing alone | 0.80 | 7/574 | 7 | 75 local-Mach rejections |
| Wing extension | 0.70 | 100/574 | 18 | 64 local-Mach rejections |
| Wing extension | 0.75 | 0/574 | 0 | 82 normalization blockers |
| Wing extension | 0.78 | 0/574 | 0 | 82 normalization blockers |
| Wing extension | 0.80 | 42/574 | 8 | 74 local-Mach rejections |
| **Total** | | **163/4,592** | **47/656** | **166 computed mismatches; 4,263 unavailable scalar values** |

The older predictions also score 163 at 5%, versus 151 at 3%. The increase of
12 is entirely the allowance change. Fresh predictions agree with the saved
ones within 8.05e-14, scaled by the larger of one and the old magnitude.
The maximum valid circulation residual is 1.03e-14. The maximum individual
physical request takes 0.60 seconds on this host; all 328 requests total
61.64 seconds, excluding batch startup, provenance checking and recording.

Failed finite-reference comparisons have these absolute percentage errors:

| Quantity | Failed checks | Median error | Maximum error |
|---|---:|---:|---:|
| Lift / CL, each | 21 | 7.54% | 8.07% |
| Drag / CD, each | 41 | 11.92% | 25.62% |
| Induced CD | 21 | 14.88% | 16.05% |
| CM | 21 | 7.36% | 7.99% |

All 47 available efficiency comparisons pass. The 21 valid baseline-wing
states fail every field except efficiency. All 26 valid extension states pass
Lift, CL, CDi, CM and efficiency; six also pass Drag and CD. These are computed
subsets, not replacements for the table denominators or mesh validation.

## The low-angle failure is not stall

Eight observed zero-incidence requests cover both original models, both
executable Mach labels and both grids. Every section is at least **29.19 stall
transition widths inside its prescribed lift limits**. The normalized
control-point leakage in the three rejected requests is at most **5.25e-14**.
Circulation is converged. Stall tuning cannot explain these low-angle failures.

| Original model / Mach label | Peak local normal Mach, N64 | N128 |
|---|---:|---:|
| Wing alone / 0.70 | 0.68853 | **1.00085** |
| Wing alone / 0.80 | 0.81992 | **1.24650** |
| Wing extension / 0.70 | 0.66677 | 0.94948 |
| Wing extension / 0.80 | 0.79183 | **1.18086** |

These are local velocities in the discrete lifting-line solution, not evidence
of physical supersonic flow in the reference experiment. The earlier
[independent swept-line diagnosis](swept-lifting-line-limit.md) establishes the
same-line wake singularity with prescribed smooth circulation, without a stall
model or nonlinear solve. The current observations reproduce the low-angle
failure on the current kernel. The subsonic validity guard remains active.

The next investigation should address the baseline wing's pre-stall loading
bias and the swept-tip source/receiver discretization. The registered 64/128
meshes are declared reconstruction choices: the original drivers supply no
NODE request. Native force-point treatment, circulation representation and
startup settings remain unverified. Changing a core, accepting a failed local
flow state, or selecting a coarser passing mesh would not resolve those gaps.

## Source history and remaining coverage

The two model inputs, eight drivers and eight archived tables have identical
Git blob hashes in all seven retained public repository snapshots containing
SA-11. Two earlier snapshots contain no SA-11 files. Thus the available public
history supplies no earlier replacement input for this scope. This does not
authenticate private producing inputs or runtime settings.

The [0.75/0.78 normalization conflict](isae-sa11-archive.md) remains: the
archived force/coefficient pairs imply an area near 97.67 m² at literal density,
whereas these model files specify 0.9329 m². No coefficients, density, areas or
geometry are rescaled. The adapter covers the baseline and extension only;
other winglet variants and their original input issues remain outside this
registered scope. SA-11 and the full project remain unvalidated.

## Verification and reproduction

All jobs preserve original inputs, reference tokens, meshes, PG settings,
stall parameters, cores and validity gates. Each foreground batch runs at
most eight solves with one BLAS thread and explicit collection between calls.
No solver workers are detached. The original and fresh job settings and
target identities are compared before execution.

The first batch omitted the runner's output accounting and stopped while
printing after saving its first physical solve. Its 328 blocked outcomes and
one computed result remain unchanged. The continuation wrapper applies the
runner's strict assessment before the 5% allowance; the final audit applies
that same assessment to all saved records and independently checks every
scalar decision. No physical rerun was needed for this recorder correction.

- [Frozen plan](../../artifacts/isae/sa11-focus-20261107/plan.json)
- [Complete scalar audit and zero-incidence diagnostics](../../artifacts/isae/sa11-focus-20261107/analysis.json)
- [Bounded serial driver](../../artifacts/isae/sa11-focus-20261107/run.py)
- [Strict-assessment wrapper](../../artifacts/isae/sa11-focus-20261107/checked-batch.py)
- [Retained public-history audit](../../artifacts/isae/sa11-focus-20261107/source-history.json)

The exact source hashes and all result hashes are retained in the plan and
analysis. This is a native Python refresh; it does not claim a new browser
sweep, changed aerodynamics, or experimental validation.

The subsequent [Fourier-runner fix](isae-sa11-circulation-settings-20261107.md)
prevents future sensitivity runs from silently inheriting frozen influences
while labeling them current. Seven focused checks pass, including computed
and rejected states. The primary adapter already specifies this setting;
the registered results and historical Fourier archive remain unchanged.
