# Full-scope implementation and evidence ledger

The [FFWT-4 complete source audit](validation/isae-ffwt4-sources-20261106.md)
establishes a required archive scope of **40 histories / 8,000 values**, with
200 existing Fixed-1 matches counted once. The 1,600-value fixed-wing scope
remains a subset. All five explicit driver/model/output pairings are retained,
including Flare20's 16° sideslip and Removed's case-only filename difference.
The original source audit rejected out-of-range point-mass attachments in
three selected PM2 models; their 4,800 reference values remain required.
Qualified source-preserving rigid-pylon handling now permits their analysis,
with native attachment semantics still unresolved. The Removed histories and seven remaining fixed
histories are also uncomputed. Fifteen source tests pass; all 659 coverage
evidence pins verify. Source inventory and shared execution registration are
separate requirements, and the latter remains open.

The [rigid-extension study](validation/isae-ffwt4-rigid-extension-20261106.md)
verifies section-load and steady Schur-matrix equivalence for explicit
synthetic extensions in both material charts; 44 focused checks pass.
This covers real point inertia and spin, with no point airflow. A prescribed
rotating history exhibits first/second-order BDF anchor differences, so exact
finite-step equivalence is contradicted. General point drag/volume flow,
three-dimensional integrated refinement and
browser behavior remain required. The [integrated tip comparison](validation/isae-ffwt4-rigid-time-20261106.md)
now supplies six complete single-axis vacuum histories at three time steps.
Both models converge to an independent exact oscillator; finest errors are
below 0.0577%, including a separate 12/12 check of individual-point motion
scales. Literal source parsing confirms the six rejected objects have zero
CDA, volume, spin and intrinsic inertia. Native attachment semantics remain
a separate unresolved requirement; that study did not change original models
or production handling.
The [continuous dynamic-matrix comparison](validation/isae-ffwt4-rigid-dynamic-20261106.md)
now verifies local-rate/acceleration terms in ten rigid vacuum cases, including
full point inertia/spin and moving-frame effects. All 30 separate inverse-block
comparisons and 24 independent formula tests pass. This completes the
continuous matrix comparison at zero-local-rate equilibria.
The [production attachment implementation](validation/isae-rigid-attachment-production-20261106.md)
now preserves literal PM2 sources and physical masses while resolving their
eligible rigid anchors. Both interpolation policies mesh all three models;
checkpoint identity and 21 built-browser checks pass. Nonlinear 3D histories,
point-airflow extensions, full PM2 coupled histories and native semantics
remain required. This implementation adds no native comparison passes.
The [startup follow-up](validation/isae-ffwt4-startup-20261106.md) implements a
bounded SVD certificate on the existing mechanical block, the source moving-frame
load predictor and complete source Newton assembly with direct derivatives.
Rank/residual thresholds and physical equations are unchanged; 52 rank/predictor
and 27 matrix/network checks pass. The literal Flare20 preflight still exceeds
150 seconds before equilibrium. Built WASM verifies all 128 columns against
centered physical derivatives; the actual browser passes 21 import/load/checkpoint
checks. The [serial-continuation implementation](validation/isae-ffwt4-continuation-20261106.md)
now completes a 55-node Flare20 equilibrium with 17 accepted load steps, no
rejections, and rebuilt residual 4.608e-13. All 40 focused checks pass and three
synthetic formulations match uninterrupted results bit for bit. The built browser
passes 32 restart/identity checks. The later
[workbench implementation](validation/steady-progress-workbench-20261108.md)
adds accepted-step advance, portable progress save/load and exact settings
restoration, checked by 39 JavaScript tests and two actual-worker browser
workflows. Full-load results agree exactly with ordinary solves in the retained
structural and coupled fixtures. Driver-mesh
refinement, other PM2 equilibria and full histories remain requirements, with
no new native comparison passes.

The [PM2 mesh study](validation/isae-ffwt4-pm2-mesh-20261106.md) completes the
107-node Flare20 equilibrium and passes the 55/107-node root-moment mesh gate
at 0.0448% (limit 0.1%). This does not close all-field or gust validation.
The earlier 211-node initial rank fallback exceeded its 90-second cap; the cached
mechanical block's singular ratio is 8.17e-11, below the existing 1e-10 gate.
This motivated conditioning/rank investigation while retaining the physical
residual and mechanism checks. Native comparison coverage is unchanged.
Further invertible scaling passes the unchanged rank gate in a diagnostic
(ratio 1.57e-10), motivating the production refinement below.
The [production refinement](validation/isae-ffwt4-rank-refinement-20261106.md)
now passes 66 native rank/continuation checks and saves the first two 211-node
load steps with rebuilt residuals below 7.80e-13. All 29 built-browser checks
pass, including literal-state agreement and continuation after a complete
page/worker restart. The [211-node follow-up](validation/isae-ffwt4-pm2-211-20261107.md)
now establishes full-load convergence (17 steps, fresh residual 2.06e-13),
while retaining one process timeout with an independently verified saved
boundary. All 21 new audit/comparison tests pass. Spatial accuracy remains
unmet: the 107/211 pair passes 0/7 root/nodal gates, with changes 0.108–0.236%
against 0.1%. Further mesh investigation and all-field/gust validation remain
requirements; no native pass is added.

The [joint-aerodynamic study](validation/isae-ffwt4-joint-aero-20261107.md)
reproduces the growing local velocity on a fixed folded shape. Independent
Biot–Savart quadrature confirms the finite segment between offset trailing-leg
origins; the literal shared physical index requires zero mutual vortex core.
The documented K/F frozen-matrix option reduces the 419-node peak from
99.5 to 21.4 m/s, but the latest aerodynamic moment change remains **0.155%**,
above 0.1%. A separate frozen 55-node cold equilibrium completes **19 accepted
steps in seven successful jobs**, with zero rejection and rebuilt residual
**5.38e-13**. Its initial root moment differs from native by **0.694%**, versus
**2.737%** with evolving matrices. The historical K/F setting is unauthenticated;
no default, original mesh result, or native pass count changes. Further spatial
refinement and full histories remain required.

The [frozen-matrix 211-node refinement](validation/isae-ffwt4-frozen-211-20261107.md)
now completes **19 accepted steps in 19 successful serial jobs**, with zero
rejection and maximum rebuilt residual **8.05e-13**. Its initial native
moment error is **0.5344%**. The 107/211 pair passes **1/7 mesh checks**;
six changes remain **0.122–0.153%**, above 0.1%. The earlier frozen 55/107
pair's 3/7 result remains recorded; its passing root-moment check did not
persist on refinement. Historical K/F remains unauthenticated, and full
histories remain uncomputed. Further mesh/field verification and gust histories
remain required. Native coverage stays **200/8,000**.

The [source-tree startup implementation](validation/isae-source-tree-production-20261107.md)
now passes **181 focused/regression tests and 29 built-browser checks**. It
uses a scoped algebraic mechanical rank proof, explicitly without a numerical
condition bound; circulation still passes its separate 1e-10 gate. The two
211-node Python startup states are bit-for-bit identical to the prior kernel,
with process times reduced from 42.63/52.75 s to **22.40/23.47 s**. Built-browser
steps take **12.32/12.72 s**, including a complete worker restart between them,
and match Python states to 4.42e-16 on the normalized coordinate scale. The
**419-node case saves its first accepted step in 27.54 s**, with independently
rebuilt residual 3.82e-14. All original physical functions and 138 unchanged
modules are retained; 140 modules were verified in that startup build.
That study stopped after one 419-node step; the subsequent run is recorded below.

The [circulation-finish memory fix](validation/isae-circulation-finish-memory-20261107.md)
now completes the **419-node frozen Flare20 equilibrium in 19 serial jobs**,
with zero rejected load steps and rebuilt residual **9.77e-14**. The old run's
step-16 allocation failure is retained; the new kernel matches its first 15
saved states bit for bit and completes under the same 512 MiB cap. Fifty Python
checks pass. The completed 211-node state reconstructs with all 45,775 compared
numeric outputs unchanged. Independent auditing verifies every new saved boundary.
The 211/419-node pair passes **0/7 original mesh checks**: changes are
**0.142–0.256%** against 0.1%. Sided force/moment components pass **11/18**;
failed components change **0.112–0.664%**, each with its own beam/component scale.
The initial root moment differs from the archive by **0.3842%**, but this is
not a full gust-history match. Native progress remains **200/8,000**.
Seven WASM and 19 built-browser checks also pass. Browser steps through the
former failure and after a full worker reload take 23.59/21.67 s after readiness,
matching Python states to 3.07e-16 on the normalized coordinate scale. Next
separate flow/load quadrature from structural mesh effects near the folding joints;
no full field accuracy, native K/F default or attachment semantics is established.

The [FFWT-4 full-history refinement](validation/isae-ffwt4-spatial-time-20261106.md)
has reached 1,162/1,592 steps on 159 nodes through 2.164225 s. All 146/146 reached
native values pass, with maximum error 0.893% at the unchanged 5% allowance;
zero integration steps were rejected, and all residuals remain below 1e-8.
The cold start, exact original gust, archived equations and BDF predecessors
are independently checked. Complete histories on 159/287 nodes and the
planned time pair on 287 nodes are still required before claiming full-window
spatial/time accuracy. Root moment, gust increment, displacement and rotation
retain 0.1% numerical gates. Other state fields, histories and shared suite
registration remain open. These repeated targets do not increase the tracked
200/1,600 fixed-subset coverage (200/8,000 across the full archive).

The corresponding saved-field comparator now has 59 passing focused checks,
including 23 field tests and 15 original-output-time gate tests. Both original
200-time root gates and denser shared-time gates must pass independently;
an off-output-time peak cannot relax the original normalization. It requires
complete histories, checks
physical-input consistency and shared nodal states at restarts, and compares
all shared times/material nodes while bounding memory to individual segments.
Its readiness does not establish the still-uncomputed full-history accuracy.
The prescribed gust is independently confirmed zero at all 535 saved
aerodynamic sample positions at step 842; the remaining unforced response is still required.

The [FFWT-4 initial spatial study](validation/isae-ffwt4-spatial-20261106.md)
passes three 0.1% mesh gates between 159/287 nodes: initial root moment,
nodal displacement and small rotation vectors. All mandatory stations are
checked independently; three new cold solves have rebuilt residuals below
1e-8, and ten audit tests pass. This is t=0 evidence only. The original
63-node initial moment differs by 0.221% from the finest, so the full gust
history still needs spatial refinement and time checks on the refined mesh.
Circulation/element fields, other histories, hinged cases and shared suite
registration remain required. No physical parameter is fitted and no new
native coverage is inferred from repeated initial values.

The [exact operator-reuse change](validation/isae-ffwt4-operator-cache-20261106.md)
preserves all saved outputs in a four-step FFWT-4 continuation while avoiding
640 repeated operator constructions. Array-layout changes also invalidate
the underlying pair cache. This is bounded regression evidence, not a new
native comparison or proof of full-history speed or numerical convergence.

The [progress dashboard](validation/isae-progress.md) records UTC changes to
comparison fractions, scopes and thresholds and generates per-case/overall
plots. Counts remain qualified native-reference scopes, not whole-family
certification. The [FFWT-4 eighth-step study](validation/isae-ffwt4-eighth-step-20261106.md)
passes the same 200 native targets through 2.9651 s, or 200/1,600 fixed-history
values. Median/max error is 0.523%/0.681%; all 1,592 steps converge without
rejection. Its complete ancestry, snapshots and source hashes are audited.
Both strict root-moment accuracy gates now pass for the latest adjacent pair:
the increment changes 0.0373% and total moment 0.0132%, below 0.1%. The original
200 ticks and all 797 common quarter-grid ticks pass. This resolves the prior
0.113% increment failure without certifying the original coarse time step,
which still fails against the fine run. Spatial/all-state accuracy, other
fixed histories, hinged models and shared registration remain required. The
same archived kernel is used across grids; physical inputs and equations are
unchanged. Repeated targets do not increase native coverage.

The [FFWT-3 source/attachment audit](validation/isae-ffwt3-sources-20261106.md)
completes original-history registration, not physical validation: 0/36,462
required slots, including 35,256 retained native values and 1,206 missing ones.
All six models have out-of-range joint attachments, confirmed on two grids.
The adapter retains source/time-grid mismatches and forbids invented outputs
or silent coordinate repairs. Shared execution and independent accounting now
complete; native attachment behavior or authenticated historical inputs must
be resolved before claiming a comparison. The 5% reference allowance does not
waive these source requirements. Production equations are unchanged.

The [FFWT-2 full-startup/aerodynamic study](validation/isae-ffwt2-history-refinement-20261106.md)
adds 408 converged steps at dt=.005 and eight independent vortex-reference
tests. All 27 instantaneous aerodynamic snapshot checks pass, with sampled
section Cl below stall. Native agreement remains 5/25 computed and 5/4,005
required at 5%; no zero-pass acceleration or angle channel is fixed. Only 1/5
full-history time-refinement gates passes. Local time accuracy, full-history
accuracy, reference agreement and historical setup remain distinct claims.
Finer full-history time steps, mesh convergence, later native rows, original
startup/settings and shared registration remain required. No physical parameter
or production equation was changed. Other zero-coverage families remain in scope;
FFWT-3 has retained model/driver/output files suitable for the next adapter audit.

The [FFWT-2 independent mechanics/refinement study](validation/isae-ffwt2-mechanics-20261106.md)
adds a rigid-mechanism reference with seven tests, checks all 204 saved jig-start
states, and computes four local time grids with 120 accepted steps. The finest
pair passes all five local 0.1% accuracy gates; original coarse failures remain.
Its native score stays 5/25 computed, or 5/4,005 total. Neither this balance
audit nor short-window refinement certifies the preceding trajectory or aero
loads. Full-history temporal/spatial convergence, native startup/settings,
remaining table rows/configurations and shared registration are still required.
No physical input or production equation is changed to obtain a match.

The [FFWT-2 startup audit](validation/isae-ffwt2-startup-20261106.md) verifies
sensor-angle conversion and reproduces the original script's supported
time-command restart as a separate declared scope. Its jig-start comparison
passes 5/25 computed values at 5% (5/4,005 full table), with acceleration and
both tip angles still at zero passes. The earlier equilibrium-start 10/25 is
retained separately. All 12 assessment tests and accepted-state residual gates
pass, but neither startup nor restart fixes the physical comparison. An
independent dynamics audit, historical initial-state/constraint recovery,
temporal/spatial refinement, full histories and shared registration remain
required. No production equations or whole-family validation claims change.

The [FFWT-2 time-matrix follow-up](validation/isae-ffwt2-time-tangent-20261106.md)
adds exact mechanical columns to the full Newton fallback and advances the
saved trajectory to 2.04 s. Strict parity holds across 49,272 numerical fields;
all 11 focused Python tests pass. The first native window has 10/25 matches at
5% (10/4,005 full selected scope). Acceleration and both tip sensors still have
zero matches. Full histories, historical C-preset/startup recovery, temporal and
spatial refinement, independent trajectory audit and shared family registration
remain required. This does not complete nonlinear folding-tip response validation.

The [AE-5 original-source ledger](validation/isae-ae5-sources-20261105.md) now
preserves 587 modal/boundary targets as explicitly blocked. Original model and
operating-point correspondence remain unproven; source stiffness differs from
the report. A fresh unchanged-source modal diagnostic passes all 16 full-matrix
checks, and 39 AE-5/P-2 regression tests pass. This does not establish native
agreement or flutter boundaries. Eight families still lack shared adapters.

The [P-2 declared input reconstruction](validation/isae-p2-recovery-20261105.md)
now covers all 24 archived CT/efficiency curves: 312/312 scalar comparisons pass
5%, with maximum error 0.633%. Primary power rows are pinned and the original
measurement-calibration procedure is reconstructed without using model targets.
The exact upstream fitting program/driver remains absent; the polynomial curves
include the report authors' variable-CdA extension. Independent power prediction,
wakes, aircraft coupling, browser and whole-family validation are not established
by these isolated engine comparisons. AE-5's later source registration remains blocked.

The [AE-6 density correction](validation/isae-ae6-density-20261105.md) fixes the
comparison adapter's cross-model air-density override and enforces source-bound
atmosphere, indicated speed and dynamic pressure. Eight fresh jobs cover all five
runnable original configurations, passing 116/118 computed components at 5%.
Only Weight7a's lowest frequency fails. The selected scope is 116/132 including
the malformed Weight0 blocker. All 41 focused tests and the independent full-matrix
audit pass. The six-table registration remains complete, while mesh convergence,
complete sweeps, other positions, historical setup, native identity and flutter
onsets remain required. Earlier wrong-density evidence is preserved separately.
Production equations and the built application are unchanged. Six earlier
[frame checks](validation/isae-ae4-frame-constraints-20261105.md) retain their
nonzero-spectrum result; wall-contact frame-motion support remains incomplete.

The [AE-4 spectrum audit](validation/isae-ae4-spectrum-20261105.md) verifies the
four selected roots against an independent full 797-state matrix solve. Fresh
102 m/s comparisons pass 4/4; both 103 m/s meshes remain unmatched. Divergent
tiny roots in two original exports and unresolved global constraints require
further investigation; the candidate slow branch is also not mesh converged.
The shared count is 11/1,200 so far and the accumulated sampled count is 67/88.
This narrows the discrepancy without changing physics, targets or pass rules.

The [AE-4 shared registration](validation/isae-ae4-suite-20261105.md) accounts
for all eighteen original text modal exports and the complete declared
undeformed alpha-zero sweep. Three fresh shared jobs verify numerical execution,
retaining the known damping failure and eight unmatched 103 m/s components.
The independent summary and 207 focused tests pass. This closes the missing
shared modal adapter, while full sweep execution, other branches, sensor/time
histories, historical setup and native mode identity remain open.

The [AE-4 later selected branches](validation/isae-ae4-later-20261105.md) add
31/32 matches at four speeds on two meshes, bringing the conditional total to
63/68 at 5%. A real-pole classification error in the comparison helper is fixed
with independent full-pencil certificates, retaining every raw root and target.
Five damping failures remain; these samples do not complete the original sweep,
native real-pole mapping or the modal requirement. Shared registration is now
recorded above.

The [AE-4 first flutter bracket](validation/isae-ae4-crossing-20261105.md) now
agrees on two meshes at the declared 69–70 m/s commands. Four additional modal
points pass 20/24 native components, with critical damping differences retained.
Difference-step refinement and the unstable offline worker pass. This verifies
a conditional first-crossing scope; it does not complete the flutter sweep,
historical setup recovery or the full modal requirement.

The [2026-11-05 reassessment](validation/isae-five-percent-20261105.md) applies
the user-approved 5% allowance to native-reference comparisons without changing
equation, numerical or mesh requirements. Saved zero-pass scopes gain qualified
matches, and 26 new SA-15 declared-setup solves yield 84/182 comparisons within
allowance. The [SA-15 declared scope](validation/isae-sa15-suite-20261105.md) is
now in the shared runner, with all 312 numerical checks passing and independent
summary verification. The archived settings dump remains undecoded. AE-4 now computes
both 41- and 81-element wall-mounted modal anchors using geometry-bounded
coordinate probes, retaining full constraint rows and physical clearance.
Neither result closes a whole-family or full ASWING feature requirement.

The [stationary-wall unsteady extension](validation/isae-ae4-wall-modes-20261105.md)
supports moving interior sections, circulation rates and complete modal
derivatives at a declared stationary solid-wall clamp. Explicit full-mirror
checks support the existing published image/apparent-mass formulas. The first
AE-4 anchor is close under declared conditions, but historical setup, spatial
refinement, full flutter coverage and native validation remain open. Broader
wall gust, aircraft-motion and nonlinear-time workflows are not established;
the ground-image requirement remains Partial. All 67 Python checks and ten
offline browser-worker gates pass, with 1,281,454 numerical comparisons.

The [selective custom-sensor optimization](validation/selective-custom-sensors-20261105.md)
removes unconsumed section reporting while retaining the complete equations,
Newton/continuation and tangent/rank/smoothness checks. All 63 Python tests and
11 offline browser gates pass. The original nominal20 AE-2 custom solve takes
26.8 s versus 103.6 s previously, with all 6,269 compared values exactly
unchanged; nominal40 now completes in 51.3 s. The near-17.9 m/s sensor-coordinate
point has two computed meshes, with observed output changes up to 0.171%.
Further refinement and the archived 17 m/s discrepancy remain unresolved.
No native ISAE score or broad requirement is marked complete.

The [ordinary wall-root custom-trim fix](validation/wall-root-custom-trim-20261105.md)
retains full physical residual, rank and smoothness checks while allowing the
existing bounded derivative extension at a declared solid-wall mount. Four new
independent-speed regressions, 43 existing tests and an actual offline UI solve
pass. Weighted-allocation/feedback wall workflows and refined AE-2 continuation
remain outside this verification. No broad requirement or native ISAE family is
declared complete.

The [AE-2 warm-start correction](validation/isae-ae2-continuation-20261105.md)
uses boundary-aware full Jacobians and existing sparse beam elimination for
eligible source-coupled saved states, retaining physical clearance, residual and
rank gates. All 104 Python tests and the offline browser comparison pass.
Conditional positive-branch results at 18–20 m/s are within 2.724% of archived
ASWING on both meshes; 17 m/s remains unresolved. This improves implementation
and reference agreement without completing any broad requirement or changing
native acceptance thresholds.

The [source steady-derivative extension](validation/source-steady-derivatives-20261105.md)
supports fixed-acceleration and free-flight responses through the moving source
airflow equations, including steady feedback. Independent rotating-bar,
controller, rigid-body and lifting-wing checks pass, together with 122 Python
checks, 29 JavaScript checks, the offline UI/project workflow and 2,749
native/browser numerical comparisons. Source section plots and CSV identify
constitutive averages. Newton factorization reuse, native ASWING agreement and
broad completion remain open; all 42 ISAE rows are unchanged.

The [source custom-trim extension](validation/source-custom-trim-20261105.md)
adds custom sensor equations and weighted redundant-control allocation to both
source steady policies. It fixes a target/report strain-sampling mismatch: an
independent 10 N target previously produced 9.634 N when the old guard alone was
bypassed. All 152 Python checks, 25 JavaScript checks, the offline project/launch
workflow and 8,962 native/browser numerical comparisons pass. Optimizer work
counts differ; the smoothness diagnostic passes its original gate independently.
Exact ASWING weighting, native agreement and broad completion remain open.

The [source steady-controller extension](validation/source-steady-feedback-20261105.md)
solves feedback actuators, integral states and ordinary command trim with the
source airflow equations. Independent mechanics/circulation checks, an elastic
climbing turn with all 16 targets, saved-state launch, 139 Python checks and 40
JavaScript checks pass. The offline browser workflow and 17,419 native/browser
numeric comparisons pass. Native ASWING
agreement remains open; broad completion requirements remain Partial.

The [moving source-airflow trim](validation/source-moving-trim-20261104.md)
now supports prescribed and solved frame rates and accelerations using the
existing full moving equations. All 126 selected Python checks, 39 JavaScript
checks and the offline trim/project/time-launch workflow pass. Native ASWING
agreement and the broader completion requirements remain open.

The [source body-flow derivative correction](validation/source-body-flow-columns-20261104.md)
aligns analytical section-load transfer with the full source residual. Twelve
focused Python checks cover complete circulation columns, assembled dynamic
matrix directions and existing generic/source regressions. Two offline WASM
cases and 1,136 native/browser numeric comparisons pass. Native reference
agreement and all broad Partial requirements remain open.

The [analytical source time-matrix columns](validation/source-time-mechanical-columns-20261104.md)
reuse exact internal-load and reaction derivatives while retaining complete
geometry, motion, aerodynamic and controller equations and the original rank
and accuracy gates. All 33 selected Python checks, including the full free-frame
refinement, pass, together with one offline UI workflow and 17,608 native/browser
numeric comparisons.
The measured short request is 22.47% faster, with identical complete matrices
and physical output. Dense rank construction, native ASWING agreement and all
broad Partial requirements remain open.

The [feedback measurement optimization](validation/source-feedback-measurements-20261104.md)
retains complete equations and rank/accuracy gates while avoiding unused section
recovery during controller evaluation. All 31 selected native cases, one actual
offline UI workflow and 17,608 native/browser numeric comparisons pass. The
original full free-frame feedback refinement now completes and passes its
unchanged gates. This closes that implementation regression; native ASWING
agreement and all broad Partial requirements remain open.

The [source-airflow trim and time launch](validation/source-airflow-trim-20261104.md)
adds ordinary mounted trim to the moving-airflow operator and launches its saved
physical state directly into time response. Solved controls and loads are retained;
steady targets are released and the full initial dynamic residual is checked.
Analytical transient refinement, loaded-wing reuse, offline UI execution and
project restoration pass. Its formerly unfinished free-frame feedback refinement
passes in the follow-up above. Native ASWING agreement and the remaining
full-scope requirements stay open.

The [source-equation steady trim](validation/source-steady-trim-20261104.md)
extends the mounted source structural operator to ordinary flow, pose, flap
and engine operating targets. Full coupled residual checks, analytical engine
loading, prescribed-state recovery, offline browser execution and saved-project
restoration pass. Frame rates/accelerations remain prescribed at zero; custom
equations, minimum-control allocation and dynamic launches remain unsupported
for this operator. No broad requirement or native ISAE family becomes complete.

The [ST-4 full-residual modal check](validation/isae-st4-directional-actions-20261104.md)
finds differentiation errors too small to explain the three examined sensitive
mode discrepancies. It adds reusable directional checks and four formula tests,
using 146 residual evaluations and no repeated eigenvalue solve. Spatial
refinement, native settings and all broad completion requirements remain open.

The [ST-3 additional comparisons](validation/isae-st3-additional-20261104.md)
match 8/9 conditional native frequency-set values across all three layups
using exact still-air dynamics. All 9 mesh checks and 144 reported eigenvector
residual checks pass. The same-name static test pair is contradicted by its
torsional response. The [shared-suite integration](validation/isae-st3-suite-integration-20261104.md)
now registers six modal jobs covering nine distinct workbook frequencies.
All saved results are preserved, one fresh worker reproduces its frequencies
exactly, and 182 focused tests pass. Historical settings, modal labels and the
uncoupled first-frequency discrepancy remain open. Production code, the static baseline and broad Partial requirements
are unchanged.

The [ST-5 forward-only refinement](validation/isae-st5-forward-refinement-20261104.md)
passes 56/56 final mesh checks, completing passing final pairs for all 16
registered static cases (224/224 measures). Ten serial solves and fresh residual
checks pass. Strict native differences, historical settings and reaction display
remain unresolved. Production code, registered scores and broad Partial
requirements are unchanged; remaining ST-3 coverage is next.

The [ST-5 roller refinement](validation/isae-st5-roller-refinement-20261104.md)
now passes 56/56 mesh checks; strict native differences remain. Eight serial
solves and fresh residual checks pass, with exact baseline replay. The
[remaining-source audit](validation/isae-st5-source-review-20261104.md) finds
three unpaired static exports and no usable native modal target. Forward-only
refinement remains open. Production code, registered native scores and all
broad Partial requirements are unchanged.

The [ST-4 gravity diagnostic](validation/isae-st4-gravity-diagnostic-20261104.md)
tests zero and toward-tip axial gravity at two sensitive speeds. Neither resolves
the archived differences; all 64 independent equation checks pass. The targeted
lift/lag/apparent-mass and local-Cm/wake-core audit identifies no new missing term.
Production code, native scores, mesh gates and broad Partial requirements remain unchanged.

The [ST-4 modal adjoint optimization](validation/isae-st4-modal-adjoint-reuse-20261104.md)
reuses checked simple conjugate left vectors for real full pencils. The measured
160-interval case uses 12 sparse factors instead of 17; matrices, roots, right
vectors and physical outputs are identical. All 33 regression tests and the
offline browser/save-reopen check pass. Native validation gaps, acceptance
thresholds and all broad Partial requirements remain unchanged.

The [ST-4 critical-region refinement](validation/isae-st4-critical-refinement-20261104.md)
adds two 160-interval full API solves and separate independent mesh refinements.
Lowest-frequency native error remains 43.10% at 120.5; the 139.5 slow root still
has the opposite sign from the archived branch. Final independent mesh checks
pass 52/52, but production refinement passes 24/26 and remains incomplete.
Releasing an unused reference LU fixes the observed memory failure; all 16 replayed
roots/vectors are identical and four formula tests pass. Production kernels,
registered native-family scores and all broad Partial requirements are unchanged.

The [ST-4 41-speed comparison](validation/isae-st4-speed-sweep-20261104.md)
adds 40 independent reference solves and six full API anchors to the retained
U=120 cases. Both methods predict the tracked slow structural branch changing
sign between 139 and 139.5; archived ASWING is still negative at 139.5 and omits
that branch at 140. Higher-frequency errors are 0.106% median at the
full anchors; near-critical low-frequency error reaches 43.0%. All numerical
residual checks pass, but new points need individual mesh refinement and native
startup remains unauthenticated. Family scores, production kernels and all broad
Partial requirements remain unchanged.

The [independent ST-4 flowing-air reference](validation/isae-st4-flow-reference-20261104.md)
agrees with the current 128-interval pilot within 0.1% in all 12 tracked pole
components, with lowest-frequency difference 0.014% and shape MAC above 0.9999996.
Separate structural/aerodynamic refinement passes 12/12 in each direction;
112 original-equation eigenvector checks and four independent formula tests pass.
Both methods retain the roughly 11.5% archived lowest-frequency discrepancy.
This supports the audited linear equations at one condition, not native-family
validation. Production kernels and all broad Partial requirements are unchanged.

The [ST-4 finer spatial study](validation/isae-st4-spatial-convergence-20261103.md)
passes all 12/12 tracked component mesh checks at 96→128 cosine intervals;
the lowest frequency still differs from archived ASWING by 11.51%, with only
1/12 strict scalar matches. Full-pencil modal matrices now stay sparse through
scaling, iteration and vector checks, removing the observed allocation failure
without changing the saved physical eigenvalues. All 29 selected regression
tests and offline browser/save-reopen checks pass. Dense recovery/export remains
available. Native family counts and all broad Partial requirements are unchanged.

The [ST-4 Fourier assembly improvement](validation/isae-st4-fourier-assembly-20261103.md)
reduces the original 64-interval run from 120.16 to 93.16 seconds while preserving
the full matrices and poles exactly. All 25 selected regression cases and the
offline Fourier browser replay pass. Native validation counts, physical equations
and acceptance gates are unchanged; all broad requirements remain partial.

The [ST-4 circulation/spacing diagnostic](validation/isae-st4-airflow-discretization-20261103.md)
adds six native cases with unchanged physics. Lowest-frequency error at 64 intervals
falls from 66.49% uniform to 11.37% cosine and
4.23% modified-cosine. Fourier matrices reproduce the paper's projection
to about 1e-15; 192 new eigenvector checks pass. Spatial convergence, local-flow
defects and native-reference differences remain; no broad requirement is complete.
This study changes validation evidence only; the prior tested application remains current.

The [ST-4 airflow refinement and modal optimization](validation/isae-st4-airflow-refinement-20261103.md)
adds 64-interval evidence while retaining reference and mesh failures.
The unchanged 32-interval cold solve falls from 101.98 to 29.54 seconds
using existing complete structured derivatives; matrix/root parity, 35 selected
regression checks and the actual offline browser/save-reopen workflow pass.
The lowest-frequency error remains 66.49%, and the latest mesh comparison
passes only 5/12. No family or broad requirement is declared complete.

The [ST-4 zero-area airflow correction](validation/isae-st4-zero-area-airflow-20261103.md)
allows dimensional loads and modes for unchanged zero-Sref inputs; undefined
coefficients remain unavailable. One original flowing-air pilot completes in
53.95 s with 32/32 independent full-pencil residual checks. Archived-root
agreement, mesh refinement and historical settings remain unresolved. No physical
load equation or accuracy threshold was changed; broad requirements remain partial.

The [original ST-5 elliptical-loading study](validation/isae-st5-elliptical-20261103.md)
extends the shared runner to 16 ST-5 static cases representing all 24 complete
model/driver/output triples. All 16 new solves and final 56/56 mesh checks pass;
strict archived-output differences and unpaired/modal sources remain open.
This adds bounded structural coverage without completing any broad requirement.

Target: an open source, physically faithful implementation of **all documented
ASWING functionality**, `.asw` file compatibility, and a JavaScript/WebAssembly web
application that runs locally in the browser, comparable in workflow to VibeLattice.
The current JavaScript worker loads the numerical kernel into self-hosted Pyodide
WebAssembly; aircraft analyses require no server-side computation.
This ledger does not reduce that target to the features
already implemented. A passing component test does not establish aircraft-level
or ASWING numerical parity.

The [analytical column verification](validation/isae-st6-column-supplement-20261103.md)
adds 19 passing source-modal cases across the Euler buckling transition, full
displacement/rotation and independent matrix checks, and two converged offline
browser cases with saved-project restoration. It validates this clamped/free
point-mass benchmark; it does not establish native ST-6 agreement, fixed-fixed
fixture reproduction or general post-buckling behavior. No physical equation
or broad completion state changes.

The [shared ST-5 suite registration](validation/isae-st5-suite-20261103.md)
made the first 12 tested snapshots repeatable through the ordinary runner. All 409
contract/runner tests pass, with exact output parity on two fresh three-grid
jobs. This adds regression coverage; strict native-reference and refinement
failures remain and no broad requirement is marked complete.

The [original ST-5 forward-only comparisons](validation/isae-st5-forward-20261103.md)
add four distinct unchanged model/driver/output pairs and 12 successful structural
solves. Strict archived-output and refinement failures remain; this extends
original-case coverage without changing any broad completion state.

The [original ST-5 roller comparisons](validation/isae-st5-roller-20261103.md)
add four unchanged ASWING snapshots on three grids, documented type-2 joint
mechanics, all output columns and one offline browser/save-restore check.
They add original-case coverage; remaining mesh and archived-output failures
are retained. No broad completion state or production equation changes.

Current work prioritizes regression comparisons across **all 41 archived ISAE
families**. Every original model, candidate output and runnable comparison must
be accounted for. Missing adapters, unsupported features, rejected inputs,
unknown operating settings and failed solves remain explicit unfinished work.
An entire case can pass only after its required archived rows and outputs are
covered against stated numerical criteria; parsing, synthetic checks and a
selected-channel match do not establish that pass. Experimental agreement is
not an acceptance requirement.
The [executable suite workflow](validation/isae-suite.md) and
[41-family backlog](validation/isae-suite-backlog.md) track this priority,
including remaining outputs and variants within registered families.
The [current combined results](validation/isae-suite-current.md) cover declared
scopes in 18 families and explicitly retain the other 23 as missing adapters.
The 2,443 recorded jobs include unsupported scopes and failures; they do not
constitute 2,443 passed cases or complete family coverage. Current FFWT startup
and ST-4 mesh regressions remain open priority work.

The [source moving-frame time extension](validation/source-moving-time.json)
adds literal Euler-angle BDF integration, same-operator saved launch and binding
checkpoint histories. Independent transient/refinement, momentum, rotation and
restart tests pass, including Radau, adaptive BDF and initial disturbances. The
offline browser matches native states and restores/continues saved histories.
This closes part of the vacuum source-time integration gap; airflow, apparent-fluid inertia,
additional topology and full ASWING time-response parity remain unfinished.
All broad requirements below remain partial.

The [source fuselage extension](validation/source-fuselage.md) adds steady
Eqs.10–12 and unsteady Eq.4 to the source beam operators, including material
damping and owned Euler histories. Static body shoulder loads and moving
body apparent-inertia loads retain conservative wrench transfer. Independent
mechanics, refinement and native/WASM/browser checks are recorded with that
increment. Chart poles, spatial branch cuts, stepped axes and full-aircraft
archived parity remain unfinished. No ISAE passing
count or broad requirement status changes.

The [still-air body extension](validation/body-still-air.md) implements circular
body apparent inertia at exactly zero flow in the source and existing midpoint
operators. Both documented coefficient conventions survive native/browser
requests and saved-state identities. Independent pressure, mass-matrix and
modal-refinement checks pass. Full aircraft reference validation, nonlinear
still-air time response and moving-frame still-air dynamics remain unfinished.

The [published modal algorithm](validation/aswing-modal-integration.md) now
uses the full coupled pencil, reused sparse shifted factors and left inverse
iteration, with explicit exceptional-pole recovery. Fresh UI settings select
this method; saved solver selections remain unchanged. Original ST-4 local
modal requests solve on four meshes and in the offline browser. The extended
64-to-128 mesh pair passes the unchanged frequency gate, while historical
setup and archived-frequency differences remain. Complete finite-spectrum
classification is a separate diagnostic, not a prerequisite in Drela's method.

The [source vacuum modal extension](validation/source-vacuum-modes.md) now
provides a distinct fixed-frame endpoint-average inertia policy, protected
structural matrix assembly, independent complete scalar spectra and offline
browser/project checks. This closes part of the source-dynamics integration
gap. The [material-damping extension](validation/source-material-damping.md)
adds local source rates and complete damped spectra with browser checks.
The [source still-air extension](validation/source-still-air-modes.md) adds
stationary thin-strip apparent inertia with independent complete spectra and
offline browser checks. The [moving-frame vacuum extension](validation/source-moving-vacuum.json)
adds real-mass frame transport and canonical free/mixed acceleration equations,
with independent wrench, full A/M and analytic free-oscillator checks plus an
offline browser solve/save/restore. It explicitly resolves the printed angular
transport omission and makes no historical executable-parity claim. The
[source frequency extension](validation/source-frequency.md) connects these
same fixed/moving vacuum and fixed still-air operators to the full descriptor
response solver, with exact matrix reuse, analytical mechanical checks and
offline browser solve/refine/save/restore coverage. The
[source airflow extension](validation/source-airflow.md) now couples source beam
dynamics to unsteady lifting-line forces for modes, frequency and time response,
with analytical control/pole checks and native/WASM agreement. The
[engine](validation/source-airflow-engines.md) and
[strut/wire](validation/source-struts.md) extensions retain moving-pylon loads
and the declared brace law in this route. Bodies, stepped axes, feedback and
inverse targets remain unsupported. Full-aircraft source Bode validation, pointwise damped strains and archived
modal reproduction remain incomplete; all broad requirements remain partial.
The [nonlinear endpoint fluid-load operator](validation/source-apparent-motion.md)
now supplies the complete thin-strip velocity/rate and acceleration wrench,
verified against analytical limits and a differentiated Earth-frame trajectory.
The active aerodynamic path shares its arithmetic without changing retained
outputs. Source airflow dynamics now uses Glauert aerodynamic sampling alongside
endpoint real inertia; this differs from the stationary endpoint-fluid policy
and retains a distinct numerical identity. General coupled refinement and all
source-model features remain unfinished; no broad requirement is complete.

The [Daedalus mixed-inertia audit](validation/daedalus-mixed-inertia.md) checks
both aircraft/elastic coupling blocks against an independent kinetic-energy
calculation at the saved cruise state. All 816 recorded checks pass, with a
largest normalized matrix-entry difference of 1.40e-11. This closes that bounded
assembly check; the full Bode discrepancy and all completion states remain open.

The [elastic boom–fin study](validation/elastic-fin-feedback.md) adds live
aerodynamic feedback into distributed elastic bending and twist at 1 Hz. All
26 fine-mesh grouped complex response criteria pass, with a worst error of
0.3601% against the independent reference. The portable native regression and
fresh independent reference reproduction pass. This clamped component does not
resolve full-aircraft coupling or the Daedalus Bode discrepancy; all broad and
ISAE completion states remain unchanged.

The [free-frame/hinged-fin study](validation/coupled-fin-response.md) adds twelve
passing coupled component cases and two regressions, with independent mass,
aerodynamic and output checks. Its two corrected adapter failures are retained.
The Daedalus reference mismatch remains open; all broad requirement and ISAE
completion states below remain unchanged.

Public baseline inspected 2026-10-03: user guide 5.97; steady formulation 5.99
(2015); unsteady extension; version notes through 6.02 (2016); extended manual
linked from the September 2025 ASWING page update. The documents have different
versions. No assertion is made about undocumented or privately distributed later
ASWING behavior. The public documents, including their later version additions,
are the implementation specification.

The [primary ST-4 study](validation/st4-primary-study.md) completes conditional
comparisons for 252 vacuum and 252 still-air states against 672 independent
references. It retains 78 before/after observations, including six incomplete
triplets, and compares 72 complete triplets as sorted spectra under an explicit
lowest-three-mode assumption. At 32 intervals the first three air frequencies
are within 0.4712% of the continuous model, while the mean absolute experimental
discrepancy is 9.264–9.296% and the maximum is 54.867%. Air density is assumed,
pylon/fixture properties remain uncertain, and higher sixth/seventh modes mix.
The 176 selected native checks, one JavaScript check, three WASM replays and
three fresh offline browser checks pass. Coverage is 17 partial families and
24 pending, none fully validated; all 40 broad requirements remain Partial.

The [name compatibility correction](validation/asw-name-comments.json) preserves
embedded `#` and `%` in aircraft/beam names across parsing, editing, export and
syntax highlighting. Native, JavaScript and actual WASM controls pass; the
working source is integrated, with the next app build/browser check still
pending. No physical equations, ISAE outcomes or broad completion states change.

Exact-zero-speed still-air modes now use the published thin-strip apparent
inertia at a stationary fixed frame, with explicit density and retained
Earth pose/gravity. The explicit source still-air policy also supports
fixed-frame initial-disturbance spectra through the same matrix operator.
ROM, stability, time launch and general nonlinear zero-flow analyses remain
unsupported for this medium.
Ordinary aerodynamic solving still requires positive airspeed, and historical
studies retain their original source hashes.

Moving-field assembly now uses packed source products on all four original
geometry samples; physical references, refinement and guarded fallbacks remain.
The observed native full-assembly gain is small (0.6–3%); browser end-to-end
speed is not established. See `docs/validation/packed-field-products.json`.
All rows remain Partial.

The local app and source downloads now separate optional raw experiment ZIPs
from code, tests, examples and validation summaries. The raw files and their
SHA-256 catalog remain available, and a compact source checkout rebuilds without
them. See `docs/validation/compact-distribution.json`. This distribution change
does not establish ASWING numerical parity; all rows remain Partial.

Mechanical section outputs now use retained physical C, with independent80-digit
references resolving the weak-stress cancellation issue. The physical same-state
2e-7output target passes; raw noisy references and strict support portability
remain separately documented. See `docs/validation/structural-output-matrix.json`.
All rows remain Partial.

Direct physical internal-load/reaction matrices now remove another 72 DAE48
residual probes, including smooth hinge derivatives. New physical references and
21-frequency validation are in `docs/validation/direct-mechanical-matrices.json`.
All rows remain Partial.

Matching constant B columns now survive a new sweep on the same loaded model,
saving twelve DAE48 input probes. See `docs/validation/input-column-reuse.json`.
All rows remain Partial; cold final-Newton handoff and full C/Q/D are open.

Reaction columns now share the existing mechanical support groups, saving 96
full DAE48 residual probes while preserving all A/M/G entries and checked browser
responses. See `docs/validation/mechanical-column-groups.json`. All rows remain Partial.

Four original field samples now share retained matrix blocks and batched
applications, with exact full DAE matrices and browser responses. All original
physical checks and accuracy thresholds remain. See
`docs/validation/batched-field-matrices.json`. All rows remain Partial.

A retained analytic support-output C matrix now resolves the recorded DAE
support-roll-moment cancellation discrepancy. Independent high-precision support
checks cover all 21 saved frequencies/four inputs. An additional 1e-9 cross-runtime
target remains unmet; its difference follows the unchanged solved states. Complete
C/Q/D and full parity remain open; all rows remain Partial.
See `docs/validation/support-output-matrix.json`.

Grouped raw geometry preparation now reuses affected rows across original field
stencils, with identical full DAE matrices and browser responses. See
`docs/validation/grouped-geometry-stencils.json`. All rows remain Partial.

Vortex receiver matrices now share endpoint/core changes and apply only changed
core columns. Complete DAE operators and browser responses remain exactly equal;
see `docs/validation/shared-vortex-sources.json`. All rows remain Partial.

Volume receiver matrices now share source-change calculations within each geometry
perturbation. Complete DAE operators and browser responses remain exactly equal;
see `docs/validation/shared-volume-sources.json`. All rows remain Partial.

Unchanged lifting-surface geometry now reuses exact owned arrays during matrix
construction. Complete DAE operators and native/browser responses remain exactly
equal; see `docs/validation/lifting-geometry-reuse.json`. All rows remain Partial.

Body and point-object field derivatives now remain available during initial
geometry matrix assembly. Full physical accuracy gates remain unchanged; see
`docs/validation/volume-matrix-reuse.json`. All broad rows remain Partial.

Circulation-rate columns now share exact local mass-matrix probes when their
load and tested-flow supports are disjoint. Full DAE M and browser responses
remain exactly equal; see `docs/validation/circulation-rate-matrix-reuse.json`.
All broad rows remain Partial.

Initial linearization now also retains direct vortex source/receiver matrices.
The original principal-value fallback and all accuracy gates remain; see
`docs/validation/direct-vortex-matrix-reuse.json`. All broad rows remain Partial.

Material-matrix energy checks now reuse exact unchanged inputs across dynamic
outputs. Full DAE outputs remain exactly equal; see
`docs/validation/damping-matrix-reuse.json`. All broad rows remain Partial.

Bode output recovery now retains moving-source derivatives from the A/B probes,
with matching model ownership, bounded storage and complete physical fallback.
Independent refinement checks correct sensitive geometry columns consistently
in A and the output map; stable vortex and moment formulas reduce cancellation.
Full C/Q/D assembly, universal final-Newton reuse and ASWING parity remain open.
See `docs/validation/bode-output-matrix-reuse.json`. All rows remain Partial.

The frozen Bode model now retains exact input influence matrices across its
full frequency sweep and matching repeated runs. Full 21-frequency/four-input
DAE columns, states and outputs remain byte-identical. This leaves C/Q/D output
maps and full final-Newton reuse unfinished. See
`docs/validation/bode-input-influences.json`. All rows remain Partial.

Small beam motion maps now participate in exact bounded reuse; zero local
motion field construction is skipped only with the original rotation-domain
check retained. Full DAE matrices and checked browser responses are unchanged.
See `docs/validation/bode-motion-reuse.json`. All rows remain Partial.

The shared warm-equilibrium tangent now stays sparse through chart conversion
and constraint checking, with a conservative inverse-norm certificate and the
existing full-SVD fallback at the same threshold. Full DAE matrices and checked
browser responses are unchanged. See
`docs/validation/bode-sparse-equilibrium-rank.json`. All rows remain Partial.

Physical vortex transforms and narrow vortex/volume influence matrices now
reuse unchanged entries during derivative construction. Complete A/M values
match the preceding release exactly; this does not complete final-Newton reuse.
See `docs/validation/bode-influence-reuse.json`. All rows remain Partial.

The final corrected-equilibrium stationary block is now shared with Bode for
matching acceleration-load constraints without controllers. Ordinary repeated
Bode runs also reuse the complete live A/M after verifying the physical operator.
These remain scoped improvements: the first cold solve does not yet reuse a
complete last-iteration Newton matrix, and no ASWING parity is claimed. See
`docs/validation/bode-matrix-reuse.json`. All broad rows remain Partial.

The 2026-10-12 Bode audit confirms the descriptor equation and derivative signs,
but not equivalent ASWING setup, discrete equations or Jacobian assembly. The
default fixed-frame DAE case differs from Drela's published aircraft-response
plot; the complete reference operating point and discretization are unknown.
The current implementation shares circulation and complete geometry derivative
assembly and avoids repeated input/output evaluations. The geometry change has
92 distinct native and 51 WebAssembly passes plus three offline browser passes.
Fresh full DAE48 native observations are 721.44 seconds before and
512.55 after, with setup 595.86 versus 378.73 seconds.
The full offline browser case takes 726.29 monotonic seconds
versus 765.11 wall-clock seconds; the clock discrepancy
is retained in the record. These are
shared-host observations; see `docs/validation/bode-geometry.json` for physical
checks, source pins, limitations and rejected prototypes. Complete converged
Newton-Jacobian reuse, fast large-model startup and matched ASWING response
validation remain open. See `docs/STATUS.md` and
`docs/validation/bode-drela-setup-audit.json`.

The Daedalus yaw-response check identifies fixed-frame body-rate zeros as a
constraint of that setup. The interface now explains the constraint and offers
an explicit free-flight action; a saved steady-trim project is supplied. The
[8/16-panel frequency comparison](validation/daedalus-rudder-sweep.json) reuses
the two loaded pencils for 203 frequencies each. All 406 harmonic solves pass
their numerical gates, but the maximum sampled complex mesh change is 23.14%
near 8.90 Hz. The published reference operating point is unidentified and its
magnitude curve differs. This is functional and numerical evidence, not
converged aircraft-response validation. The
[direct derivative check](validation/daedalus-rudder-directional-check.md) passes
six selected state, rate and input directions at both declared step sizes,
without a new trim or linearization. Its scope is one loaded state and the
tested directions. A subsequent [32-panel attempt](validation/daedalus-rudder-refinement.md)
stopped at a moving-field derivative accuracy guard after returning from trim;
no new response curve or convergence result was obtained in that attempt.
The [derivative recovery](validation/daedalus-rudder-field-refinement.md) now
allows six bounded refinement levels with the same accuracy rules. The
identified column resolves and the change passes 29 native and eight
WebAssembly regression cases. The full-model follow-up completes the 32-panel
matrices and three harmonic samples without repeating trim. The subsequent
[three-mesh sweep](validation/daedalus-rudder-mesh-sweep.md) resolves all 203
frequencies on the finer mesh, with a maximum sampled 16-to-32 complex change
of 14.28% near 7.26 Hz. Mesh convergence and matched-reference validation remain
open. All 40 broad rows remain Partial.

The [free-flight local-rate optimization](validation/daedalus-rudder-local-rates.md)
extends grouped local-motion derivatives to canonical free/mixed force and
moment equations. Same-state 32-panel assembly uses 849 residual evaluations
instead of 5,498, with all matrix entries and four yaw responses checked.
Fifteen focused native and eleven WebAssembly cases pass. The local kernel is
updated; this numerical and performance evidence does not change completion
or aircraft-validation classifications.

The [Daedalus speed sensitivity](validation/daedalus-rudder-speed.md) adds a
new 16-panel steady trim at 6.7 m/s and 203 passing harmonic samples. Its
low-frequency magnitude is closer to the drawing, but the near-1 Hz minimum
still differs. The reference operating point and cruise-speed mesh convergence
remain unresolved. The separate [saved-equilibrium progress change](validation/equilibrium-progress.md)
passes 22 native and 12 JavaScript tests and 40 actual WASM assertions across
five cases, with identical callback-on/off states and evaluation counts.
Neither increment changes any broad completion or experimental-validation state.
The [Bode display](validation/bode-log-axes.md) now uses decade/minor grids and
logarithmic magnitude by default, with selectable frequency and angular-response
display units. Saved physical values and CSV remain unchanged; matching plot
conventions does not establish agreement with the reference response.

The [matched cruise-speed refinement](validation/daedalus-rudder-cruise-mesh.md)
completes all 203 responses at 32 panels. The complex mesh change is 0.462% at
1 Hz but reaches 22.87% near 6.65 Hz; the reference minimum and convergence
remain unresolved. The [fixed loaded-shape diagnostic](validation/daedalus-rudder-fixed-shape.md)
retains circulation, inertia and free flight in 109 equations and resolves all
203 points, with an independent 21-check saved-data audit. It demonstrates
elastic-coupling sensitivity in a deliberately constrained model, not a physical
correction or ASWING parity. All broad states remain Partial.

The [near-1 Hz coupling checks](validation/daedalus-rudder-coupling.md) add fresh
full-residual derivative comparisons, a seven-frequency saved-state decomposition,
and a separately declared printed body added-mass coefficient comparison.
The latter changes complex yaw by only 0.037% at 1 Hz. Neither a numerical
consistency check nor the new primary structural-reference lead resolves the
published-response discrepancy or upgrades any requirement status.

The [independent component checks](validation/daedalus-component-checks.md)
verify loaded boom–fin mechanics against a variable-section continuum reference
and twelve idealized wing–fin aerodynamic transfers. The finest structural
mesh has a maximum scaled motion error of 0.0206%. Frozen-load mechanics and
zero-circulation fixed-geometry aerodynamics do not cover the complete loaded
aircraft coupling; the Daedalus discrepancy and all broad Partial states remain.

The [loaded-motion extension](validation/daedalus-loaded-motion.md) passes twelve
nonzero-circulation moving-fin comparisons and fourteen selected Daedalus
responses under two isolated velocity conventions. The latter change complex
yaw at 1 Hz by only 0.068% and 0.308%. This adds independent translational
aerodynamic coverage without resolving the full aircraft discrepancy or changing
production defaults. All broad states remain Partial.

The [loaded rotating-fin extension](validation/daedalus-rotating-motion.md)
passes twelve additional cases including changing normals/span, moving induced
fields, nonzero profile force/couple and physical moment transport. A separate
2,882-check saved audit passes. This checks the declared finite discrete
convention, not full-aircraft agreement, swept-mesh convergence or original
ASWING interpretation. No broad requirement or ISAE coverage state changes.

The [loaded propeller–fin comparison](validation/loaded-jet-coupling.md) adds
nonlinear circulation/inlet/jet feedback with independent moving-engine and
moving-fin references. It retains the initial reference error and a coarse
output-probe failure, then verifies that failed output at two smaller widths.
Twenty-three other cases complete both widths; four durable one-hertz
regressions pass. This component coverage does not establish full-aircraft
agreement or change any broad requirement or ISAE validation state.

A current-source loaded-wing study now audits 34 native case records and three
matched 75% spar oscillatory crossings: 22.0847/22.4500/22.5777 m/s for 8/16/32
requested intervals. These do not reproduce the published 24.58 m/s Case 4 number;
original setup conflicts remain. Exact current-source repeats, differentiation/time-unit
invariance and computed sign brackets are evidence for the numerical study only.
No kernel or physical parameter was changed. See `docs/validation/loaded-flutter.json`.
Three public-API WASM and offline browser replays now preserve the N16 sign bracket
and N32 near-neutral point, matching base values, mode shapes and mobile CSV exports
(`docs/validation/loaded-flutter-portability.json`). Full-spectrum coverage,
shared aerodynamic-convention reconciliation and exact ASWING agreement remain required.
All 40 broad rows remain Partial.

The loaded-wing structural isolation now includes six saved Case 4 configurations
with the actual offsets and exact rigid shear/extension limits. Independent
continuum integration checks six complete tip-wrench responses on three meshes;
the finest worst-column difference is 0.0757%. Independent kinetic-energy checks
of ten motion fields per case agree within 5.35e-12 relative. Equivalent nodal
loads are held fixed, so aerodynamic feedback and a complete loaded modal
operator were outside this isolation study. See `docs/validation/loaded-wing-mechanics.json`.

The independent structural reference now includes distributed real inertia,
all nodal response matrices at five spectral points, and eight locally matched
structural modes. Finest overall matrix differences are below 0.39%; matched
frequencies agree within 0.204%. This remains a frozen-load isolation study.
Weak individual point-load channels are not covered by those matrix-norm bounds;
one near-root error is resolved through local mesh refinement. See
`docs/validation/loaded-wing-dynamics.json`.

The subsequent independent coupled reference checks complete nodal aerodynamic
and gravity operators, apparent kinetic energy, six re-equilibrated continuum
solutions and twelve local coupled poles. Finest selected-pole differences are
below 0.015%. Its independent 75% spar local bracket centers at 22.5763 m/s and
overlaps the production bracket near 22.578 m/s. The published 24.58 m/s remains
unreproduced. Shared aerodynamic conventions, original setup, finer meshes and
complete-spectrum classification remain open; local independent agreement does
not close broad feature or physical-parity requirements. Seven corrupted records
are rejected. See `docs/validation/loaded-aeroelastic-reference.json`.
All 40 broad requirements remain Partial.


The follow-up kinematic-arm sensitivity study changes only force/control motion
arms while retaining virtual influence geometry. Eight selected mode changes
are below 0.078%, and both independently bracketed speed shifts are below
0.02 m/s. This does not account for the approximately 2 m/s published gap;
it does not establish the original ASWING convention or close physical-parity
requirements. See `docs/validation/aero-kinematic-arms.json`.

Saved equilibria now launch one compatible nonrotating Earth-position history,
using a separate version-4 scope. Older velocity scopes keep their original
contracts. The saved deformation and motion remain fixed during initial
completion; independent spring/inertia, Radau refinement and BDF1/BDF2 checks
pass, as do all checkpoint restores. All 130 distinct selected native tests and
62 JavaScript tests pass after correcting test fixtures. The actual offline
browser launch passes independent mechanics. Its retained export reopens unchanged
through the public archive UI, shows the mobile target plot/CSV and continues with
BDF2. Initial browser setup/input/assertion failures remain recorded. No equations, mesh settings or tolerances changed.
Portable evidence checks retained mechanics and source ownership without importing
the solver. Collection is 1,743 tests, not a full-suite pass. Initialization remains
expensive. See `docs/validation/saved-position.md` and
`docs/validation/saved-position.json`;
the full goal remains incomplete and all 40 broad requirements remain Partial.

All three `.asw` downloads linked from Drela's official ASWING page are now
bundled unchanged: Daedalus (`dae.asw`), the ultralight sailplane (`usa.asw`) and
the swept flying wing (`fw.asw`). They appear under **Drela’s ASWING examples**
in the example picker and are included in source/offline downloads. Upstream
attribution and download hashes are retained. All 44 parser/round-trip checks
pass; the production browser imports and saves each original file unchanged at
1440- and 390-pixel widths with external networking blocked. That example addition did not change numerical sources.
See `docs/validation/drela-examples.json`; this is import/display
coverage, not new aircraft solution validation.

The Radau position-history extension is integrated and verified in a 71-module
kernel. Its Earth position/velocity-defect coordinates preserve the full physical
equations, original target samples and replayable accepted stages. Independent
native and packaged-WASM pilot checks cover compatible restarts, method changes,
replacements, cutoff and a three-position/free-rotation refinement case. All 423
selected integration tests passed before the browser exposed a JSON numeric
spelling bug. The metadata-only correction uses exact numerical equality without
changing definition signatures or tolerances; all 80 selected final-source checks
pass, including 13 new transport/tampering cases. All 62 JavaScript tests pass on
unchanged UI sources. The corrected actual offline browser workflow passes Radau
continuation, mobile target/residual plots and CSV, and branching into BDF2; the
original failed attempt remains recorded. Portable evidence checks retained
mechanics and source ownership without importing the solver. The current
collection is 1,727 tests, not a full-suite pass. See
`docs/validation/radau-position.json`. The full ASWING goal remains incomplete
and all 40 broad requirements remain Partial.

The preceding input-transition increment is integrated and verified in a 70-module kernel.
Compatible inverse-history replacements, slope breaks and cutoff retain separate
before/after states without projecting physical motion. Saved history scope v3
permits those transitions; older scopes keep their original contracts. Independent
native spring/controller mechanics, checkpoint replay and isolated packaged-WASM
checks pass. All 139 selected main native tests and all 62 JavaScript tests pass;
1,692 native tests collect, which is not a full-suite pass. The actual offline
browser transition passes mechanics, plot and CSV checks. Its original workflow
remains failed because the test clicked an export button in a hidden mobile tab;
a corrected followup reopens the exact retained result and passes actual
right-state continuation. Both attempts are preserved. Portable evidence verifies
the source hashes and retained mechanics without importing the solver. See
`docs/validation/input-transitions.json`. Broader history combinations, impulsive
events and ASWING/aircraft parity remain unfinished. The full ASWING goal remains
incomplete; all 40 broad requirements remain Partial.

Preceding saved-history increment: smooth cubic Earth-velocity tables now launch from a saved
equilibrium and continue across interior knots. Version-1 checkpoints retain
their original two-knot contract. Independent spring/discrete/continuous checks,
refinement and checkpoint replay pass; 149 distinct current selected native
tests pass after correcting an older clock-shift fixture. Ten relevant JavaScript
tests pass. Collection is 1,663, not a full-suite pass. Actual browser launch
mechanics and a separate offline archive/display/continuation workflow pass; the
original UI-assertion failure remains retained. See
`docs/validation/saved-spline-histories.md`; the full
ASWING goal remains incomplete and all 40 broad requirements remain Partial.

Preceding load-evaluation increment: exact rotation-transfer reuse, empty-source
influence handling and xyz vector operations preserve complete native/WASM
outputs and the default browser export. The 138-case selected native coverage
and final WASM/offline-browser workflows pass; original harness failures remain
recorded. Collection is 1,647, not a full-suite pass. See
`docs/validation/load-reuse-performance.md`; all 40 broad rows remain Partial.

Preceding inverse-history increment: the 69-module kernel adds documented
motion/reference-flow target rows and explicit Earth-vector extensions, cold
initial consistency, BDF position-history coordinates, recorded-step checkpoint
replay, and guarded saved-equilibrium velocity-history launch. The integrated
selection passes 425 distinct native cases after a scalar-fixture correction;
60 JavaScript cases, public native/WASM mechanics and one offline mobile browser
solve/plot/continuation workflow pass. Cold inverse initialization remains slow.
The current collection has 1,645 tests, not a full-suite pass. Arbitrary histories,
events, controller/load changes, companion-file compatibility and ASWING-level
quantitative validation remain open. See `docs/validation/inverse-histories.md`.
No broad requirement is closed; all 40 remain Partial.

Preceding performance increment: the 60-module mounted solver preserves equations,
mesh and tolerances while reducing duplicate tangent work, grouping disjoint
internal-wrench finite differences and removing exact-zero/general-axis overhead.
The selected numerical/progress coverage is 97 distinct tests; 14 independent
complete residual/Jacobian comparisons and both native48 full results match the
original exactly (excluding the evaluation counter). Current collection is
1,334 tests, not a full-suite pass. Browser default solves take 78.213/106.520
seconds versus 115.601 seconds before on a shared host. Full default results
match exactly, and the flexible browser result exactly matches the original
solver in the same WASM runtime, excluding only evaluation counts/provenance.
Actual progress observations pass separately; both browser harness FAILs and
the pre-existing native/WASM near-zero moment discrepancy remain recorded.
See `docs/validation/mounted-performance.md`; all 40 requirements remain Partial.

Preceding integrated correction: bounded original-residual probes reject witnessed
nonsmooth-controller alternatives without retrying past the ambiguity. The
59-module kernel passes 68 selected main tests, 13 actual packaged-WASM public
workflows and one offline browser refusal/unique-saturation workflow. Collection
at that revision was 1,289 tests; no full current-suite pass was claimed. Finite probes do not
certify general branch uniqueness or generalized nonlinear initialization.
See `docs/validation/controller-nonsmooth.md`; all 40 requirements remain Partial.

Preceding integrated correction: controller cold initialization, ordinary BDF,
Radau and accuracy-controlled steps now request the existing accepted-root
centered rank check. Declared integral/custom initial values and nonzero rates
remain owned by the initial state. The actual main checkout passes 39 selected
tests (13 new controller cases plus 26 prior Newton/checkpoint cases); ten
unchanged production tests, four independent mechanics comparisons and eight
actual packaged-WASM workflows also pass, with overlapping coverage. Complete
collection at that revision was 1,260 tests, not a full current-suite pass. A
one-sided clipping family defeated the centered check and remains preserved as
the physical counterexample motivating the later correction above. See `docs/validation/controller-time-rank.md` and
`docs/validation/controller-one-sided.md`. No broad requirement is closed.

Preceding integrated corrections: accepted inverse Newton roots now receive the
requested final local-rank check on both return paths. Checkpoint restoration
checks cached frame inputs against physical velocity, rates, position,
orientation, time and gravity without applying a future command. The integrated
26-case regression, separate 31-/20-case production selections, two combined
native continuation cases and 15 actual packaged-WASM checks pass; overlapping
selections are not counted as unique coverage. The complete preceding baseline
passed 1,221 tests in 73 files and predates these two fixes. Final combined full
regression and browser acceptance are not inferred from that baseline. See
`docs/validation/solver-consistency.md`. General inverse histories remain open.

Preceding integrated correction: exclude only a panel's own physical bound-vortex
self-field from its apparent pitch-rate beam-axis velocity. Independent line
quadrature and quarter-chord continuity checks, plus existing self-influence,
frozen-influence, unsteady and wake-core regressions pass: 64 targeted tests,
including a prescribed-circulation frozen/Mach-0.6/two-beam reference. Eleven
packaged-WASM cases and the loaded offline WebGL browser workflow pass; the new
full 1,221-test native regression passed before the two later solver fixes. The
unloaded browser's first corrected-kernel attempt passed numerical/export checks
but failed its healthy-WebGL-context assertion; the failure remains recorded.
An instrumented follow-up reached a healthy desktop gate but stopped without a
terminal result or mobile checks, under recorded severe memory pressure. The
source-pinned closeout preserves all three historical attempts
(`docs/validation/durrant-unloaded-browser-closeout.md`). Subsequent isolated
tests support the integrated on-demand/no-multisampling viewer change. Its
rebuilt unloaded-wing offline workflow now passes the original numerical,
export and desktop/mobile WebGL gates; the two checked roots match native
within 1.933e-12 per second. See `docs/validation/renderer-fix.md` and
`docs/validation/durrant-unloaded-browser-repaired.json`. The
independent unloaded-wing reference and conditioning study are integrated, with
484 standalone WASM roots checked. Three fresh corrected-kernel native grids
and twelve reference cases reproduce the historical unloaded physical results
exactly, with separate source pins. Loaded flutter and experimental agreement
remain open. See `docs/validation/axis-apparent-rate.md` for the source-pinned
correction evidence.

Preceding completed increment: implicit flap/engine targets during nonlinear
time integration, with local authority/rank checks, forcing, saved launch,
checkpoint continuation and browser persistence/solved-setting outputs. All 140
distinct targeted native tests, six independent native cases, 52 JavaScript tests,
four packaged-WASM replays and two final offline WebGL workflows have passing
evidence. See `docs/validation/time-actuators.md`. General velocity/pose inverse
histories and full ASWING parity remain open.
The successful Newton-correction uniqueness bypass is corrected and validated
as described above. Its original isolated failures and five scalar checks
remain in `docs/validation/newton-rank-review.json`; that historical record
retains its original pre-integration scope.

The preceding stall kernel passed the complete 1,188-test native regression
across 70 terminal file subprocesses with zero skips/failures/errors and audited
sources. The subsequent inverse time-actuator kernel passed all 1,216 tests in
71 files with zero failures, errors or skips and audited source/terminal evidence
in `docs/validation/native-regression-inverse-20261009.json`. This predates the
apparent-rate correction. Its complete 1,221-test regression is recorded in
`docs/validation/native-regression-apparent-rate-20261010.json` and predates the
two later solver-consistency fixes. Earlier baseline and interrupted runs retain
their original scopes. All 40 broad
requirements remain Partial; full ASWING/aircraft parity is unproven.

Preceding completed increment: optional physical temporal-discrepancy control, BDF midpoint
checkpoint history and checked/fixed browser continuation. All 113 distinct
targeted native tests, ten independent native cases, six packaged-WASM cases,
24 JavaScript checks and ten final offline browser workflows have passing
evidence. Failed/interrupted original runs are retained. This local indicator
is an OpenSwing extension, not a global error bound or ASWING convention.
See `docs/validation/time-accuracy.md`; all broad requirements remain Partial.

Preceding completed increment: physical ROM output selection, exact algebraic-rate zeros,
nine independent spring/finite-wing references, five packaged-WASM replays and
five offline browser workflows. All 86 targeted native checks and 27 JavaScript
checks have passing evidence; retained failures are documented. See
`docs/validation/rom-outputs.md`. Full ASWING/aircraft parity remains open.

Preceding increment: finite-frequency modes at decreasing positive airspeed,
with 20 native cases, independent still-air mechanics, six packaged-WASM
replays and a corrected offline browser workflow for both Durrant wings.
Three-mesh frequency/shape convergence and tangent/search/time-unit checks
pass. Air inertia remains as aerodynamic damping and normalized circulation
vanish. That historical study did not cover exact zero speed; the later ST-4
study checks a separate fixed-frame still-air modal path. The slow aerodynamic
spectrum, nonlinear rest launch, original ASWING conventions and experimental
flutter remain unresolved.
See `docs/validation/durrant-low-speed.md`; all broad rows remain Partial.

Preceding increment: a source-audited reconstruction of Durrant's two wings, with
16 native cases and an independent energy-based beam reference. Three-mesh
frequency/shape convergence, tangent/search checks and source/setup sensitivities
are recorded. The appendix differs materially from the main tables; zero-speed
air-mass settings and experimental apparatus remain uncertain. Four final
packaged-WASM replays (36 positive roots) and one offline browser workflow with
both wings pass. Retained failures and exact outcomes are in
`docs/validation/durrant-structure.md` and its checks record.
No full ASWING or flutter validation claim is made; all broad rows remain Partial.

Preceding increment: complex section cm, normal aerodynamic/inertial density
and elastic incidence in modal, harmonic and initial-spectrum output, with
base-validity masks, physical units and browser plots/CSV. The 13-case native
and packaged-WASM studies, 85 distinct targeted native checks, 37 JavaScript
checks and three distinct offline browser workflows pass across the recorded
runs and corrections. The residual and dynamic matrices are unchanged.
See `docs/validation/dynamic-section-outputs.md` for exact retained outcomes.
Original ASWING sampling, section ROM channels and broader validation remain.

Preceding increment: documented derived section cm, f_aero, f_reac and da_eff
outputs, with normal-load decomposition, explicit current-length normalization,
raw radian/displayed-degree conversion, time envelopes, CSV and archive gaps.
The 14-case independent reference checks 608 scalar values; the packaged-WASM
replay compares 560 recorded values. All 57 targeted native and 24 JavaScript
checks pass, along with four offline browser workflows. The release audit compares
the final bundles with the tested sources. Exact original-ASWING sampling and
modal/harmonic displays were still open in that increment; see
`docs/validation/section-outputs.md`. The unresolved K/C=2 derivative mapping is
recorded in `docs/validation/derivative-axes-research.md`.

Preceding increment: lifting force-point velocity, normal speed and Mach diagnostics,
with body coordinates, maximum location, detailed subsonic rejections, browser
plots/time envelopes and CSV/archive support. An independent prescribed-circulation
closed form reproduces swept-line tip growth across five meshes; this is field
verification, not a converged operating-point or experimental validation. All 104
historical computed SA-2 results retain their 4,784 compared values exactly and
all ten rejections remain. The 17-case native and packaged-WASM field studies,
78 distinct targeted native checks across runs, 23 JavaScript checks and five
distinct browser workflows pass. Exact outcomes and retained initial failures
are in `docs/validation/section-airflow.md` and its checks record. No physical
equations or thresholds changed. The release audit checks the tested files
against the final source and offline bundles.

Preceding increment: archived SA-2 swept-wing comparison and source audit. The unchanged
input has 35.26546-degree sweep, differing chord and tip geometry from the primary
45-degree experiment; a repository zero drag replaces a missing primary datum.
Pressure-only and total-force comparisons are separated. The study records 104
computed and ten rejected cases, with independent tip-velocity quadrature,
30 WASM replays and an offline browser workflow. Fine-mesh local-Mach rejections
prevent a full-range convergence claim. No production kernel changes. See
`docs/validation/sa2.md`; these findings expand the remaining validation work.

Preceding increment: K/F frozen aerodynamic influences. The 11-case independent native/WASM
study passed 516 physical comparisons; targeted native coverage is 163 passing
checks across the original batch and corrected fixture check. All 45 JavaScript
checks and ten offline browser workflows passed. See
`docs/validation/frozen-influences.md` for exact outcomes and scope.

Preceding increment: time-history distribution overlays, signed sampled extrema
with snapshot/time/forcing-side provenance, and all-state distribution CSV in
the loading and structure tabs. All 45 JavaScript checks and ten browser
regressions passed; both analytical spring grids passed, and the dedicated
history workflow passed on provenance-checked replay after correcting a
roundoff-sensitive test assertion. See `docs/validation/distribution-history.md`.
No numerical kernel changes.

Preceding increment: computed-solution archives in version-2 browser projects,
separate from editable cases. Records retain full requests/results, ROM/sweep/
flow/Bode data, selectors, checksums and numerical-source/runtime provenance.
Time continuation preserves the recorded origin of retained snapshot ranges.
The final verification is recorded in the latest STATUS entry and
`docs/validation/solution-archives.md`. Legacy `.set`/`.pnt`/binary `.state`
interoperability and broader ASWING parity remain required.

Preceding increment: the K/W wake-core radius/chord control, shared by the solver,
external sensors and surveys, browser cases and saved physical states. Its
independent 15-case two-surface study and packaged-WASM replay passed 708 physical
comparisons, with 141 targeted native tests and three offline browser workflows.
The numerical kernel is unchanged by the archive work. See
`docs/validation/wake-core.md`.

Preceding increment: the documented K/L aerodynamic-lag option, with a shared
algebraic-circulation path, retained apparent mass, browser control and saved-case
compatibility. Verification passed 156 targeted native tests, six JavaScript
project-data tests, 23 independent native and packaged-WASM cases, and four
offline browser workflows. The WASM study compares 297 physical values with
maximum scaled difference 2.311e-11. See `docs/validation/aero-lag.md`. The mesh row also
corrects an unsupported separate-sampling-mesh gate using steady equations
62–63; independent Fourier/structural resolution remains the documented target.

Preceding increment: verified straight type-5 numeric gust import and canonical
export, sharing the existing Earth-field physics. Pinned public examples,
independent field/load/unit/encounter checks and stale-import protection are
recorded in `docs/validation/legacy-gust.md`. Other catalog types, nonzero slopes
and exact executable interoperation remain open. Verification passed 79 targeted
native tests, 14 packaged-WASM cases and five browser workflows, including small
positive input-unit lengths and late-import protection.
The preceding increment: dimensionless arclength continuation improves nonlinear circulation
initialization without changing the physical equations. An original rectangular-wing
study checks signed incidence, units, complete Fourier equivalence, continuation
step refinement and an independently bracketed 2D limit. Finite-wing 90-degree
convergence and general stalled-root uniqueness remain open.
Verification passed 147 targeted native tests, 49 packaged-WASM cases and two
offline browser workflows. See `docs/validation/stall-circulation.md`.
The preceding increment: a pinned SA-1 straight-wing study compares the unchanged
archived input with ASWING 5.96 and digitized experimental lift/drag data at
five meshes and two PG Mach choices. Numerical resolution is established for
the sampled range; near-stall drag discrepancies and deep-stall branch/failure
diagnostics remain explicit. Eighteen packaged-WASM cases and two offline
browser workflows passed. Browser alpha/beta fields now accept arbitrary
decimal angles. See `docs/validation/sa1.md`.
The preceding increment added drawn cubic distribution grafts, tangent endpoint joins and
explicit per-property symmetry controls. Grafts become ordinary ASW stations
with checked value/slope reconstruction errors over the complete property,
including its exterior. Independent polynomial and variable-stiffness spring
references passed native and packaged-WASM verification, with five offline
browser workflows and 79 parser/editor tests. Exact ASWING spline
endpoint and editor conventions remain open. The preceding increment completed
persistent projects and named editable cases; legacy `.set`/`.pnt` formats remain required. The current increment adds
independent computed-result records to those projects. Every other
remaining requirement below stays part of the goal.

Status: **partial** = working component with outstanding parity/coverage work;
**pending** = required but not implemented. No row below is a claim of complete
ASWING parity.

| Requirement | State | Current evidence / completion gate |
|---|---|---|
| Open source implementation and distribution | Partial | MIT license, original Python/JS sources, downloadable source ZIP. The [extracted local-app audit](validation/local-bundle-20261108.md) verifies current kernel/source/runtime contents and three actual-worker browser workflows with external requests blocked, including failed-flow diagnostics and saved structural/coupled continuation. Public repository publication, reproducible releases and full functionality remain. |
| Complete `.asw` global blocks | Partial | Name, Unit/Units, Constant, Reference, Weight, Sensor, Engine, Strut, Joint, Jangle, Ground parsed. Lossless unchanged export and validated canonical serialization of edited global records and per-property grids; annotations and unknown blocks retained. Bundled/official-example round trips cover all parsed record groups. Complete field semantics and executable interoperation still require validation. |
| Beam distributions and arbitrary logical/physical indices | Partial | Full documented property names retained, unlimited indexed flap derivatives, multiple beams. Official Daedalus/USA/flying-wing parse checks. Unknown inputs are preserved and diagnosed. |
| Cubic interpolation, decreasing t, doubled stations, per-variable symmetry | Partial | Unit tests for direction reversal, jumps and reflected jumps, mirrored y and derivatives. Natural endpoint conditions are provisional; establish ASWING's actual spline boundary convention. |
| Arbitrary consistent input/output units | Partial | Raw input-unit physics; L/T/F/M SI conversion and derived units. Broader output-unit UI and arbitrary-label formatting still needed. |
| Node editing and independent Fourier/structural resolution | Partial | Per-logical-beam cosine/modified-cosine/uniform material-arc counts and explicit t nodes; mandatory endpoints, attachment/load/break insertion and conservative rigid position jumps. Browser node editing, required-node table, arc/angle and Fourier-basis plots, mesh JSON import/export, physical-state persistence and incompatible-state rejection. Rigid inspection and all solver families share the settings. Independent per-beam Fourier circulation counts use material Glauert angles and weighted local-flow equations. Circular-arc convergence, oscillator dynamics and native/WASM saved-state checks are recorded. Physical vortex/load samples share structural intervals, as in steady formulation §3.1, equations 62–63. Independent Fourier counts provide the documented resolution choice; separate sampling meshes are not established as a public ASWING requirement. Legacy settings interoperability and broader zero-length-interval parity remain. |
| General nonlinear 6-DOF beam, all stiffness couplings and axis offsets | Partial | Continuum BVP plus objective SO(3) mixed connected-beam network, all section couplings and exact rigid limits. Large-rotation mesh convergence, combined-load BVP comparison and joined-beam checks. The [AE-3 unit-load comparison](validation/isae-ae3-mechanics.md) adds refined elastic-axis loading, an independent continuous reference, centered linear-limit controls and two WASM replays; primary experimental discrepancies and fixture uncertainty remain. Need broad geometry/ASWING discrete parity. |
| Distributed and additional mass, inertia, damping | Partial | Steady finite-segment inertia plus unsteady eight-point material mass integration and virtual-power-consistent load transfer. Local elastic/Coriolis/gyroscopic terms, documented tdeps/tdgam strain-rate law and passivity diagnostic. Mass symmetry/energy, rigid limits and damped/undamped cantilever-frequency refinement checks. BDF1/BDF2 load-release and rigid-frame trajectories checked; Radau covers constrained motion with nonzero initial velocity; broader finite-rotation dynamic validation and ASWING parity remain. |
| Point objects, rigid pylons, full inertia and angular momentum | Partial | Rigid-pylon motion, gravity/CDA, source/doublet flow, rotated full centroidal inertia and intrinsic spin implemented. Local elastic velocities/accelerations and frame transport enter instantaneous loads. Product signs follow CG_Calc.pdf; cloud equivalence, direct Earth-trajectory acceleration and motion-repartition checks pass. Time histories and reference parity remain. |
| Rigid/pinned/roller/sprung joints, ground constraints | Partial | Joint types 0/1/2/3 and ground types 0/1/2, conservative paired reactions and tangent rank checks. Jangle moving axes, continuous nonlinear cubic laws, breaks/extrapolation, preload angles and coupled circulation; exact rigid-link/spring, orientation/covariance, pylon and load-transfer tests. Spline/interior moment-trace parity, offset/interior passivity, discontinuous freeplay/failure and stability/branch tracking remain. |
| Struts and wires, slack/preload | Partial | Current-pylon axial loads, preload, superposition, bilateral struts and explicit tension-only wire mode across legacy and source static/dynamic routes; energy/covariance, exact parallel stiffness, elastic poles, powered frequency response, free-frame balance and slack-transition/checkpoint checks. Source browser/JSON routes preserve the selected law. Printed force-vector ambiguity and undocumented ASWING compression/large-strain parity remain. |
| Extended lifting-line aerodynamics | Partial | Pointwise and truncated Fourier circulation, wind-aligned bound/CP locations and wakes, section lift slope, configurable K/W finite-core interactions for distinct physical beams and external samples, with the current interval-width floor and same-physical-beam exemption. Independent two-surface line-integral, PG/image, unit, saved-state and browser checks cover the control. Analytic Biot–Savart, high-AR elliptic continuum, complete-basis equivalence through stall, mixed representations, empirical-lag harmonic response and published flying-wing mode/panel studies. The K/F option now freezes vortex and volume coefficients at jig geometry and zero wind angles, retaining current frames, circulation, kinematics and loads. Mach/core/image-plane changes invalidate an owned cache; attached and external receiver conventions are explicit. The independent 11-case native/WASM line-integral study, 163 targeted native checks (including the separately corrected fixture), 45 JavaScript checks and ten offline browser workflows passed. Original-executable fast-mode conventions remain unverified. The SA-2 archive study now exposes increasing tip velocity and local-Mach rejection on fine meshes, confirmed by independent line quadrature. Its archived input differs from the 45-degree experiment. Force-point velocity, normal speed/Mach and rejection locations are exposed. A separate prescribed-elliptic-circulation closed form reproduces the swept-line tip growth, independently of nonlinear circulation closure. A justified refinement/tip treatment, geometrically matched swept/nonplanar/multisurface references and exact ASWING parity remain. |
| Trefftz-plane forces and span efficiency | Partial | Wind-normal current lifting-wake traces (jig geometry and zero-angle axes under K/F), infinite trailing filaments, impulse lift/sideforce/roll and induced-drag quadrature; separate near-field drag ledger. Elliptic/Fourier continuum, stagger/rotation, image downwash and published flying-wing checks. Parallel ground images supported; unresolved intersections, negative quadrature drag and oblique images are explicit gaps. Frozen current circulation in time/modal results, without shed-wake history. Broader nonplanar/multisurface mesh studies, body/jet wakes and exact ASWING parity remain. |
| Wind-aligned compressibility | Partial | Physical-to-PG coordinate transform and transpose velocity transform, tested lift increase. Need independent swept/compressible references and Mach control parity. |
| Local stall lift limiting and pressure drag | Partial | Equations 203–204, pressure/friction terms in eq 70, flap mixing. Browser factor/width controls retain published defaults, strict finite-input validation, case/archive restoration and saved-equilibrium time-launch settings. Stable logarithmic evaluation avoids narrow-width overflow and broad-width cancellation; continuation can refine to floating-point resolution without weakening its physical or branch guards. Verification includes 113 targeted native checks, 75 reference/parameter/unit cases, 270 independent 450-digit value/derivative comparisons, two exact corner systems, 19 packaged-WASM replays, 50 JavaScript checks and three final offline WebGL workflows. Initial failures remain recorded. The SA-1 archived ASWING/experimental polar is compared on five meshes and two PG settings; near-stall discrepancies remain. Signed-incidence checks through 30 degrees and zero-incidence/pressure scaling pass. The historical SA-1 study exposed competing 60-degree roots. Dimensionless arclength continuation recovers mirrored roots on four meshes in an original matching rectangular-wing model, with unit/basis and 75/85-degree continuation-step checks. An independent infinite-span scalar limit includes 90 degrees; the finite-wing 90-degree solve remains unresolved. General branch uniqueness, high-angle physical validity and broader post-stall validation remain required. |
| Slender-body source/doublet volume aerodynamics | Partial | Current-geometry PG source/doublet quadrature, body lift/profile/acceleration loads and moments in the common residual. Independent potential, adaptive-integration, cylinder drag/added-mass and closed-body Munk-moment checks. Concentric radius jumps use exact area-integrated R/2 source cores and concentrated nodal forces, with PG/images, moving geometry, steady/time/derivative/checkpoint and browser impulse/history/CSV support. Independent shrinking-transition, Munk-moment, unit, beam-response and native/WASM references are recorded. Sharp-step separated flow is outside this slender-body law. Combined radius/axis breaks, thick lifting-surface volume inputs, self-field convention, general multi-body and published parity remain. |
| Point-object volume influences | Partial | CDA source and Vol doublet, documented core and PG transform, moving pylon positions, mutual volume and wing/engine/drag feedback. Potential-gradient, symmetry and deformed-pylon checks; published multi-object comparisons remain. |
| Ground-effect image system | Partial | Solid/free-surface images of vortices, reflected wakes, body/point sources and doublets; Earth pose, arbitrary plane normal, current-geometry clearance and displayed plane. Direct boundary checks, independent line integrals, elliptic-sheet downwash, far-height limit and coupled inverse checks. Oblique compressible reflection is explicitly approximate; stationary wall-root unsteady fields and modal derivatives are verified in the AE-4 study. Moving/gust/jet wall cases, nonlinear wall time response, full published comparisons and broader parity remain. |
| Engines 0/1/2, actuator disk, losses, propeller whirl | Partial | Proportional/disk/P-factor forces and torques, physical cubic branch, blade/swirl losses, deformation-following mounts and propulsive jets coupled to circulation/point drag. Hover, power budget, direct jet momentum quadrature and independent blade-element derivatives checked. Sensor jet measurements are exposed. An original two-axis elastic rotor mount has independent gyroscopic/beam/blade-quadrature references for full-system whirl modes, complex torque response and a refined instability boundary, with spin reversal, coordinate/time-unit and mesh/tangent checks. Nonlinear rotor histories, powered/preloaded mount validation, oblique-wake and published/executable/experimental parity remain. |
| Fully coupled nonlinear aeroelastic Newton solve | Partial | Common residual includes nodal motion, internal loads, reactions, circulation and selected operating variables; current-geometry/wake and inertial feedback, complete numerical Jacobian and target/load continuation. Rigid, conservation, inverse and free-flight checks. Prescribed-condition mounted equilibrium now uses directly assembled sparse mechanical/flow blocks, a circulation Schur complement, geometry-lagged Newton tangents and full physical residual acceptance. Exact geometry/setup reuse and direct fixed-geometry circulation derivatives reduce repeated work, retaining engine/jet and load-dependent hinge feedback. Native/WASM/browser evidence is recorded in structured-mounted.json, mounted-geometry-reuse.json and mounted-direct-circulation.json. Steady load-only mass evaluation now omits unused records and zero-motion work with exact full-tangent/output controls (steady-mass-performance.json). Prescribed/free/mixed BDF1/BDF2 also uses grouped sparse local mechanics and a circulation/frame Schur complement, with nodal decomposition of net-load rows, full residual acceptance and dense fallback. Bounded pattern matching removes a verified transient-wing rank-screen stall while retaining numerical rank checks. Full physics, broader analytic derivatives, structured general trim, inverse/controller/Radau systems and published comparisons remain. Canonical acceleration/net-load steady equilibria and exactly stationary free/mixed time initialization now use the sparse global border, with original initial inputs, coordinate scales and full unsteady acceptance; direct circulation load rows and rank/missing-inertia checks are retained (structured-frame-startup.json). BDF circulation columns now directly include Gamma and k0 Gamma-dot dependence; residual-only frame solves defer wake/mass/sensor reports with identical physical rows and original full-output paths (direct-time-circulation.json). Bounded matrix and LU reuse within a steady load stage reduces stationary time-startup work, with full physical acceptance, same-state fresh-matrix recovery and unchanged rank checks (static-matrix-reuse.json). Exact influence caches now remain active through fully unlagged frame-variable columns, and xyz kernel reductions avoid temporary product tensors; physical equations and all pairs remain unchanged (frame-influence-reuse.json). |
| Arbitrary operating constraints, inverse solutions and trim | Partial | Flow/motion/flap/engine/Earth-position/attitude unknowns with net force, moment, lift, coefficient, Earth-motion-component, flight-path, equivalent-airspeed and dynamic-pressure targets; prescribed N scales only lift targets. Six-acceleration free-flight preset; reference-aware body-velocity derivative and radial-acceleration targets, direct variable targets, ten-equation steady-turn motion and sixteen-equation full flight-trim presets. Independent rigid-motion/circular-path/Newton–Euler checks and elastic straight/left/right/climbing trim. Surface lift excludes direct body/engine/point/apparent-mass forces. Steady feedback and operating targets share the same solve, with explicit command trim variables and separate actual actuators. Gust-aware reference speed/alpha/beta (steady eqs. 181–184), ideal local equivalent-air-speed and pressure targets, posed sampling and shortest alpha continuation now have independent vector/load/unit checks and a browser preset. Weighted least-squares allocation for redundant solved flaps/engines retains hard physical equations, with preferred settings, positive weights, stationarity/curvature checks and browser controls. Weighted linear projections, nonlinear disk momentum, elastic proportional flaps and saved dynamic-base references are available. Named custom equations can now target coupled sensor displacement, structural loads, adjacent strain/stress and airflow, or combine actual operating settings, net loads and coefficients. Loaded-target continuation, final rank/one-sided tangent checks, browser editing and saved dynamic release have independent compliance, sensor-vector and finite-rotation references. Exact ASWING allocation-weight/branch, VIAS/radial-reference and custom-routine conventions, seed/branch robustness, remaining constraints and published trim comparisons still required. Nonlinear time solves additionally support implicit flap/engine targets for net loads, lift, frame acceleration and radial acceleration, with local rank/ownership checks; typed velocity/pose histories now retain the trajectory equations and consistent cold initialization; compatible held-state replacements, slope breaks and cutoff now preserve before/after states, including saved Earth-velocity scope v3; broader combinations and impulsive events remain open. |
| Standard atmosphere and gravity in flight frame | Partial | US76 hydrostatic layers for −5 to 86 km geometric altitude, sea-level-constant scaling, density override, altitude-dependent sound/PG/local Mach; atmospheric altitude independent of Earth Z. Prescribed gravity magnitude rotates with attitude, preserving original weight-to-mass conversion; body-axis override retained. COESA table, independent hydrostatic integration, layer continuity, density/load/mass and coupled target checks. ASWING table/interpolation/range parity remains. |
| Aerodynamic, structural, control stability derivatives | Partial | Implicit centered linearization of the complete implemented common residual with one factorization, scaled-tangent rank and linear-residual checks. Fixed-acceleration or six-acceleration free-flight response; canonical speed/angle/normalized-rate, velocity-reference and body-origin inputs; flap/engine controls; body/stability/reverse-stability coefficients with fixed base axes/normalization. Distributed/total-fluid/net wrenches, reference/origin accelerations, circulation, nodal motion and element loads exported and plotted. Independent nonlinear perturbations, analytic drag/thrust/gyroscopic response, added mass, rigid limits and mesh/step studies. Closed-loop steady derivatives retain actual actuators, integral/custom-state equilibrium equations and solved command values; controlled settings use explicit command columns. Independent P/PI/nonlinear/scheduled-controller and acceleration-feedback formulas, full-descriptor DC comparison, nonlinear elastic Fourier re-solves and immutable-base checks. Browser controller/measurement matrices and physical-unit CSV/JSON are available. The [source moving-airflow extension](validation/source-steady-derivatives-20261105.md) retains the source steady equations, full frame response and feedback; section plots/CSV identify constitutive averages. Its 122 Python, 29 JavaScript, offline UI and 2,749 native/browser numeric checks pass. Reuse of the converged Newton factorization remains open. Full-physics and ASWING numerical parity, wind-axis display convention, branch-specific nonsmooth tangents and broader benchmark validation remain. |
| Structural strain and stress displays | Partial | Material-midpoint local resultants, translated bending/torsion moments, complete mechanical strain and curvature changes; signed shell-point strain, §8.2 strain bound and signed/absolute thin closed-shell torsional shear stress. Missing/invalid dimensions explicitly unavailable; frame/unit/axis convention exported. Browser distributions, stress unit selection, CSV/JSON and refinement study. Independent cross-section integration, wall shear energy, large-rotation/covariance, load jumps, collocation convergence and WebAssembly checks. Tension-versus-elastic shell-coordinate convention and ASWING nodal parity remain unverified; ASWING mode-display parity remains. Linear modal and quasi-steady derivative strain/stress plots are available, with midpoint availability, all-column CSV, analytical axial/torsion and independently re-solved perturbation checks. |
| Integrated mass, CG, inertia and apparent-mass tensors | Partial | Real mass/CG/reference and CG inertia, spin momentum, real/apparent 6×6 spatial matrices for surfaces and bodies. Parallel-axis/covariance/energy, exact uniform-beam, cloud-equivalence and independent cylinder pressure-integral checks. Classical versus printed ASWING body coefficient is explicit. Nonuniform refinement and executable/reference comparisons remain. |
| Unsteady local shed-vorticity states and apparent mass | Partial | Common instantaneous residual accepts local nodal velocities/accelerations and circulation rates, with empirical lag, rate lift at quarter chord, local real/apparent inertia and moving engine/point/body inflows. Zero-rate recovery, motion repartition, complete real/apparent mass symmetry/rigid limit and the documented rational lag transfer are checked, including WebAssembly. Circulation-state evolution participates in the implicit time kernel. The documented K/L toggle removes rate downwash and rate lift together, giving algebraic circulation while retaining apparent mass, inertia and damping; the browser, saved cases and physical states preserve the choice. Broader unsteady modal validation, gust-catalog conventions and ASWING validation remain. The empirical model is not exact Theodorsen theory. The two-wing low-positive-airspeed study checks the finite-frequency still-air mass limit on three meshes, including lag-off and consistent time-unit cases, with six WASM replays and an offline browser workflow. A separate exact-zero-speed, fixed-frame still-air modal path now retains thin-strip apparent inertia with explicit density and pose/gravity; its 252-state ST-4 comparison and independent references retain physical discrepancies. Broader zero-flow nonlinear evolution, ROM/stability/frequency-response/time reuse and slow circulation roots remain outside this path. |
| Nonlinear time integration and arbitrary forcing | Partial | Experimental coupled BDF1/BDF2 and three-stage Radau IIA kernel advances local elastic motion, circulation and six-DOF flight states, with prescribed, free or mixed acceleration/net-load constraints. Consistent initial equilibrium, nodal load release, SO(3) increments and Newton step retry. Independent oscillator/time-order, free-fall, rigid-body conservation and separate-reference checks. Workbench time controls, coefficient/motion/node/input histories, complete physical-snapshot JSON and selected-time CSV exports, cancellation and computed-state playback. Documented open-loop F#/E#/Ax/Ay/Az/Gx/Gy/Gz tables plus active Fx/Fy/Fz/Mx/My/Mz load targets, scaling, initial-setting offsets, cubic interpolation, doubled-time breaks and zero specified values after the last sample; independent acceleration/thrust ramp order and non-grid step checks. Earth-coordinate gusts are sampled inside the common residual; known-wave phase travel limits prevent coarse monotonic steps from skipping a pulse. Computed-state checkpoint continuation preserves physical motion, controller/forcing references and BDF history; initial load release and event-side semantics are retained. Saved steady trim launches with its solved setup and controller state, zero local rates or compatible nonlinearly completed physical disturbances, released trim constraints and full residual validation; new time inputs apply after the initial snapshot. BDF startup can give nonconvergent peak reactions for curved constraints with nonzero initial velocity; Radau and temporal refinement are recommended there. Optional coarse-versus-refined physical temporal checks, saved midpoint history and browser controls have independent spring/controller/finite-wing and native/WASM/browser verification. This local indicator is not a global error bound; unresolved constrained reactions must still be rejected. Remaining forcing targets, companion-file restart, broader constrained/nonlinear temporal-control validation and aircraft validation remain. Implicit flap/engine targets now retain the unsteady kinematics, with BDF/Radau mechanics references, rank checks, units, cutoff, saved launch and restart evidence. Solved settings are plotted/exported and participate in optional temporal discrepancy checks; typed velocity/pose inverse histories, position-history BDF coordinates and guarded saved Earth-velocity launch are integrated; compatible held-state input transitions now retain separate before/after states and restart BDF history, with checkpoint, native/WASM and browser evidence; Radau position histories now use complete Earth position/velocity-defect coordinates and replayable stages, with native/WASM single- and multiple-position, offset-reference, free-rotation, method-change and cutoff evidence; arbitrary combinations and explicit impulsive events remain open. Final local uniqueness checks cover both accepted Newton return routes; see solver-consistency.md for the regression and WASM evidence. |
| Gust fields and all documented gust types | Partial | Earth-coordinate uniform, slanted compact cosine, indefinite sinusoid, bounded arithmetic expressions in x/y/z/t and superpositions. Current deformed wing control/force/axis points, body quadrature, engines and point objects sample the same field; steady, derivative and time residuals include it. Native load/pose/elastic-feedback formulas, empirical-lag time refinement, pulse sampling guard, browser profiles, arbitrary body/Earth slice-plane surveys of saved flow states, and offline UI/JSON/history checks. Original OpenSwing JSON format; Gust-relative reference-airflow operating targets now sample the posed reference point. Pinned public straight type-5 numeric inputs now import into the common cosine field, with canonical legacy export, analytical profiles/loads, frame and unit checks, narrow-pulse transient sampling and saved-case restoration. Other VGUSTE/.gust types, nonzero type-5 slope/sign/length conventions, exact sensor-flow conventions and broader reference validation remain. Complex frequency-domain Earth gusts with streamwise phase and cosine/sine span families are implemented. |
| Sensors and user-defined control laws | Partial | Moving pylon axes; full/kinematic airflow, pitot/vane, inertial, GPS, anchor motion, one-sided csn force/moment, adjacent material strain/stress and circulation with explicit sample locations. Steady/time/modal/harmonic outputs, browser tables/history/Bode and CSV/JSON. Independent moving-frame trajectories, gravity/free fall, induced-flow quadrature and complex acceleration/gust checks. Scheduled measurement/error/integral feedback participates in steady, time, modal and harmonic residuals, with actuator unknowns and command inputs. Simultaneous operating/controller trim supports explicit command unknowns, final tangent rank checks and preservation of the trimmed modal/harmonic base. Original `.con` table syntax with explicit index/unit bindings, controller editor/import, histories, complex tables and CSV. Independent PI/acceleration-feedback poles/transfers, matrix-exponential time refinement and gain-derivative checks. Bounded nonlinear explicit/implicit actuator expressions, coupled actual-actuator references, scheduled parameters and custom differential state rates support filters, actuator lag and explicit saturation/anti-windup. State/rate outputs and one-sided tangent checks are available. Exact nodal strain, ASWING core/trace/angle parity, default INDEXC bindings, arbitrary legacy routines/internal-array access, cold/nonsmooth nonlinear controller initial-state construction and aircraft/experimental closed-loop validation remain. Closed-loop quasi-steady derivative matrices retain zero controller-state rates, release trim targets, reject singular/nonunique tangents, and expose actual actuator/measurement/integral/custom-state responses. |
| Full-system eigenmodes and flutter | Partial | Continuous common-residual pencil about loaded fixed/prescribed/free/mixed bases, with per-axis prescribed acceleration or constant net-load targets; vacuum option; published full-pencil Arnoldi in fresh UI settings; exact coordinate-integrator determinant factors in the reduced methods preserving zero-root multiplicity without small-root snapping; algebraic/hidden-constraint reduction, dense and reduced/full-descriptor shift-and-invert roots (the full-descriptor search leaves total finite dimension unclassified), full left/right eigenvectors, residuals, complex geometry/loads/strain and optional A/M export. Complex local cm, normal aerodynamic/inertial densities and elastic incidence retain their loaded-base tangent, undefined-base gaps and saved eigenvector amplitude, with plots/CSV and analytical output identities. Independent oscillators, cantilever refinement, gyroscopic/free-body and aerodynamic lag limits; original heave/pitch/lag comparison. Browser mode map, exact-integrator labels, explicit near-neutral display threshold, body/Earth phase playback and complex-output CSV. Native/WASM tests retain weak nonzero poles, scaled/permuted chains, semisimple zero-mode ROMs and rotating-body roots; generalized/defective bases remain unsupported. Rank/step/mesh studies remain essential. Operating-point root progression and checked sign-bracket refinement are available, with explicit ambiguity/coverage limits. Warm physical equilibrium continuation and bounded adaptive parameter subdivision are available. The original elastic rotor mount additionally checks gyroscopic mode polarization, mesh-dependent whirl roots and a refined frozen-coefficient crossing. Fold/invariant-subspace tracking, broader closed-loop flutter validation, vacuum Engine cases and ASWING/experimental validation remain. Physical derivative coefficients use fixed-state load extraction with analytic hinge and smooth-controller chain rules; piecewise laws retain composite one-sided checks. The original loaded swept/twisted wing resolves at tested meshes without relaxing weak-inertia guards. Homogeneous output recovery normalizes state/rate directions to retain tiny initial-spectrum loads. The two-sided QR constraint staircase now preserves complete ST-3 spectra at 8/16/32 panels, with original weak-inertia and full-pencil checks; 21 points, 165 native tests, WASM and offline-browser evidence are recorded in dense-staircase.md. The finer 64-panel uncoupled input still requires a tighter rank setting. |
| Frequency response and Bode/2D gust analysis | Partial | Full continuous descriptor solve for unit flap/engine, active frame-load/prescribed-acceleration and complex spatial gust inputs, fixed/prescribed/free/mixed frames, direct input/rate load and strain output, optional A/M/B export, full-equation residual checks and explicit pole/DC gaps. Earth-convected or uniform streamwise gusts with cosine/sine span families and mesh-phase diagnostics. Browser magnitude/dB and wrapped/unwrapped phase, physical-output/station/input selection, phase playback and CSV/JSON. Independent forced oscillator, free thrust, zero-frequency flap derivative, empirical gust lag, offset point-load phase and coupled heave/pitch/lag studies. Sensor complex response is included. Section cm, normal aerodynamic/inertial densities and elastic incidence now include direct input/rate terms and initial-spectrum boundary terms, with radian incidence and physical density units in plots/comparisons/CSV. Selected measurement commands and closed-loop actuator/integral response are included. Independent twelve-state offset-reference Newton–Euler harmonic comparisons, mixed gyroscopic roots and scheduled-feedback checks. Matched broken-loop gain/phase implements the documented 1-u/x display, with actual actuator/measurement/net-load/acceleration pairing, dimensional consistency, explicit zero/overflow/unmatched gaps, and immutable physical response. Independent controller, lag, coupling and unit-scale checks accompany browser/CSV/JSON support. Loaded frequency grids can add samples or extend the range using the exact original base, pencil and inputs, with transactional merging, exact duplicate handling, retained gaps, selected-response preservation and complete exports. Live sessions reject changed sources/settings and expire on worker replacement; fresh full-grid replay remains available. Consistent physical initial profiles use the complete finite descriptor space, including relaxation and integrator chains, and one-sided Laplace spectra with the sX-x0 rate boundary term. Nodal/beam-field, circulation, frame and controller profiles, import/export, extra-time-unit plots/CSV, per-input gaps and full-state consistency diagnostics are available. Independent oscillator, controller, unstable-system, free-flight and circulation checks cover units, mesh and step settings. Unresolved weak inertia is rejected; the full spectral convergence check is conservative. Compatible physical profiles can now initialize nonlinear time launch from a saved equilibrium, with fixed physical coordinates, hidden-constraint completion and local rank/spacing/one-sided checks. Cold/nonsmooth/higher-index initialization, multivariable return-ratio/margin analysis, general inverse dynamic targets, exact legacy Bode output parsing and ASWING/experimental parity remain. Simultaneous multi-input, multi-output and multi-station plots support gust forcing ranges, physical-unit/spectrum grouping, per-trace phase unwrapping and gaps, detailed selection, grid refinement and CSV/standalone SVG exports. Local OpenSwing Bode/comparison CSV and explicitly mapped numeric data can be overlaid with independent grids, recorded unit/time/convention conversion, preserved gaps, hide/remove/sample inspection and combined CSV/SVG exports. Preview invalidation and stale-read guards prevent old imports from attaching to a changed analysis. Original analytical oscillator checks and offline browser workflows cover conversion and immutable-solution behavior.  Large harmonic sweeps now use sparse full descriptor matrices, exact grouped local derivatives, exact element-map reuse and stationary base initialization, with separate progress for each phase; initial-spectrum finite-subspace reduction remains dense. Shared direct circulation derivatives, exact node/element maps, per-channel constant input reuse and single-evaluation output recovery retain full physical coupling. Complete Newton-Jacobian reuse and large-model startup performance remain unfinished; the fixed-frame default does not reproduce the published DAE flight-response setup (bode-assembly.json, bode-drela-setup-audit.json). |
| Reduced-order models and `.rom` exports | Partial | Arbitrary returned-mode selection, conjugate-pair completion and real mass-dual projection; real A/B/C/D and derivative-input sensor matrix, full state lift/projection and separately checked algebraic input feedthrough. Flap/engine and controller commands, mixed frame load/acceleration inputs and fixed spatial gust families; named global/sensor outputs with units, plus explicit node motion, local section resultants/strain/stress, aerodynamic strip fields and global loads/coefficients. A browser quantity/beam/sample selector retains exact mesh identity and unavailable-base gaps; SI .rom labels are explicit OpenSwing extensions. Exact singleton mass constraints preserve zero rate coordinates without relaxing rank/export guards. Nine independent spring/finite-wing references, five WASM replays, five offline browser workflows and 86 targeted native checks have passing evidence. Frame inputs propagate through real ROMs and annotated SI exports, including radian angular-acceleration scaling; selected mixed-frame speed-mode transfers match the full descriptor. Browser selection, full-descriptor comparison, immutable JSON/text and annotated .rom exports with SI physical units. Independent .rom viewer preserves printed coefficients/unknown labels, reconstructs real matrices and plots literal response with pole gaps. Nine pinned public files round-trip without coefficient changes; four original/generated mechanical cases independently check complex response, feedthrough, time/length/force scaling and actuator lag. Existing constrained reactions, oscillator step response, repeated modes and coupled heave/pitch/gust checks remain. Physical initial profiles now undergo full finite constraint completion and mass-dual projection, with represented/omitted states, complete/reduced linear free histories and one-sided spectra. Full-spectrum convergence guards retain omitted unstable modes; browser JSON/CSV/profile workflows and independent constrained/controlled oscillator and unit checks are available. ASWING Bode reconstruction/executable interoperation, older file variants, convected-gust frequency-dependent matrices, generalized/defective mode bases, derivative-input descriptor constraints, exact original output sampling/labels and aircraft/experimental validation remain. |
| Companion files `.set`, `.pnt`, `.con`, gust and forcing files | Partial | Open-loop time-forcing text import/export, scaling, doubled-time and finite-support semantics for the supported channels; active net-force/moment histories and mixed frame constraints. Relative-channel cutoff convention is explicit and still needs executable comparison. OpenSwing gust JSON remains an extension; straight type-5 numeric .gust import/export now supports the verified public layouts. Other numeric types, nonzero slopes and unknown trailing values remain explicit gaps. Selected sensor/controller command channels are supported; `.con` gain tables require explicit index/unit bindings. Other formats, general velocity/pose inverse forcing channels, default maps and executable interoperation remain. The official FAQ confirms that .pnt/.set memory dumps depend on version and compiled dimensions; compatibility needs explicit verified build profiles, not a universal array map (see legacy-settings-research.md). |
| State histories, snapshots and restart | Partial | Owned physical time snapshots with full-history JSON and solve request, time-series CSV, all-state section/strip/shoulder CSV and sampled spanwise extrema with available-count and time/snapshot provenance. Versioned OpenSwing steady equilibrium JSON with exact source/mesh validation, physical-scale conversion, controller/trim preservation and full-residual reuse in static/modal/Bode/ROM/sweeps. Physical OpenSwing time checkpoints preserve the BDF predecessor/step, velocities, circulation, frame pose/motion, controller states and original forcing offsets; native/browser/WASM continuation and event-side checks are available. Direct steady-trim launch preserves solved conditions, commands and loads and validates zero-local-rate consistency without a new equilibrium solve. Optional nonlinear physical disturbances complete loads, reactions and initial rates while preserving prescribed nodal/frame/circulation/controller coordinates. Import/export, initialization progress and restart-compatible snapshots are available; numerical refinement and unresolved-constraint rejection remain essential. Legacy binary .state solution-archive/restart compatibility, other ASWING 5.95 companion formats and broader restart/aircraft equivalence remain; .pnt stores operating-point definitions rather than computed beam states. Time checkpoints and compatible saved-equilibrium launches retain inverse actuator targets, solved settings and original forcing offsets; older OpenSwing records may omit the new optional fields. Redundant cached frame inputs are validated against saved physical state before residual reuse; equivalent angles remain valid, malformed speed/vector data and time mismatches are rejected. Hidden inverse-history constraints and predecessor-trajectory authentication are outside that check. |
| Run-case management, sweeps and stability root progression | Partial | Ordered [steady point sequences](validation/operating-points-20261030.md) now reuse the existing rigid/mounted solves, inherit specified conditions/constraints, retain failed points, and separate requested from solved trim settings. The browser provides alpha polars, per-point inspection, CSV/complete JSON, progress and cancellation. Project cases retain the angle list and cold/previous-point initialization; complete polar results require their separate JSON export. Optional warm stacks reuse checked rigid circulation or mounted physical states, preserve prescribed settings and record seed origins/retries. Supplied rigid seeds use dimensionless increments and a bounded absolute-coordinate finishing solve, with checked tiny-root/unit/WASM accuracy and unchanged cold equations. Failed points and circulation-basis changes restart independently; implicit controller measurement commands or released command trims retain cold initialization to preserve their specified meaning. External first-point seeds, arbitrary per-point browser editors and legacy point-file interchange remain. Saved-modal-request operating sweeps with fresh equilibrium and full-residual eigenvalues at each point. One-to-one shape/prediction assignment in a fixed physical coordinate metric, explicit ambiguous/missing/failed gaps and finite-spectrum coverage. Bracket refinement requires parameter and normalized-growth convergence; oscillatory/aperiodic and stabilizing/destabilizing transitions are distinguished. Browser root/growth plots, point-mode inspection, immutable JSON and path CSV. Warm loaded-equilibrium correction and bounded adaptive tracking subdivision, with recomputed warm endpoints and retained superseded attempts. Persistent browser projects hold named editable cases and separate computed-solution records with literal ASW text, applied meshes, analysis inputs, loaded equilibria, full primary/supplementary results and numerical provenance; portable JSON, undo, exact restoration, rollback, storage failures and cross-tab write conflicts have browser checks, including analytical response after restoration. Folds/bifurcations, adaptive search windows, invariant-subspace tracking, exact legacy stored-state interchange, arbitrary parameter families and ASWING/experimental progression validation remain. |
| Interactive 3D workbench, model editing and import/export | Partial | Mobile Editor/Settings/Plots/Output workspaces stack the aircraft, loading, modes and remaining plots; shared run controls, layout-independent saved settings, input validation, keyboard focus and single-viewer preservation have two production browser workflows plus 52 JavaScript checks (see mobile-workspaces.md). WebGL/software orbit/zoom, jig and true-scale deformed beams/circular bodies/pylons/braces/engine disks/joint axes, physical image plane, ASW editor, rigid/constrained modes, motion/target/engine/Earth-pose inputs, steady-turn/control-mapping presets and kinematic reports, explicit brace/body-mass conventions, section lift and force-per-length plots, lifting force-point velocity/normal speed/Mach with old-archive gaps, documented local cm, normal circulatory and distributed gravity/inertial load densities, elastic incidence change with explicit radian/degree units, local structural loads/strain/torsional stress, all-snapshot spanwise overlays and signed sampled extrema with time/forcing-side provenance, complete distribution-history and envelope CSV, quasi-steady derivative matrices/structural response plots, mass properties, reactions and hinge reports, CSV/JSON exports. Beam-property station tables support insertion/deletion/doubling, scale/offset, new/omitted properties, actual-spline previews, transactional apply/undo and saved ASW output. Arbitrary body/Earth velocity planes now inspect saved steady/time states and modal/Bode bases, with gust/vortex/volume/jet decomposition, masked interiors/ground, quiver/color plots and CSV/JSON/SVG exports. Drawn/typed cubic grafts, tangent/free endpoint joins and per-property independent/mirrored halves now produce ordinary saved ASW stations, with whole-domain value/slope reconstruction checks. Exact ASWING endpoint/editor conventions, broader plot/animation parity and legacy stored-state interchange remain. Named case projects retain editable inputs and loaded equilibria. Separate computed-solution records now retain primary results, exact requests, supplementary data and views, with checked checksums/provenance and transactional restoration in browser storage and portable JSON. |
| Deflection/mode/time/frequency animations | Partial | Accepted time-state playback and scrubbing in body/Earth frames, true-scale deformation and motion, synchronized loads/structure/report, fixed camera in WebGL and software renderers. Linear eigenmode phase playback in body/Earth frames, with explicit arbitrary display amplitude and separate base-state plots. Harmonic response phase playback uses physical input amplitude in body/Earth frames with separate base plots and explicit unavailable frequencies. Broader dynamic validation and ASWING animation parity remain. |
| Publicly accessible hosted final app | Partial | Owner-private development app deployed with downloadable MIT source. Final public audience/repository and full functional release remain. |
| Quantitative published ASWING and experimental validation | Partial | The [current ISAE suite audit](validation/isae-validation.md) records all 41 families and 279 literal parser checks (177 accepted, 102 rejected), source-pinned SA-1–8, [SA-10 winglet/tip-sail comparisons](validation/isae-sa10.md) and [SA-12 ground-effect comparisons](validation/isae-sa12.md) of all 75 lift/71 drag points across three meshes with pose/section limitations retained, including [SA-6 primary aileron tables with reconciled axes, yaw normalization and mixed test angles](validation/isae-sa6.md), exact archived P-1 component reproduction, [ST-3 modal comparisons](validation/isae-st3.md), and [ST-5 literal and reconstructed rigid-joint load comparisons](validation/distributed-static.md), with experimental discrepancies retained. Original ST-3 dense-reduction failures remain in their historical report; the later [dense repair](validation/dense-staircase.md) resolves the checked 8/16/32-panel spectra. Primary/ISAE mode-label and frequency discrepancies remain. The [static study](validation/isae-st3-static.md) compares 160 signed samples and archived curves, with torque/source conflicts retained; literal signed-load browser workflows now pass. Three literal ST-5 load cases solve across five meshes; out-of-range attachments, rejected syntax, custom link-joint behavior and experimental discrepancies remain. SA-6 adds 1,728 converged cases and 21 offline browser solves, but high-incidence control effectiveness and setup uncertainties remain unresolved. The [zero-origin Reference compatibility audit](validation/reference-compatibility.md) verifies identical prior input states and unchanged physics modules. The [primary ST-4 study](validation/st4-primary-study.md) adds conditional 252-vacuum/252-air comparisons and 672 independent references, with assumed zero-speed density, unresolved setup/inertia, experimental discrepancies and sixth/seventh-mode mixing retained. The [coverage ledger](validation/isae-coverage.md) records 17 partial families and 24 pending, none fully validated, and separates all unrun and blocked families; full-suite validation is not claimed. Pinned MIT flying-wing figure: visually transcribed trim and vector-extracted root data, inferred unpowered-glide setup, three spatial meshes, two shifts and differentiation-step comparison. Historical native/packaged-WASM root checks are in `docs/validation/flying-wing.json` and its companion study. The `trefftz.json` and `circulation.json` studies record far-wake efficiency for comparison with the published definition. Original mesh/settings are unknown. The pinned SA-1 unchanged input now has 171 native cases against archived ASWING 5.96 and ISAE-reduced experimental lift/drag data attributed to Applin (1995), with five meshes and both PG choices. Coefficient grids use their actual recorded angles; source/setup conflicts and failed deep-stall diagnostics are explicit. Near-stall experimental drag is substantially underpredicted and exact archived ASWING parity is unresolved. The SA-2 study audits the archived geometry against primary ARC R&M 2882, preserves missing pressure-drag data, and records 104 computed/ten rejected mesh/K/F/PG cases plus 30 WASM replays. Archived drag disagreement and independently reproduced tip-velocity growth remain; its geometry mismatch precludes matched experimental validation. The Durrant structural study reconstructs two main-table wings and compares nine modes against independent energy-based beam elements on three meshes, with explicit main-table/appendix, Nea, instrumentation, gravity and still-air uncertainties. Source conflicts prevent an exact ASWING/GVT or flutter claim. The current-source loaded study audits 34 native case records, exact 32-interval repetitions, tangent/time-unit invariance and three 75% spar local sign crossings at 22.0847/22.4500/22.5777 m/s for 8/16/32 intervals. The published 24.58 m/s number remains unreconciled; no parameter fitting, full-spectrum stability or experimental agreement is claimed (loaded-flutter.json). Three public-API WASM/offline-browser replays preserve the N16 sign bracket and N32 near-neutral point, with physical shape/base comparisons and complete mobile CSV checks (loaded-flutter-portability.json). Broader aircraft cases, exact executable/discrete parity, independently reduced experimental data, uncertainty characterization and converged flutter boundaries remain. |
| Documentation, numerical limits, convergence failures | Partial | Working limitations/diagnostics surfaced; expand to all physics and validated application envelope. |

Completion requires evidence for every row, browser access to the corresponding
capability, meaningful numerical validation (not tests that merely restate code),
no silently ignored unsupported inputs, and an explicit full-scope audit. Current
tests and the green build are evidence for the implemented components only.
