# Status: reproducing tested ASWING cases

Updated 2026-10-27. The acceptance target is **OpenSwing matching tested ASWING
results with the same models and operating settings**. Experimental agreement
is useful context but is not required. Daedalus reference matching stays deferred.
The full project remains incomplete.

For current coverage across all families, use the [41-family suite](isae-suite.md) and [complete backlog](isae-suite-backlog.md). The default registry now has 4,029 jobs across selected scopes in 25 families; 16 families lack adapters, and no whole family is validated. The [AE-1 expansion](isae-suite-ae1-20261027.md) covers all 100 native rows and six sensor channels: 196 computed mesh jobs, four blocked initial records, 98 scalar print matches and no complete six-channel row match. The [AP-2 expansion](isae-suite-ap2-20261027.md) adds all 117 position-grid ratios and both endpoint coefficient pairs, with unpaired exports retained. The [ST-5/AE-2 expansion](isae-suite-st5-ae2-20261027.md) covers all twelve AE-2 sensor sweeps and all four ST-5 rigid-joint load snapshots. The selected historical studies below do not describe the full current coverage or establish new-kernel passes.

The [AE-3 batch](isae-suite-ae3-20261027.md) now covers all six native finite-control states on two meshes: 12 computed jobs, 38 blocked/inventory records and 725 required slots. All 348 physical checks pass, but no six-coefficient state matches completely. All derivative, inertia and separately qualified embedded targets remain explicit unfinished work.

The [ST-1 batch](isae-suite-st1-20261027.md) retains all 197 native structural scalars from 27 files and all ten models. All 37 jobs finish: two static jobs compute six body-anchor positions and 35 remain explicitly unsupported. All 52 physical checks pass, but only two coarse-grid channels match printed precision; neither complete state matches. The 194 unavailable slots include all 76 complex roots, with 25 real-only roots preserved. Extra postprocessor arrays and plots remain outside this native denominator; no whole-family reproduction is claimed.

The [moving-frame source vacuum implementation](source-moving-vacuum.json)
passes independent mechanics and offline browser checks. It adds no archived
ISAE match and does not change any case's reference-comparison status.
The [source Euler-BDF time extension](source-moving-time.json) also passes
independent transient, momentum and restart checks. Its synthetic mechanics
fixtures add no archived ASWING time-history match.

The [published modal algorithm](aswing-modal-integration.md) is now integrated.
Fresh original ST-4 local Arnoldi solves pass on 16/32/64/128 nominal intervals.
The 32-to-64 mesh gate fails three frequencies; the separate 64-to-128 extension
passes the same 0.1% gate for all six. Finest-grid differences from ASWING are
0.018%–0.370%, with no printed-precision pass. The 32-interval browser solve
takes 12.27 s and passes 836 offline checks. Historical settings remain unknown;
no reference case is newly complete. Complete-spectrum classification remains
a separate diagnostic, not a prerequisite of the paper's local modal method.

The preceding [original ST-4 modal comparison](isae-st4-source-modes.md) uses
the unchanged model and adjacent archived driver/output. Its coarse native
run passes numerical checks, with six frequency differences of 0.0498% to
1.5110%. The next mesh is rejected because dynamic rank is ambiguous at the
declared tolerance. At that dense-method checkpoint, refinement, historical
setup and a browser comparison remained unresolved; it added no reference pass.

The [rank diagnosis](isae-st4-rank-diagnostic.md) identifies a real weak
inertia in a constrained rigid direction. Proposed reductions failed
independent lost-mode tests and were rejected. The dense method retains its
conservative guard. Subsequent local Arnoldi checks on saved pencils led to
the four fresh runs and browser comparison reported above.

The [source vacuum modal implementation](source-vacuum-modes.md) now extends
the documented structural equations into distributed/point inertia and modal
matrices, with independent scalar spectra, refinement and offline-browser
checks. It is a prerequisite for broader source-dynamic comparisons and adds
**no archived reference pass**. The subsequent [material-damping extension](source-material-damping.md)
passes independent complete damped spectra and browser checks, again adding
no archived reference pass. The [still-air modal extension](source-still-air-modes.md)
now verifies stationary apparent inertia and browser/native agreement. It also
adds no archived reference pass. Moving-frame and circulatory source dynamics,
Bode/time integration and historical ST-3 modal settings still need resolution.

The [source joint extension](isae-source-joints.md) adds Ground types 0/1/2
and Joint types 0/1/2/3 with analytic and integration checks. It adds no
archived-reference pass. The [original FFWT-1 pilot](isae-ffwt-original.md)
now imports the unchanged file and solves one declared coordinate on two
meshes. Physical checks pass; reference differences remain.

The [FFWT startup follow-up](isae-ffwt-startup.md) reduces native solve times
from 46.50/49.40 s to 20.58/34.65 s, with unchanged physical results and
accuracy gates. The browser solve takes 44.57 s and agrees with native output.
An independent saved-field check finds no vortex arithmetic or grouping error
at six selected hinge receivers. The remaining root-moment mesh sensitivity
and historical setup/discretization gaps are unresolved; no reference case is
newly classified as passing.

The [documented frozen-influence counterpart](isae-ffwt-influence-choice.md)
narrows the FFWT fine-mesh lift/root-moment differences to −0.05387% / −1.5388%.
Tip bank improves; airflow incidence is slightly farther from the archive.
All physical/browser checks pass, but the root-moment mesh check and all eight
printed-channel checks still fail. The original K/F setting is unknown, so this
does not establish a historical match or replace the updated candidate below.

| Case and compared scope | Recorded agreement with ASWING | Reference status |
|---|---|---|
| P-1, six static propeller CT curves | All 110 values at 55 RPM coordinates; maximum absolute CT difference 2.22×10⁻¹⁶, below the existing 2×10⁻¹² gate | Complete for these archived component curves |
| SA-3, all 22 polar rows and seven predicted outputs | Fine-mesh CL / CD / CDi RMSE 0.000344 / 0.000349 / 0.000000392 | Corrected-arc comparison complete; reference differences remain in all seven outputs |
| SA-2 and SA-5, selected polar channels | CL RMSE 0.00196 and 0.00792 | Quantitative comparisons complete for selected channels; differences remain |
| SA-8, tandem and fore-only polars | CL RMSE 0.00977 and 0.00928; other coefficient differences remain | Selected channels compared; a lift match alone is insufficient |
| ST-3, original negative-coupling static snapshot | All 45 rows / eight columns covered; 269/270 structural entries consistent with printed coordinate/output rounding, plus 90 conditional zeros | Very close; the remaining tip moment is 5.59×10⁻⁹ N·m in ASWING versus effectively zero; other ST-3 cases remain incomplete |
| ST-4, original Weight7a/7a_b17 vacuum modal export | Paper-method local solves on 16/32/64/128 intervals; finest six ordinal differences −0.0178% to −0.3698%; 64-to-128 changes below 0.1%; 32-interval offline browser solve 12.27 s | Selected frequencies numerically converged on the extended mesh pair. Printed-precision agreement and historical settings unresolved; original dense failure and 32-to-64 mesh failure retained |
| ST-5, original rigid-joint 20 lb 80/20 snapshot | Opt-in source-discrete solver on archived node grid: forward/rear deflection differences 0.00084% / 0.0086%, twist about 0.013%; latest browser solve 3.68 s | Very close finite-grid agreement; strict printed-precision differences remain. Bounded static browser option and project preservation verified |
| ST-5, original rigid-joint 20 lb 90/10 and 30 lb 90/10 snapshots | All 80 rows each compared; archived-grid tip-deflection differences below 0.004%, tip-twist differences below 0.014% | Very close finite-grid agreement on two further unchanged models. Strict printed/display differences and mesh sensitivity remain |
| AE-1 Pazy, 98 positive-speed coordinates | Frozen-influence displacement RMSE 0.240 / 0.120 mm at 5° / 7° | Close curves in two selected outputs; historical settings and remaining output columns unresolved |
| AE-2, original uncoupled wing at 5° / 10 m/s | New source-coupled policy: displacement difference 0.4350%, heading 0.3410%, sensor speed 0.0242%, sensor beta −0.1376° | Same original coordinate checked with default/source policies on two grids; four-channel reproduction not yet achieved |
| FFWT-1, original Flare10 at 5° / 20.9418853 m/s | Fine-mesh lift +0.5713%, root moment +11.2425%, tip bank +0.19846°, tip airflow angle −0.13120° | Two cold mounted candidates pass physical checks; root moment fails the 0.1% mesh gate. One of eight coordinates tested; historical per-point settings unresolved |

A fresh current-source P-1 replay passes all 110 archived values in 2.80 s
including imports; its maximum CT difference remains 2.22×10⁻¹⁶.

P-1 is an isolated propeller component benchmark using the archived power and
CdA inputs. It does not validate aircraft hover or independently predict those
inputs. Its experimental discrepancy does not invalidate this ASWING match.

SA-3 now compares lift, drag, CL, CD, CDi, pitching moment and span efficiency
at every archived incidence on 100/200/400 intervals. All 66 solves converge.
All 154 checks from 200 to 400 intervals pass the predeclared 1% mesh gate;
pitching moment fails that gate at all 22 incidences from 100 to 200.
No finest-mesh row matches every output to the archive's printed precision.
The selected offline browser solve takes 8.72 s, after 27.73 s startup, and
agrees with native output. Historical ASWING mesh/settings remain unresolved.
Near-sonic local velocity at the zero-chord tip also needs investigation.

The other aerodynamic polar statistics retain their recorded source versions;
they are not new runs against today's kernel. AE-2's independent saved-field
check reproduces the existing sensor calculation and rules out relocating the
receiver alone as a fix. Its 0.138° beta difference remains unresolved.

The historical **18 partial / 23 pending / 0 fully validated** tally describes
broader family studies that mixed experiment and reference reproduction. It is
not a pass count for this revised acceptance target. The detailed old records
remain intact so their evidence and limitations are not silently relabeled.

Before a reference case is complete, record its original model and setup,
account for every required archived row/output, verify the solve and mesh,
and check every required output against a stated numerical criterion. Keep
printed precision, mesh sensitivity and any approximate engineering tolerance
separate. Passing a mesh gate alone does not establish agreement with ASWING.
No parameter changes or tolerance widening should be made solely to hide a
reference discrepancy.

The [two additional ST-5 comparisons](isae-st5-load-cases.md) preserve the
different rear-wing self-weight and each file's own output exponents.
All six cold solves and fresh restorations pass physical checks. Archived-grid
strict structural matches are 392/1,120 and 396/1,120; 6/7 global header values
match in each case, with tiny roll moments remaining different. The finest
refinement passes 6/14 and 8/14 mesh measures. Refinement changes the endpoint
load quadrature and moves away from the stored finite-grid solution. These
results extend case coverage without changing the production kernel or defaults.
Both new cases solve offline in the browser in 3.46/3.36 s, agree with native
output, and reopen their saved projects without recomputation.

The [SA-3 velocity diagnostic](isae-sa3-velocity.md) now separates the bound and
trailing fields. An independent high-precision check passes; the tested JVL
curvature analogue does not explain the discrepancy. Exact historical
discretization and node-to-collocation geometry remain open. The
[AE-2 core review](isae-ae2-core-source.md) finds no supported alternative to
W = 0.25; kinematic-only sensor output worsens agreement.

The [complete ST-3 static-output comparison](isae-st3-reference.md) now uses
the unchanged signed-weight model on 44/88/176 intervals. All numerical and
mesh checks pass. One allowed span coordinate per row makes the interpolated
native outputs consistent with printed precision in 44/45 rows on every mesh;
these coordinates are not a reconstruction of the historical ASWING mesh.
The sole remaining entry is a tiny nonzero archived tip-moment residual where
the physical force pair requires zero. At exact printed centers, 220/270
structural entries match; coordinate rounding explains the difference.
Tip deflection is 40.045 mm versus printed 40.0 mm, and twist is 21.962° versus
printed 22.0°. The offline browser solve takes 3.68 s and matches native output.

The [accurate-arc study](isae-sa3-accurate-arc.md) confirms and corrects a
9.91% local length defect in the old polygonal arc map. Independent geometry
checks pass, all 66 repeated SA-3 states converge, and older saved meshes retain
their original construction. The correction barely changes the reference
comparison and slightly increases CD RMSE. It does not explain the drag gap.
Other cases above retain their recorded source versions.

The [original ST-5 output comparison](isae-st5-reference.md) resolves the
historical MATLAB scaling conflict using independent geometry, force balance
and shell-recovery checks. All 80 rows and 27 output fields are accounted for,
with computed structural quantities separated from conditional zeros and input
echoes. Native solves take 0.85–1.77 s. The clamped forward geometry differs
before loading, and only 7/14 structural field measures pass the fine-mesh
gate. The middle-grid offline browser solve takes 3.32 s and reproduces the
native result; the reference comparison remains incomplete.

The [ST-5 interpolation diagnostic](isae-st5-spline-diagnostic.md) now tests
a fixed endpoint rule found in official Drela sources. It explains the
clamped geometry and many independent material/display observations much
better than natural interpolation. Five isolated solves converge, and all
14 final mesh checks pass. Forward/rear deflection differences are 0.66% /
0.16%, but twist differences remain 3.39% / 1.25%; only 116/1,120 structural
entries match strict printed precision. These results do not change the
production app. Historical ASWING use of the candidate routine remains
unproven, and passing numerical checks is separate from reference agreement.

The [source-discrete ST-5 follow-up](isae-st5-source-discrete.md) now implements
the documented endpoint matrix/stiffness/load averaging in an isolated static
solver. On the archived node grid it reduces tip-deflection errors to
0.00084% / 0.0086% and twist errors to about 0.013%. Every structural channel's
maximum error is below 0.025% of its archived absolute envelope; that is a
descriptive error measure, not a widened acceptance gate. Refinement moves
the result away from the finite-grid archive. All three numerical solves pass,
but only 403/1,120 entries on the archived grid match strict printed precision.
Rendered Eq. 54 corrects the earlier text-only reading: invert averaged
stiffness, rather than averaging its inverse.

The [reusable static implementation](isae-source-discrete-integration.md) now
supports coupled stiffness and concentrated loads, including ST-3's rotating
tip-weight pylons. All six original-case reruns pass numerical checks. ST-5
preserves the preceding reference agreement; ST-3 matches 220/270 structural
entries at printed coordinate centers. A new saved-field audit applies the
previously frozen coordinate witness to these source-policy states and obtains
269/270 structural matches and 44/45 jointly matching rows on each of the
44/88/176 grids, plus 90 conditional zeros separately. All 930 audit checks pass.
One coordinate per row is shared across all outputs and grids, with interpolation
split at the exact t=.3348 breakpoint; no new coordinate search or solve occurs.
The unmatched value remains the archived 5.59×10⁻⁹ N·m tip Mc residual
(printed half-last-place 5×10⁻¹² N·m), versus effectively zero. This is possible
rounding consistency, not historical-node recovery or a full reference pass.
Explicit interpolation/operator identities preserve old saved states.

The [browser follow-up](isae-source-static-browser.md) completes source-specific
interval, endpoint and sensor recovery and adds an explicit static equation
selector. The offline ST-5 solve takes 3.68 s, agrees with native output and
preserves new and old saved projects without recomputation. Six restored states
retain the preceding physics and reference counts exactly. That report concerns
the preserved `drela-steady-zero-offset-v1` operator, not the new general-section
policy. The default formulation is unchanged.

The separate `drela-steady-section-v1` option adds the four section offsets,
finite shear stiffness and normal/additional distributed-CG gravity couples.
Its eight synthetic formulation tests, 58 existing regressions, 109 Python
boundary checks and 25 JavaScript checks pass. The
[general-section integration](isae-source-section.md) adds 124 native checks:
ST-3/ST-5 positions, rotations, internal forces/moments and reactions are
bit-for-bit identical to their prior zero-offset results, with cold solves of
1.45/0.95 s. The separate synthetic browser case takes 2.53 s after 36.65 s
startup, matches all 2,466 checked native numerical values and restores all
three policy generations exactly. The browser audit passes 1,111 checks.
These are implementation checks, not additional matched ASWING cases. No qualified unchanged static archive covering those new terms
was found in the bounded ST1/ST2/ST4/other-static inventory: finite-shear inputs
have unresolved literal defects; ST4's offset-bearing exports are modal;
nonzero-Cea ST5 variants lack a resolved compatible input/output pairing.

The [mounted source-coupled follow-up](isae-source-coupled.md) now adds a fourth
explicit policy, preserving the preceding three. Four original AE-2 cold solves
and fresh restorations pass 66 checks, and all four deflection/twist mesh checks
pass. The new conservative aerodynamic transfer barely changes the discrepancy:
all 16 strict printed-channel checks still fail. The sole browser solve takes
5.61 s and agrees across 44,049 numerical values; all four project policies
restore exactly. It is a verified integration,
not a newly matched ASWING case. Exact historical aerodynamic/settings choices
remain unresolved.

The three preceding policies remain distinct in requests and saved states. General rigid
static sections do not imply support for non-rigid joints, body charts, stepped
axes, dynamic coupling, struts or engines. The new fourth policy adds only the
bounded prescribed mounted steady-aerodynamic scope described above. Those capabilities and
the remaining archived-reference discrepancies remain open. Experimental-property
reconstruction is not a completion blocker; do not tune a model to fit the
archived numerical residual in ST-3.

[SA-3 current comparison](isae-sa3-accurate-arc.md) ·
[SA-3 force diagnostic](isae-sa3-reference-forces.md) ·
[AE-2 sensor diagnostic](isae-ae2-sensor-reference.md) ·
[Detailed status review](isae-aswing-status-review.md) ·
[Machine-readable evidence](isae-aswing-status-review.json) ·
[AE-2 settings comparison](isae-ae2-aswing-settings.md) ·
[P-1 current replay](isae-p1-aswing-current.md)
