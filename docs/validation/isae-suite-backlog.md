# ISAE comparison backlog

**Current focus: AE-4 flutter comparisons, selected by the user.** The
[new 40–43 m/s batch](isae-ae4-40-43-20261113.md) passes **48/48 native comparisons**
in eight bounded serial jobs. **Primary advances from 657/1,200 to 705/1,200
at 5%**. All 128 new physical checks pass. The largest new error is **0.664%**;
maximum frequency errors are **0.063% /0.150%** on cosine40/80.

Only **16/24 new mesh checks** pass the unchanged 0.1% gate. Both components
of the middle pair fail at every new speed: real-component differences are
**0.115–0.122%**, and frequency differences are about **0.212%**. The other
four components pass at each speed. Native agreement does not establish
spatial convergence. Runs cover every integer speed from **40 through
108 m/s** on both meshes; unmatched references at 103 m/s remain open.

**Current primary accounting:** 728 paired values include **705 passes and
23 failures**; failed errors have median **9.02%**, range **5.50–117.18%**.
**16 unmatched**, **12 unknown initial values**, and **444 unrun** remain.
Selected scope is 756 components. The earlier overlapping 86/108 sample and
9,480 historical modal components remain separate. AE-3 stays **434/725**.
No tracked scope or denominator changed.

The earlier [independent complete-pencil audit](isae-ae4-aerodynamic96-20261113.md)
at 96 m/s passed 5,196 checks and all 4,708 A/M columns. It supports the
implemented equations at that straight fixed-frame state, without resolving
the [native damping discrepancy](isae-ae4-high-mode96-20261113.md): the higher pair
is decaying in native ASWING but growing on cosine80/160. First-crossing
growth rates, the 79 m/s frequency, historical settings, spatial convergence,
wall/frame support, deformed branches and time histories remain open.

All eight new numerical workers completed and were reaped. Maximum use was
**9.631 CPU seconds, 13.007 wall seconds and 299.3 MiB RSS**, with separately
bounded library preload. One BLAS thread and **512 MiB /15 CPU /25 wall-second**
caps remain. Production equations, defaults, parameters and acceptance gates
are unchanged; browser/build/WASM checks remain held.

**Next: fill 36–39 m/s** on both registered meshes, eight unrun jobs.
Preserve all existing failures, original input settings and reference denominators.

**AE-3 result.** The [full native comparison](isae-ae3-frozen-influences-20261111.md)
now uses the documented frozen-influence default. **434/725 pass at 5%**:
**612 computed, 178 mismatches and 113 unavailable**. All coefficients,
derivatives, mass/inertia properties and normalized rates complete at all six
speeds; coefficients retain both declared meshes. The total is unchanged from
the earlier updated-influence comparison. Printed-precision passes are now
388. Original model bytes, target counts and numerical gates are unchanged.

All **870 base-check records and 258 auxiliary checks** pass; base evidence is
inherited from twelve verified cold solves where appropriate. All thirty
numerical children are reaped, with no native job capped or unrun. The original
83 passing regressions are now supplemented by a passing source-summary check;
four reporting/registry checks were rerun after fixing standalone imports.
The [adapter guide](isae-ae3-adapter.md) links the evidence and replay commands.
The one-thread **512 MiB /15 CPU /25 wall-second** limits are unchanged. The complete
[comparison CSV](../../artifacts/isae/ae3-frozen-primary-r2-20261111/comparisons.csv) retains all 725 entries, including
blank predictions for unavailable references. AE-3 is not fully validated.

Failed Cl/CX/derivative median errors are **51.42% /51.04% /52.04%**. Of 78 failed
mass/inertia references, 55 have magnitude <=1e-8; the other 23 have median
228.62% error. Largest mass cross-term error is 8.92645e-5. All six CLa/Cma/Clp
comparisons pass; all six CldF1/Clu/CYa/CLb comparisons still fail on the literal
model. Exact historical model/control and MM constraint settings remain open.

The separate sibling-control/free-acceleration diagnostic now covers all six
speeds: **492/576 native fields match**, including **204/210 derivatives at the
first five speeds**. These overlapping alternative results add no primary votes.
At the highest speed, nominal160 improves to 78/96 fields. A bounded nominal320
frozen solve now completes, but its Cl error rises again: **28.49% →12.99%
→24.31%** on nominal80/160/320. Mesh convergence remains unproved. No minimum
horseshoe spacing is enabled. A new fully nested **82/164/328-interval** check
preserves the flap-boundary spacing ratio: Cl errors are **28.49%, 37.27% and
36.39%**. The finer pair changes only **0.64%**, passing its 5% mesh gate but
still missing ASWING. On the same grids, rigid-jig Cl changes only **0.07% and
0.10%**. The larger sensitivity appears in the coupled response; its aerodynamic,
load-transfer and structural contributions were separated with prescribed
fields, whose changes are much smaller. The roll constraint's measured
acceleration amplification is **1.05× at low speed and 3.12–3.16× at high speed**.
Two full nonlinear target perturbations confirm the tangent prediction within
**0.00013%**. All **92 new checks pass**, and all five new children are reaped.
Native coefficient/derivative ratios are similar, supporting the conditional
roll interpretation without proving the archived mask. The remaining high-speed
fixed-acceleration CldF1 errors are **26.95% /34.10%** on nested82/164; their
algebraic contribution explains most of the corresponding Cl difference.
The new full-tangent forcing split finds strong cancellation: at high speed,
lift-normal and pitching-moment contributions are **−0.007106 and +0.007291**,
leaving CldF1 **+0.00018535**. On nested164 they are −0.007144 and +0.007340.
The components change by **0.538% /0.666%**, while their remainder changes by
**5.332%**. Over 99.9% of the moment contribution comes through the elastic
state response. All **96 additional checks pass**, including independent
published-equation load checks; all three children are reaped within existing
limits. This explains the sensitivity without identifying a faulty term or
resolving the native mismatch. The subsequent spanwise audit adds **129 passing
checks**: translated torque and the full Euler-angle relation reconstruct twist
within 9.04e−14 rad. **89.44%** of the net rolling-response mesh difference
appears in the outer flapped region, while **89.84%** of the twist difference
accumulates inboard. The report includes a new spanwise plot. Stiffness sampling
shows a small second-order difference; no missing torque or broken beam relation
was found. Three small numerical children and one rendering child are reaped.
The output-chain and rigid-wing audits add **175 passing checks** across five
normally exited, reaped children. Circulation redistribution accounts for the
mesh change; geometry and direct-control projection contribute less than
**0.02%**. The rigid-wing flap increment matches the corresponding coupled
contribution within **0.019%**, and the next refinement reduces that increment
about fourfold. These checks identify a discretization effect but do not explain
the full native discrepancy or justify changing a physical equation. These
alternatives add no primary votes; historical inputs remain open.

The [constrained warm-correction improvement](isae-ae3-constrained-warm-20261111.md)
is now adopted: **43 regressions and 46 numerical checks pass**. The two AE-3
roll-target jobs take **5.36 / 5.45 supervised seconds**, versus **24.72 / 24.78**
in the saved dense runs; 13,260 recorded values retain dense parity. Only the
warm eligibility guard changed; the full equations and residual/rank gates are
unchanged. All fourteen children are reaped, including three retained nonpassing
attempts. The native comparison keeps its original source hashes and counts;
its cold/checkpoint paths are unchanged.

The [independent nonlinear control check](isae-ae3-control-nonlinear-20261111.md)
now completes **eight full solves**, passing **100 physical and 30 response
checks** at two perturbation sizes. Both the held-acceleration and active-roll
responses agree with their saved tangents, including the complete solution
vectors. Their high-speed CldF1 values are **0.000185346522 / 0.000578437891**;
the native value is **0.000146**. The held-acceleration error remains **26.95%**;
changing response convention does not resolve it. Two earlier wall-capped
attempts remain recorded. The successful serial replay separates bounded library
loading from bounded numerical work; all ten numerical children are reaped.
These diagnostics add no native votes.

The [circulation-mode study](isae-ae3-circulation-modes-20261111.md)
now checks 19, 38 and 76 Fourier modes on the unchanged 82-interval conditional
high-speed case. Rolling-moment errors are **12.56%, 10.53% and 5.70%**, versus
**28.49%** pointwise. A full 82-mode basis reproduces pointwise circulation;
the final mode refinement changes Cl by **17.74%**, so convergence is not
established and no default changes. All strips remain unstalled. Historical
mode/node settings remain unknown; the following fixed-order study separates
interval resolution from mode truncation.

This study exposed and fixed a [continuation checkpoint defect](steady-continuation-operating-origin-20261111.md):
the original operating-target ramp values were omitted from saved progress.
The corrected full AE-3 restart matches all **1,035 solution components exactly**.
The 76-mode case now completes in two serial stages. **47 native regression
checks pass**, including the existing serial parity checks; earlier capped
attempts remain recorded. Governing equations, native fractions and resource
limits are unchanged.
Browser/build checks remain held.

The [fixed-mode mesh study](isae-ae3-fixed-mode-mesh-20261111.md)
now holds **38 modes** fixed on **82/164/328 intervals**. Conditional high-speed
Cl errors rise to **10.53% / 22.12% / 25.17%**; the final mesh change is **2.43%**.
All **135 physical/mesh checks pass**, with no stalled strips. The closer coarse
result is not a converged correction. The following 76-mode comparison separates mode order from grid resolution;
historical settings and primary inputs remain qualified.

A verified [Fourier matrix optimization](steady-fourier-local-assembly-20261111.md)
reduces the saved AE-3 matrix's geometry groups **498 to 18** and measured CPU
build time **3.449 to .167 seconds**. Two complete matrices and Newton steps
match exactly; **17 selected native regression cases pass**. The cold solve
reproduces all **1,035 components exactly** in **1.41 CPU seconds**. The 328-grid
chain finishes within the original per-child limits. Capped attempts remain
recorded. This adds no native passes; AE-3 stays **434/725**. Browser/build
verification remains held.

The [mode-and-mesh comparison](isae-ae3-mode-mesh-20261112.md)
now also completes **76 modes on 82, 164 and 328 intervals**. Conditional Cl
errors are **5.70%, 20.58% and 24.16%**. At the finest grid, changing 38→76 modes
changes Cl by **0.81%**; refining 164→328 at 76 modes changes it by **2.88%**.
Both last truncated-mode pairs meet the existing 5% policy, but the K76
result still differs from the saved pointwise result by **8.97%** on 328
intervals. Representation convergence remains open. A read-only review passes
21 input/node/operator checks and discloses the four intervening kernel files;
it is not a fresh same-kernel isolation. All **150 physical/mesh/setup checks**
and **16 additional matrix checks** pass. The exact cold-replay gate fails at
a maximum normalized state difference of **7.99e-14**; the existing 2e-10
parity gate passes and the zero gate remains recorded. No production source
or native votes changed. The following current-kernel audit now resolves the
source boundary and checks the deformed-section aerodynamic fields; the
representation gap remains open. AE-3 remains **434/725**; browser/build checks
remain held.
The [current-kernel representation audit](isae-ae3-representation-fields-20261112.md)
recomputes pointwise328 with **47 passing checks** and reproduces its Cl within
**5.53e-18**. The **8.97%** gap from K76 remains on identical production code.
Two independent field/load workers pass **38 checks**, recovering accepted Cl
within **2.17e-19**. Switching circulation while holding shape fixed changes
Cl by about **0.000005215**; the coupled gap is **0.000055077**, about **10.56
times larger**. Two diagnostic paths associate **90.53%** of the gap with the
shape change. This is not a unique causal split or representation convergence.
The failed binary64 zero-core reference controls remain recorded; direct
Biot–Savart quadrature and 90-digit arithmetic resolve their cancellation
error without changing OpenSwing. All eight numerical children, including two
failed diagnostic attempts, are reaped. No production change or primary pass
is added.
The [completed coupled-tangent check](isae-ae3-coupled-residual-response-20261112.md)
passes **38 checks** and predicts the observed pointwise/Fourier Cl increment
within **0.062%**. Structural response amplifies the fixed-shape correction by
**3.33×**, and roll acceleration adds **3.17×**, explaining the **10.56×** total.
Both declared spatial partitions identify the aileron boundaries as dominant;
the tips contribute **−5.07%** of the signed correction. The single worker
completes in **3.45 CPU /4.95 wall seconds** and is reaped within unchanged
limits. This explains the conditional representation difference; primary AE-3
still uses pointwise circulation and remains **434/725**. Historical input
ambiguities and native mismatches remain open. No production equations change.


**AE-2 remains open.** Exact sparse recovery now handles allocation failure in
the full-Newton beam factor; **16 production regression tests and 20 AE-2 control
checks pass**. The control matches within **6.661e−16** in normalized coordinates.
The real memory error recovers within the existing limits, but the smaller
retry reaches the original minimum increment without convergence. Its last
accepted load remains **92.1631%**. No native comparison pass is added.

The last fully audited AE-2 comparison remains **2,070/2,200 at 5%**: **523 states,
2,092 computed values, 22 mismatches, 12 unresolved outputs and 96 unavailable
references**. It precedes the recovery-only code change; the full sweep has not
been repeated after adoption. The eighteen 5° failures have median **267.995%**
error (range **227.303–356.743%**); four 1°/16 m/s failures have median **12.2094%**
(range **8.6983–15.7294%**). Prior source revisions and failed attempts are retained.
Numerical jobs stay serial with one BLAS thread and unchanged **512 MiB /15 CPU
/25 wall-second** limits. Browser/build checks remain held.

The earlier [Newton/line-search study](isae-ae2-newton-merit-20261110.md)
finds virtually identical lagged and full Jacobian directions at the difficult
20 m/s state (relative difference 2.353e−8). Stall-transition circulation curvature
accounts for 99.9886% of the full-step squared residual, forcing the original
line search to accept 1/16. A separate correction-norm merit experiment halves
the final 19 m/s control step from **26 to 13 iterations**, passes all **20 physical
and parity checks**, and agrees within 8.737e−13 in normalized coordinates.

The difficult 20 m/s experiment still does not complete: it saves a **92.1875%**
load boundary before a retained supervisor timeout. A separate fresh restore
verifies that partial boundary at residual 4.207e−14; it is not a full-load pass.
At that diagnostic observation, production defaults and the **548/2,200** count were unchanged.
The five supervised diagnostic processes are reaped (four zero exits, one timeout).
The [report and plots](isae-ae2-newton-merit-20261110.md) distinguish the numerical
candidate from the original continuation and retain the native branch discrepancy.

The [cold-solve diagnostics](isae-ae2-cold-stages-20261110.md) complete the
previously failed 18 m/s, nominal-160 negative-coupling case in four bounded
continuation jobs. All 18 physical checks pass, but the same opposite-deflection
branch remains (three native errors of 229.178–284.755%). The staged 19 m/s
control exactly reproduces every prior solution coordinate and all four outputs.
Together they pass 38 checks. At 20 m/s, nominal 80 reaches a checked 87.5%-load
checkpoint; its next full-load attempt times out. That partial state earns no pass.

The traces show many damped Newton steps and repeated structured-matrix
refreshes: 72 iterations in the control, 75 in the complete finer-grid case.
The complete stages use no full-matrix fallback. All 13 staged children are
terminal and reaped (12 exit zero, one supervisor timeout); the separate
whole-control diagnostic timeout is also retained. Numerical children retain
one BLAS thread, 512 MiB and 15 hard CPU seconds; diagnostics use a 25-second
worker alarm after setup plus a 30-second outer supervisor, unlike the native
suite's 25-second supervisor. No total-runtime speedup is claimed.
[Residual, damping and matrix-reuse plots](../../artifacts/isae/ae2-cold-stages-20261110/newton-progress-verified.png) show verified load boundaries.
These diagnostic attempts add no primary votes and preserve all original failures.

The [complete 5° sweep comparison](isae-ae2-beta5-sweeps-current-20261110.md)
raised the preceding current replay from **34/2,200 to 548/2,200** at 5%, through
expanded coverage with the same solver. All three original layups and every
archived speed in their commanded-beta-5° sweeps have been attempted on both
meshes. Uncoupled and positive coupling pass **176/176 and 240/240 available
comparisons**; each retains eight unavailable initial values. Negative coupling
passes 132/144 computed comparisons, with 12 opposite-branch mismatches at
17–19 m/s, 16 outputs from four failed runs, and eight unavailable initial values.
Typical failed-value error is **249.161%** (range **227.303–356.704%**).

The preceding 5° observation retained **560 computed values, 16 failed-run outputs, 1,528 finite
unrun comparisons and 96 unavailable native values**. All **2,520 physical checks**
and **69 completed mesh pairs** (138 checks) pass; maximum fresh residual is
9.995e−13 and maximum mesh change is 0.04078%. Three nonzero mesh pairs remain
incomplete at 18–20 m/s. [Four-channel curve overlays](../../artifacts/isae/ae2-beta5-sweeps-current-20261110/curves.png)
show the branch split and leave failed predictions absent.

The four failed negative-coupling runs ended with SIGKILL before returning a
solution: nominal 160 at 18/19 m/s, and both meshes at 20 m/s. All were reaped;
the exact kill cause was not recorded. Small serial limits remain unchanged:
one BLAS thread, 512 MiB, 15 CPU seconds and a 25-second supervisor deadline.
No retries, fitted parameters or production changes were introduced.

The [completed inverse-speed diagnostic](isae-ae2-staged-inverse-20261110.md) remains separate:
its positive branch recovers the 18/19 m/s controls within 0.221%, while the
archived 17 m/s deflection requires 18.9528 m/s. It adds no primary passes and
does not establish original native convergence, stability or uniqueness.
Next: continue the pinned 1° plan at uncoupled IAS 10 m/s, followed by the
two coupled layups. Retain the three new deadline failures and audit reporting
overhead before any recovery. The 10°/15° sweeps and high-speed branch issue
remain open; the correction-merit candidate is not a production default.
Browser/build tests remain held.

**AE-1 deferred:** its [full comparison](isae-ae1-full-current-20261110.md)
remains **1,170/1,200**, with six crossover discrepancies and 24 unavailable
startup values retained. The [final spacing refinement](isae-ae1-refinement-current-20261110.md)
finished the three probes already underway, passing all 87 physical checks.
The current cosine tip-Z error remains 30.900 µm at nominal 160; the alternative
mapping's close nominal-80 match does not persist under refinement. No default,
primary fraction or acceptance gate changed. Further AE-1 work is deferred.

**ST-5 deferred:** its [static gravity reporting change](isae-st5-static-gravity-pending-20261110.md)
has 14 passing analytical tests, with broader verification incomplete (four
passes and one unresolved modal-fixture failure). The saved-data production
replay, fresh ST-5 parity solve and JavaScript/browser verification remain pending.
The accepted ST-5 mechanics score is unchanged.

**Retained ST-5 results.** The [current mechanics comparison](isae-st5-mechanics-current-20261110.md)
passes **16,687/16,688 distinct native observations at 5% plus original printed
precision**. All 16 original static cases pass physical checks on five grids:
**80 physical states and 224/224 final mesh checks**, with maximum final field
change 0.03865%. The sole miss is a near-zero normal force, differing by
0.0000381 lb (13.12%). Six acceptance-accounting tests pass.

This explicitly changes the primary scope to native agreement on the archived
station grid, qualified by independent physical and convergence checks. Mesh
repeats, prescribed zeros, input echoes and unresolved display fields add no
mechanics votes. All four historical strict totals, finer-grid discrepancies
and unavailable reference evidence remain separate and unchanged. The reduced
primary denominator changes the overall pooled percentage; it is not a solver
regression. No production equation, geometry, load or material property changed.

The [converged paper overlay](../../artifacts/isae/st5-convergence-current-20261109/converged-paper-moments.png) retains all twelve joined-wing moment
curves from Part III Figures 28–29. Maximum difference is 0.412% of each curve's
peak, a descriptive curve-scale error. Remaining work: investigate the near-zero
force and reconcile the paper's modified-link description with literal roller outputs. Original node
generation, reaction display and unavailable modal evidence remain open.
ST-4 remains stopped; browser/build checks remain held.

The [ST-5 recurring runner](isae-st5-recurring-20261110.md) now registers all sixteen
cases with the same mechanics scope. Four fresh representative cases complete
20 physical states and 56 final convergence checks, preserving the sole native
miss. The independent import succeeds and 121 focused tests pass. This replay
adds no primary votes; the complete study still supports the fraction above.

The [remaining-force audit](isae-st5-force-audit-20261110.md) confirms the original token
and exponent. All four coordinate-precision probes converge; their largest
effect is 9.44% of the 0.0000381 lb discrepancy, so none resolves the miss.
The full force-vector error at that location is 0.00375%, while the archived
normal force has a small left/right asymmetry. Original node generation,
native stopping behavior and output recovery remain unresolved explanations.
The primary count and tolerance are unchanged; no production physics changed.

The [ST-5 workbench presets](isae-st5-browser-presets-20261110.md) now include all sixteen original
static models and an explicit comparison-setup action for the reviewed section
equations, file gravity and archived station grid. All 34 data files match
pinned sources/settings; at that check the 141 production modules were unchanged. UI
integration, the eighteen new JavaScript checks and build verification remain
pending under the existing test hold. No new native passes are claimed.

The [distributed normal-load audit](isae-st5-reaction-display-20261110.md) now checks the meaning of
`f_reac` against the manual and all sixteen saved cases. Existing physical
gravity loads and midpoint normals agree with all 992 physical-interval values
within 0.01966%; 200 duplicate/terminal display rows remain separately retained.
The earlier scalar-midpoint diagnostic omitted normal projection and endpoint
weight averaging. Exact export interpolation remains open. No solver, equation,
primary fraction or tolerance changed; this is separate from the retained `Fn` miss.

Retained ST-4 findings (deferred while working on ST-5): the
[completed mechanics comparison](isae-st4-mechanics-current-20261109.md) passes
66/72 published frequencies at 5%, median error 0.2028%. Six failures in four
configurations span 5.556–19.703% (median 14.073%). All 64 physical states,
72 primary mesh/shape checks, 2,048 matrix checks and 18 focused tests pass.
The primary scope now compares complete three-frequency sets; the original
54/72 named-mode checks and 93/3,749 archive stay separate. This is an explicit
scope/method change with no production-physics changes. Deferred work: resolve the
unloaded input and the 7d/33, 7f/24 and 7f/40 source correspondences, then
complete replay through the newly integrated recurring adapter. Keep all six
failures required. The lower-inertia unloaded diagnostic adds no primary votes.

The [direct native-export refinement](isae-st4-native-refinement-20261109.md)
now passes all 31 frequencies on 128/192 meshes, including the seventh 7d root.
Maximum native error is 0.8128%; mesh change 0.06841%, continuous-reference
error 0.05472% and all 320 saved-matrix checks pass. The original 20/31 result
and killed 256 attempt are retained. All values survive compact JSON exactly;
the serialization wrapper changes no numerical equation. This overlapping
supplement adds no primary votes. Native identity/settings and airflow remain open.

The [recurring ST-4 adapter](isae-st4-recurring-20261109.md) now preserves the
paper and native scopes separately. The full native replay and combined import
now pass all 31 original frequencies using ten fresh states. The paper replay
stopped after 16 completed configurations, with eight unfinished; the previous
complete study still supports 66/72. The interrupted job and terminal receipt
are preserved; no ST-4 process remains running. The [source-row audit](isae-st4-source-rows-20261109.md)
identifies mixed positions without fitting predictions, and a 7.93% discrepancy
between an ASWING CSV value and its paired native export. No original target,
production equation or accepted count changed.

The [current airflow diagnostic](isae-st4-airflow-current-20261109.md) completes
four bounded jobs with 192 matrix/pairing checks passing. A 40-node modified
cosine grid reduces the low-frequency error to 1.48% and restores the native
slow-pole sign, but its magnitude still differs by 24.62%. Keep this separate
from structural acceptance: exact archived nodes and convergence remain open.
Investigate documented node generation/weight placement before attributing the
near-critical mismatch to a missing physical term. Neither spacing alternative
adds primary passes or replaces the historical strict airflow ledger.

ST-2's completed
mechanics comparison passes 91/91. Its original static attachment remains open:
the retained MIT examples have no out-of-range anchors and supply no native rule
for that case. Preserve the independently supported rigid-tip reconstruction;
do not alter production attachment behavior without source evidence. The
earlier ST-4 batch stopped after six completed jobs and one interrupted job;
its frozen plan, partial results and terminal receipts remain preserved. The
completed continuation reuses those six verified states and adds 58 fresh states
without overwriting that attempt.

The new ST-3 adapter's three-job pilot now completes six physical states, covering
positive force, signed torque, modal behavior and both unavailable ordinates.
All five readable values pass; the combined import and seven artifact checks
pass. Its fresh replay stopped scheduling after 36 of 43 completed jobs when
focus switched to ST-4. Seven jobs and the final import remain; no solver is
running. The existing 93/95 mechanics result is unchanged.

Retain the earlier [baseline input audit](isae-st4-baseline-pairing-20261109.md):
W0M and WING have identical beam properties, so W0M cannot supply a lower-inertia
unloaded alternative. The root driver's W0 input is still missing. The subsequent
0.0035-inertia sensitivity uses an explicitly modified input and remains separate.

The [registration overhead fix](isae-st2-registration-performance-20261109.md)
now shares production-source hashes within each legacy ST-2 plan and rechecks
the complete inventory before returning. It removes 75% of those repeated reads
and preserves every job setting/target. Forty-five focused checks pass; the
interrupted broader source-check batch remains explicit. This adds no native
passes and does not resolve the out-of-domain attachment convention.

The [loaded attachment check](isae-st2-loaded-attachments-20261109.md) now
extends the static result to six vibration modes on both meshes. All four
states, 96 matrix checks, mesh/shape gates and independent point-motion/mass
checks pass. Public input history preserves the same out-of-range anchors
from the initial upload. Keep that parsing question open; the evidence
supports the physical pylon/joint mechanics and does not justify changing
the input policy. The 91/91 native mechanics score remains unchanged.

ST-3 retained status: the [complete current ST-3 static
comparison](isae-st3-static-curves-20261109.md) passes all 84 readable ordinates
out of 86 required, on both meshes. Two clipped source values remain unavailable.
All 80 serial states and 86 mesh checks pass; static errors have median
0.08725% and maximum 0.43472%. With the unchanged 9/9 modal result, the explicit
primary mechanics scope is 93/95. The historical 930/1080 static snapshot stays
separate and intact. Native startup, modal labels, legacy compatibility and
regular-catalog integration of the new static scope remain open.

ST-2 retained status: the
[complete recurring replay](isae-st2-mechanics-complete-20261109.md) now passes
all 77 published static ordinates and 14 modal frequencies in 43 serial jobs.
All 89 physical states complete without failure or retry. The combined-summary
importer supports and authenticates the mechanics scope; all 98 focused
mechanics/reporting checks pass. The original 56/490 archive remains separate.
Workflow integration is complete. Native attachment/input compatibility,
historical settings and legacy output fields remain open.
Browser/build work remains held. See [current status](ISAE_STATUS.md)
for the latest results; the older investigations below retain their original
counts and priorities as historical evidence.

Earlier SA-11 focus: pre-stall swept-tip local-flow
failures. Post-stall repairs are deferred at the user's request. The current
refresh covers all sixteen archived polars and four paired configurations.
The [expanded result](isae-sa11-complete-scope-20261108.md) is **163/9,184 at
5%**, with 47 valid states, 281 local-Mach rejections and 984 unavailable
original requests. All 328 executable requests were freshly run with unchanged
outcomes. Adding upper and upper/lower winglets doubles the denominator; no new
numerical matches are claimed. Their original Joint scaling/attachment blockers
and the eight .75/.78 normalization conflicts remain explicit, with overlaps
counted once. Zero-incidence fields confirm negligible stall leakage;
investigate low-angle junction flow and historical setup first.

The [whole-beam receiver sweep](isae-sa11-whole-beam-polar-20261108.md) now
extends the two-angle finding to all 21 archived 0–5° rows. Formal CD error
falls from 12.63–44.13% on the earlier native-receiver diagnostic to
0.043–0.241%, with identical source endpoints and the existing production
sampling. Formal CL error magnitude is 0.587–0.730%. All states still reject
at exactly two roots; maximum local Mach spans 1.223–2.849 and stall drag is
negligible. Nineteen new serial calls and two reused states are checked against
the original table and independent force reductions. This is the disclosed
report-minus4 alternative, not a new primary score. Retain the published
sampling and force laws; resolve the local root velocities and producing
setup while using the broad force agreement as a constraint. Do not clip
moment PG, drop strips or promote rejected states to passes.

The [Trefftz and root-ray audit](isae-sa11-whole-beam-wake-20261108.md) now
checks CDi and efficiency separately on every one of those 21 states. Error
magnitudes are 1.390–1.537% and 2.930–2.984%, respectively. Both are within 5%,
although less accurate than the native-receiver diagnostic; no best-of-settings
score is assembled. Near-field vortex drag remains 26.84–31.72% below Trefftz
drag, so `CD-CDi` cannot be taken as native profile drag. The current root-ray
decomposition retains the large offset-origin field even after subtracting
only its circulation-imbalance term. Keep the local-flow/setup investigation
as the remaining task; all states and primary fractions remain unchanged.

The [root-moment envelope](isae-sa11-root-moment-envelope-20261108.md) now
rules out using aggregate CM at 5% to identify that correction: all four
conditional moment envelopes intersect the tolerance band. Matching the printed
whole-beam totals using only the two undefined intrinsic moments would require
root Mach above 0.999997, without satisfying the velocity equations. Native
receivers use section-local cosine angle midpoints; only main-wing receivers
move materially under the whole-beam rule. Root velocity changes come from
circulation. Retain the local-flow investigation; no moment-only tuning or
additional primary passes follow from these saved-field checks.

The [paired-speed moment audit](isae-sa11-moment-speed-20261108.md) now shows
that total-Cm agreement can conceal a receiver mismatch. With fixed endpoints,
the documented whole-beam rule reduces the baseline increment discrepancy from
7.11–23.15% to 1.17–2.18%; three extension replays agree within 0.624%, while
the fourth reaches local Mach 1.005887 at 266 m/s. Two serial solves completed.
Retain the published full bound-point velocity/local-Mach law; this evidence
does not support a global velocity substitution. Continue the actual winglet
junction and producing-setup investigation, keeping all alternatives and
rejected states outside the unchanged primary 163/9,184 count.

The [fixed-PG candidate study](isae-sa11-fixed-pg-candidate-20261108.md)
narrows the baseline .75/.78 setup: independently sourced normalization and
slope 6.34 with zero global PG bring native/production CL/CDi within 0.4% at
0°/1°. Production Cm is within 0.2%; total CD is still 42.70–46.82% high.
This does not transfer to the upper-winglet archive. All nine winglet states
reject local Mach without stall while circulation agrees with native AVL within
0.124%. Both extension comparisons fail exact geometry mapping because the
exporter straightens curved ASW distributions. All twelve native runs and
eighteen production calls are terminal; four planned production calls remain
conversion-blocked. Keep the primary **163/9,184** result. Next, reconcile
upper-winglet inputs by speed pair and resolve local junction evaluation;
do not use another global-PG/count sweep as a proposed local-flow repair.
The [unchanged full-scale cant0 candidate](isae-sa11-cant0-candidate-20261108.md)
also fails to explain the upper .75/.78 archive at 0°/1°: native CL errors
are +4.87–6.95%, CDi −19.34 to −12.75%, and efficiency +24.15–39.59%.
Both direct rigid-aerodynamic calls reject local Mach before stall. Original
joint errors remain, and no archive is reassigned to this unpaired model.
Return to the matched .70 upper-winglet junction; this specific scale/geometry
candidate is insufficient and adds no primary matches.
The [additional Chreim source audit](isae-sa11-chreim-review-20261108.md)
does not establish an ASWING correction: its better-converging method changes
both wake geometry and the section-lift velocity, while retaining the same
control-point slope factor. ISAE says it did not observe the cited wake
instability. Do not classify ASWING as the paper's coincident-control-point
Gamma method or use its results to replace the force law. Keep the junction
investigation and the known curved-extension conversion defect explicit; no
new solver results or primary passes follow from this review.
The later [curved-extension checks](isae-sa11-curved-extension-20261108.md)
remove the source-endpoint conversion blocker by sampling each original ASW
node. Six native and six production cases are terminal; five production states
compute and one original .70 fine-grid state rejects local Mach before stall.
All four zero-PG/alternative-normalization production checks agree within
0.075% CL, 0.692% CDi and 4.049% total CD, but their historical setup is still
unverified. Keep them separate from primary matches. Native AVL's small
quartic core matters for curved-bound fields and is now replayed explicitly;
it does not remove swept-tip growth. Future comparisons must retain the
measured receiver and core differences. Primary SA-11 stays 163/9,184.

The [length-allocation and speed-pair audit](isae-sa11-allocation-and-speed-20261108.md)
rules out the tested length-proportional allocation as a junction repair: all
six states converge without stall and still reject local Mach. The original
.75/.78 outputs now provide evidence beyond command omissions: three
configurations retain all CL/CD/CDi/efficiency values within printed precision
across speeds while Cm changes. The upper/lower configuration changes in all
channels. Constrain global PG versus local moment PG from this signature;
exact producing inputs/startup and normalization remain unresolved. No new
primary matches or denominator changes follow.

The [section-input diagnostic](isae-sa11-section-inputs-20261107.md) now
separates a likely input mismatch from the remaining drag issue. The baseline
alone uses slope 7.0; substituting the other SA-11 models' fixed 6.34 brings
CL within 0.124% and CDi within 0.133% at four pre-stall states. Transferring
the extension's drag inputs as well leaves CD 5.32–6.27% low at 1°.
Retain the original comparison: exact native producing inputs are unverified,
and the alternative does not resolve fine-grid swept-tip or normalization
failures. No fitted constants or production-equation changes were made.
The [frozen-influence follow-up](isae-sa11-frozen-inputs-20261107.md) does not
resolve the residual drag error: transferred-input CD remains 5.18–6.08% low at
1°. Eight saved outputs satisfy the reconstructed force/moment equations within
3.33e-16 normalized error. Further toggling at these points is not useful;
investigate swept force-point velocities and native section-input evidence.

SA-10 is deferred. Its [complete fresh comparison](isae-sa10-focus-20261107.md)
passes **1,610/2,268 at 5%**, with 269 valid states, one local-Mach rejection
and 54 original attachment-input blockers. The Newton corrector removes the
reproduced timeout and preserves physical predictions within 2.93e-14 scaled
error; the +354 displayed matches reflect the allowance change. All six
original models and both meshes remain. Deferred work includes Louvered's drag and
induced-drag discrepancy (277/378, the weakest executable configuration), plus
the shared post-stall induced-drag difference. Retain the original attachment
and local-flow blockers; do not substitute repaired models or the unverified
strength-20 setting. Current plan: `artifacts/isae/sa10-newton-20261107/plan.json`.

[SA-7](isae-sa7-focus-20261107.md) is deferred at the user's request.
Its selected comparison is **682/812 at 5%**:
full aircraft 406/406 and fore wing 276/406. The original fore-wing input
matches the dimensions in the ISAE report; the later repository file changed
geometry without changing the reference table. The former 406/812 pairing
remains a diagnostic; this count change corrects source pairing, not equations.
All 58 fresh fore-wing jobs converge. The remaining 130 failures comprise
116 Drag/CD checks, four low-lift Lift/CL checks, and ten post-stall CDi checks.
Resolve those differences without altering the signed native references.
Frozen-setting pilots lose 15 matches and gain none; supplied drivers explicitly
toggle F, so retain their evolving-influence setting.

The [force-consistency follow-up](isae-sa7-force-consistency-20261107.md) now
verifies the published surface-force identities on 24 fresh mesh states.
Twenty-three native rows violate the conditional CD/CDi lower bound even at
5%; 22 violate the drag-only floor. The sampled non-drag failures persist from
39/40 to 80/160 interval requests, with fine-grid changes below 0.004%.
Investigate native setup/output conventions and independent source evidence for
the non-drag differences; do not repeat rejected mesh, frozen, receiver or sign
sweeps without new evidence. `--comparison-scope sa7-documented` now selects
the 812 documented-case targets directly, preserving all signs and avoiding
double-counting. Counts remain 682/812.

[SA-6](isae-sa6-focus-20261107.md) is deferred at the user's request. Its
profile-load feasibility study was prepared with two preliminary LP pilots,
but no planned 88-state batch was run. Retain that work as unfinished.
The [complete frozen-default F1 comparison](isae-sa6-frozen-f1-20261107.md)
passes 370/528 separately from statics. Its analytic response passes all
selected nonlinear-stencil checks. The
[independent section reference](frozen-stall-reference-20261107.md) now verifies
both influence modes and upper/lower stall transitions, including control and
incidence derivatives. The [full finite-wing reconstruction](isae-sa6-frozen-independent-20261107.md)
now also verifies all 88 current static/F1 states and four independent cold
equilibria. On resuming SA-6, investigate the native profile-normal force identity (default
11.92–12.84% high) to distinguish stall/setup and load-convention differences;
do not repeat the completed equation, vortex-field or control-response checks.
The registered frozen-influence default passes **470/528**, confirmed by 88
fresh solves and retaining strength 40 and all original targets. The former
current-wake **346/528** remains a separate historical alternative. All 58 frozen
failures are roll errors of 5.09–8.25%. Prioritize that post-stall rolling
response with source-supported math; both alternatives converge. The qualified strength-20
result remains separate. The full SA rerun is deferred after 457 jobs, with
seven completed family results retained and SA-10 partial. Its stopped job,
timeout and errors are preserved. FFWT-4 remains deferred at 200/8,000.

The [FFWT-4 complete source audit](isae-ffwt4-sources-20261106.md) expands its
tracked scope to **200/8,000 at 5%** across all 40 archived histories. The
existing fixed-wing score is 200/1,600; repeated refinements add no targets.
All five drivers are paired to their explicitly selected models and outputs.
The original audit rejected two out-of-range weight attachments in each
Flare10/20/30 PM2 model. Qualified rigid-pylon handling now permits loading;
4,800 native values remain uncomputed and native semantics remain unresolved.
Removed's 1,600 values and the other 1,400 fixed values remain uncomputed.
Resolve native attachment behavior without moving weights or substituting
models; preserve Flare20's explicit 16° sideslip. Fifteen source tests pass.
Implement shared registration after retaining these source qualifications.

The [rigid-extension study](isae-ffwt4-rigid-extension-20261106.md) now passes
44 checks covering explicit-extension section loads, steady Schur matrices
and the finite-BDF limitation, in body and lifting-surface charts. Do not
repeat the completed synthetic mechanics proof as missing work. The
[integrated comparison](isae-ffwt4-rigid-time-20261106.md) now completes six
single-axis vacuum histories with 140 accepted steps and no rejection. Both
representations converge to the exact oscillator; finest errors are below
0.0577%, and all 12 individual-point motion gates pass at 0.1%. The literal
rejected objects have zero CDA, volume, spin and intrinsic inertia. The
[continuous dynamic-matrix comparison](isae-ffwt4-rigid-dynamic-20261106.md)
now closes the velocity/acceleration matrix gap: ten cases, 30 separate
full-inverse checks and 24 reference-formula tests pass. The
[production implementation](isae-rigid-attachment-production-20261106.md)
now loads the literal PM2 models with source records and physical positions
preserved, and records its qualified endpoint policy in saved-state identity.
Attachment/null-object and station/wall tests pass 84 and 44 checks; both time
formulations pass checkpoint tests and 21 built-browser checks pass. Next
establish coupled PM2 equilibria/histories and check general 3D integrated motion.
The first literal Flare20 preflight (55 nodes, beta 16°) hit its 150-second
limit. The [startup follow-up](isae-ffwt4-startup-20261106.md) now avoids that
rank rebuild using the existing equilibrated mechanical block at the same
1e-10 gate, and supports the source moving-airflow first-load predictor.
The complete source Newton matrix now includes direct load/circulation blocks
and moving-field geometry; source beam compatibility remains in physical
residual probes. First-load startup is 4.3–8.0 seconds and a loaded full matrix
is 8.65 seconds in retained runs; 52 rank/predictor and 27 matrix/network tests
pass. That 150-second attempt ended after starting eleven load attempts.
The [serial-continuation implementation](isae-ffwt4-continuation-20261106.md)
now completes the coarse literal Flare20 equilibrium in six jobs: 17 accepted
steps, no rejected attempts and rebuilt residual 4.608e-13. All 40 focused checks
pass, and every checkpoint join and saved physical state is audited. The built
browser passes 32 checks, including a worker reload, exact final-state parity
and the first accepted literal Flare20 load step. Refine
this equilibrium to driver-relevant meshes, establish Flare10/30 equilibria,
and then compute PM2 gust histories; all accuracy gates and native counts
remain unchanged.
General point-airflow support remains required. Exact finite-step equivalence is
contradicted by the prescribed-history BDF probe; native attachment handling
remains unknown. No new native pass is claimed.

The [Flare20 nested-mesh study](isae-ffwt4-pm2-mesh-20261106.md) completes
107 nodes in seven jobs and 17 accepted load steps, without rejection. Its
rebuilt residual is 9.65e-13. The root moment changes 0.0448% from 55 nodes,
passing the existing 0.1% gate, while hinge/other-field convergence remains
open. The earlier 211-node run timed out in the full unloaded rank fallback. A
bounded SVD diagnostic of its cached mechanical block gives 8.17e-11,
below the unchanged 1e-10 gate. Increasing the dense-size cap alone would
not certify it. The subsequent conditioning study preserves the failed
attempt and all physical/numerical gates.
A read-only 300-update norm-scaling diagnostic of that same physical block
passes the rank gate at 1.57e-10 (its separate norm-convergence target is not
met). This motivated the production follow-up below; the original diagnostic
study itself changed no production kernel.

The subsequent [rank implementation](isae-ffwt4-rank-refinement-20261106.md)
passes 66 native tests, including mechanism/redundancy rejection. The 211-node
case now has two accepted load steps with fresh residuals below 7.80e-13,
using the same physical equations and rank gate. All 29 built-browser checks
pass, including a full page/worker restart and native-state agreement.
The [subsequent 211-node chain](isae-ffwt4-pm2-211-20261107.md) completes full
load in 17 steps, with zero load rejections and rebuilt residual 2.06e-13.
One process timeout with a complete output boundary is independently audited
before resuming; all nine later one-step jobs exit successfully. The
107/211-node comparison passes 0/7 numerical mesh gates: root moment changes
0.195%, and per-beam displacement/finite rotation changes 0.108–0.236%, above
the 0.1% limit. Investigate this mesh sensitivity and refine further before
claiming resolution or completing PM2 histories. Twenty-one new audit/field
tests pass; element/circulation fields and historical qualifications remain.

The [joint-aerodynamic study](isae-ffwt4-joint-aero-20261107.md)
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

The [frozen-matrix 211-node refinement](isae-ffwt4-frozen-211-20261107.md)
now completes **19 accepted steps in 19 successful serial jobs**, with zero
rejection and maximum rebuilt residual **8.05e-13**. Its initial native
moment error is **0.5344%**. The 107/211 pair passes **1/7 mesh checks**;
six changes remain **0.122–0.153%**, above 0.1%. The earlier frozen 55/107
pair's 3/7 result remains recorded; its passing root-moment check did not
persist on refinement. Historical K/F remains unauthenticated, and full
histories remain uncomputed. Further mesh/field verification and gust histories
remain required. Native coverage stays **200/8,000**.

The [source-tree startup implementation](isae-source-tree-production-20261107.md)
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

The [circulation-finish memory fix](isae-circulation-finish-memory-20261107.md)
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

The [FFWT-4 full-history refinement](isae-ffwt4-spatial-time-20261106.md)
has reached 1,162/1,592 accepted steps on 159 nodes through 2.164225 s.
All 146/146 reached native values pass at 5%; median/max error is 0.763%/0.893%.
There are no rejected steps, failed process jobs or excluded attempts in this
history. Finish its remaining 430 steps, then complete the planned 287-node
time pair and compare spatial/time accuracy at the unchanged 0.1% gates.
The full-history accuracy verdict remains open; repeated native values add
no coverage beyond the previous complete 63-node history's 200/1,600 fixed subset (200/8,000 full archive).
The full-history field comparator has 59 passing focused checks, including
15 new tests preserving the original native-time gates alongside denser-time
gates. It refuses to promote an incomplete history to an accuracy pass.

The [FFWT-3 source audit](isae-ffwt3-sources-20261106.md) supersedes its earlier
unregistered status: 27 jobs now retain 35,256 native values and 1,206 missing
reference slots, all blocked. All six literal models have out-of-range joint
stations; neither a documented native clipping convention nor an alternative
model was recovered. One time grid differs and two files lack a counterpart.
Current unregistered families are P-3, P-4, P-5, AE-7, FFWT-2, FFWT-4 and FFWT-5.
Priority remains zero-pass scopes at 5%. FFWT-4 now passes all 200/200 values
of its first fixed-wing history, or 200/1,600 across all eight fixed histories;
this covers the gust and decay through 2.9651 s. The completed
[eighth-step study](isae-ffwt4-eighth-step-20261106.md) has at most 0.681% native
error and now passes both strict root-moment time-accuracy gates. The latest
adjacent gust-increment change is 0.0373%, below 0.1%, resolving the preceding
0.113% failure. All 797 common ticks and 200 native ticks pass; all 1,592
physical steps converge without rejection. The
[initial spatial study](isae-ffwt4-spatial-20261106.md) now passes 3/3 at
159/287 nodes, including displacement and small rotation vectors. The original
63-node initial root moment differs from the finest by 0.221%. Next establish
full-history spatial accuracy and time accuracy on the refined mesh, check
remaining state fields, add other histories and implement shared registration.
Repeated targets count once. The original coarse time step remains insufficient.
No physics parameter is fitted to a reference value. The new
[progress tracker](isae-progress.md) records future fraction changes in UTC.

The [FFWT-2 full-startup/aerodynamic follow-up](isae-ffwt2-history-refinement-20261106.md)
completes 408 dt=.005 steps without rejection or job timeouts. Native agreement
stays 5/25 computed, with acceleration/bank/tip channels at zero. Full-history
time refinement passes only 1/5 accuracy gates; it is not converged. Independent
instantaneous aero checks now pass 27 snapshot records, and eight quadrature
reference tests pass. Their sampled Cl is at most 0.3900, without stall.
Do not repeat these bounded mechanics/aero arithmetic audits as missing work.
Remaining FFWT-2 work: finer full-history time/mesh studies, historical startup
and vortex conventions, later rows/models, and shared registration. The next
actionable zero-coverage family is FFWT-3, whose archive retains model, driver
and output files starting at t=0; bind forcing and measurement contracts first.

The [FFWT-2 mechanics/refinement audit](isae-ffwt2-mechanics-20261106.md) checks
all 204 saved jig-start states and passes seven independent reference tests.
Four new local time grids accept 120 steps; the finest pair passes all five
accuracy gates, while native agreement remains 5/25 and acceleration/tip
channels stay at zero. Next: refine the full startup history and independently
check aerodynamic loads. The mechanical bookkeeping and sensor conversion
audits are complete for their stated scopes; do not repeat them as pending work.
Eight cached historical trees contain identical selected source triples.

The [FFWT-2 startup audit](isae-ffwt2-startup-20261106.md) now tests a separate
jig start and the original second time-command restart through 2.04 s. Both
jig alternatives pass 5/25 computed values at 5%; acceleration and tip angles
remain at zero passes. Sensor-output conversion agrees independently to
roundoff; all 12 assessment tests pass. These alternatives do not replace the
earlier equilibrium-start 10/25. Next priority is an independent dynamics audit
and temporal/spatial refinement; do not choose or fit startup from output error.
Original initial state and the constraint preset remain unknown.

The [FFWT-2 time-matrix follow-up](isae-ffwt2-time-tangent-20261106.md)
reaches 2.04 s and adds the first 10/25 computed matches at 5% (10/4,005 across
the selected table). Exact mechanical columns reduce full-matrix cost with
strict result parity. Next: investigate the zero-pass acceleration/tip-sensor
channels, recover the final original constraint preset and startup, extend the
history, refine time/mesh, and register the family. FFWT-2 remains one of eight
families without a shared adapter. Missing-reference scopes remain separate
from numerical failures; the default native allowance is 5%.

The [ST-4 directional check](isae-st4-directional-actions-20261104.md) finds no
derivative-step error large enough to explain three sensitive mode discrepancies.
Four formula tests and two full-residual probe jobs complete; no eigenvalue solve
is repeated. Spatial refinement and historical settings remain open.

The [ST-6 symmetric fixed-fixed supplement](isae-st6-fixed-fixed-20261104.md)
adds nine passing discrete-reference cases and four passing final pole/mesh
comparisons. Fine pole errors are 0.0082–0.0314%; the critical bracket center
differs from Euler by 0.01785%. The coarse 0.1256% continuum failure and failed
execution attempts remain recorded. Native scope stays zero. Antisymmetric
modes and the experimental fixtures remain outside the verified scope. The later
[Newton load-step correction](equilibrium-load-step-20261104.md) adds three fresh
analytical cases and two fixed-fixed browser cases, and resolves the repeated
cold-equilibrium iterations without changing physical equations or tolerances.

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

<!-- UA2-THEN-ST1-ST6-PRIORITY-20261103 -->
User priority (2026-11-03): finish sufficient **UA-2 validation**, then test
**ST-1 through ST-6**, in order, using small serial jobs with one BLAS thread.
Finish and publish the already-running UA-1 browser verification first.
For UA-2, distinguish independently verified equations and numerical convergence
from agreement with archived ASWING results; unresolved native provenance must
remain explicit. Record the evidence and remaining limitations before moving on.
The transition to ST is based on the UA-2 physics and numerical assessment;
separate interface/storage improvements do not delay this requested sequence.
For each ST family, review the original models, drivers and output coverage,
run the supported cases, and update [ISAE_STATUS.md](ISAE_STATUS.md) with
passing/total counts, typical error percentages and specific unavailable checks.
Existing ST counts are historical baselines, not fresh verification. ST-6 has no
identified archived ASWING target; analytical checks must be labelled separately.
<!-- /UA2-THEN-ST1-ST6-PRIORITY-20261103 -->





UA priority and rows updated 2026-11-01; the other detailed counts below are the historical 2026-10-28 snapshot. Use [ISAE_STATUS.md](ISAE_STATUS.md) for current steady counts and tolerances. This backlog covers all **41 present families**, including remaining variants and outputs inside registered families. The target is the archived tested ASWING calculations; experimental agreement is optional. SA-9 is absent from the pinned collection.

All six broad baseline batches are terminal. The [new FFWT/ST-4 follow-up](isae-suite-followup-20261026.md) retains separate current-kernel outcomes and verifies the startup/station fixes. Detailed execution and reference results are tracked by the [suite report](isae-suite-current.md) and [completed-batch receipts](isae-suite-readiness/completed-batches.json). Registration and completed computation are distinct from reference agreement; none of these selected scopes establishes whole-family reproduction.

The frozen inventory contains **279 original models**: 278 inside the families and one supplemental input. Import preflight accepted 212 and rejected 67. **Sixteen registered adapter types cover selected scopes in 26 families**, with executable scopes in 24; **15 families still have no adapter**. The [current source-only registry](../../artifacts/isae/sa6-postprocessor-pairing-20261028/registry.json) contains 4,043 jobs and 66,682 required scalar slots. This includes prepared ST-2 modal jobs and eight blocked SA-13 figure series; registration does not establish execution or agreement. The [new ST-2/AP-1 batch](isae-suite-st2-ap1-20261026.md) is terminal: six computed header jobs and 31 unsupported records, 78 numerical values and zero strict matches. The earlier broad baseline and SA-11/SA-12 batches retain their own kernels and outcomes. These accounting totals are not validation percentages. AP2 registration adds 237 jobs and 248 scalar slots: 234 executable mesh jobs and three blocked TXT exports. Its batch outcomes are recorded separately; this backlog makes no new whole-family pass claim. AE1 now adds 200 registered jobs and 1,200 slots: 196 worker jobs and four unknown-initial-state jobs. The [complete bounded AE1 batch](isae-suite-ae1-20261027.md) finished all 200 jobs: 196 computed and four blocked. It returned 1,176 valid scalar values and 98 strict matches, representing 49 distinct original sensor-X cells; no complete six-channel row matches.

The AE1 batch took 474.080366898 seconds. All 196 started processes were reaped, and each computed job passed all 29 required physical checks (5,684 checks total), with one cold solve and one fresh residual per job and no retries. Its 24 unavailable slots retain both unknown initial states at both meshes. The independently validated [combined AP2+AE1 summary](../../artifacts/isae/ap2-ae1-summary-20261027/summary.json) covers 437 jobs on the same 123-module kernel: 1,448 required slots, 1,418 numerically valid values, 98 strict matches and 30 unavailable slots. This selected summary is separate from the current 4,043-job global registry and from earlier batches on their own kernels.

The [complete AE-3 batch](isae-suite-ae3-20261027.md) adds 50 jobs and 725 required slots. All 12 coefficient states compute in 66.68 seconds with 348 physical checks passing; 38 blocked/inventory records preserve the rest. Its 50 scalar matches represent 25 distinct cells, including 24 zero-reference cells. No complete six-coefficient state matches. All 576 native and 113 separately qualified embedded source cells remain visible; only the finite coefficients repeat on two meshes.

The [complete ST-1 batch](isae-suite-st1-20261027.md) finishes all 37 jobs in 56.53 seconds: two computed and 35 unsupported records. All 52 physical checks pass, with one cold solve and one fresh residual per mesh and no retries. Six positions are numerically valid; only nominal-100 X/Y match their printed intervals. All 194 unavailable slots remain in the denominator, and no complete three-channel state or family matches. The exact unchanged model retains its undefined sensor triad, while body-anchor positions are independent. Current parsing accepts this model losslessly; the nine other ST-1 models still report `Line 60: engine is missing End.` Historical NODE arrays, gravity/pose startup and producer identity remain qualified.

[Machine backlog](isae-suite-backlog.json) lists every original model, current import diagnostic, candidate output and driver path. Current import records come from the [frozen ST-1 default catalog](../../artifacts/isae/default-plan-st1-20261027/catalog.json). Supporting historical evidence: [import preflight](isae-suite-readiness/catalog-preflight.json), [registered scopes](isae-suite-readiness/adapter-scopes.json), and [additional aerodynamic readiness](isae-suite-readiness/next-aerodynamics.json). The last audit predates adapter registration; its source findings are retained while the backlog uses the later registered scopes.

**Current user priority: fix zero-pass and uncovered scopes, allowing 5% native-reference error.** Use [ISAE_STATUS.md](ISAE_STATUS.md) for current scores and adapter coverage. The numerical registry totals, priority numbers and strict scores below retain their historical scopes; they are not a new full-suite assessment at 5%. Earlier UA and structural investigations remain documented. “Setup known” means the listed commands or source facts are recoverable, not that the producing executable’s complete startup state is known.

| Priority | Family | Current scope and remaining gap | First implementation step |
|---:|---|---|---|
| 1 | **SA-2** | 10/10 registered solves compute, 0/70 checks match. Finer-mesh CD is 5.23–10.75% low. Force normalization and saved-force arithmetic checks pass; K=40 and endpoint-force source reviews do not resolve drag. | Investigate independently supported differences in force integration and historical circulation/sampling settings. Retain the source-reviewed bound velocity; do not repeat completed arithmetic, K=40 or endpoint substitution diagnostics without new evidence. |
| 2 | **SA-3** | 44/44 registered solves compute, 0/308 checks match. Finer-mesh CL differs by 0.097–0.118%, CD by up to 1.75%. Independent Eqs154–158 geometry reconstruction is complete and relevant code unchanged. | Retain historical NODE, circulation and spline-endpoint qualifications. Seek independent source/operator evidence for the remaining difference; the completed force/control-point reconstruction is not a pending task. |
| 3 | **SA-4** | 84 jobs, 588 slots, 0 strict matches. Baseline had seven failures; the source-equation-preserving fallback recovers one. A bounded 20-attempt incidence study recovers no further registered target. | Preserve the six remaining failures and physical guards. Further continuation work needs a new supported mechanism rather than an increased retry budget; no repaired geometry or relaxed Mach criterion. |
| 4 | **SA-5** | 24/24 solves compute; 24/168 checks match after the profile-force first-moment correction. Four new Cm matches are duplicate zero-incidence rows at two meshes; four undefined efficiencies remain unavailable. | Resolve the historical treatment of same-beam sharp-junction bound induction. Saved-field Biot-Savart reconstruction isolates the opposite-leg contribution; its integrated lift is conditionally logarithmically singular for nonzero junction circulation. Further mesh refinement or a fitted core is not a supported correction. Preserve the verified profile moment and all original targets. |
| 5 | **SA-6** | Static: 88/528; conditional F1: 88/528; state: 528/3,168, all matching only zero side-force channels. Separate mass scope: original 1,740/2,904; saved-only validation replay 1,760/2,904, including 440 nonzero apparent entries. No complete row matches. The completed influence diagnostic changes no registered score. | Test the source-box endpoint-acceleration/physical-midpoint identity, then assess consistent apparent-acceleration consumers; retain the current kernel baseline and original targets. General quadrature/exporter identity and three spanwise pairings remain unresolved. Do not select NODE by fitting. |
| 6 | **SA-7** | The current-file scope retains 116 jobs, 812 slots and 0 matches. The separate opt-in historical fore-wing pairing now completes all 58 jobs with 406 finite valid outputs, 522 passing numerical checks and 0 strict matches. It reuses 203 native cells; 21 negative-drag rows and unverified historical startup remain unresolved. | Use the completed 29-incidence historical polar to investigate remaining force/exporter and stall-region differences against independent source equations and settings evidence. Original model recovery and full-polar source binding are complete; do not repeat endpoint-only reconstruction or rename-and-rerun diagnostics. Preserve the current-file scope and negative archived drag. |
| 7 | **SA-8** | 72 jobs, 504 slots, 0 matches. Original airframe/fore inclusion and qS normalization are verified by the SA6–SA8 source audit. Per-surface outputs and high-angle differences remain open. | Use retained row results to investigate source-equation or historical-setting differences; avoid repeating the completed model-inclusion/normalization audit. Bind per-surface outputs before adding targets. |
| 8 | **SA-10** | Current complete scope: **1,610/2,268 at 5%**; 269 valid states, one local-Mach rejection and 54 original attachment blockers. Faster LU/Newton correction removes the reproduced timeout without changing physical predictions. Five allocation failures are retained with declared isolated reruns; serial batch cleanup prevents recurrence. | Deferred at the user's request; post-stall repairs are not the active priority. Keep all original joints, signs, source settings and local-Mach gates. See [current report](isae-sa10-focus-20261107.md). |
| 9 | **SA-11** | All sixteen original polars: **163/9,184 at 5%**; 47 valid states, 281 local-Mach rejections, 984 unavailable requests. Failed CL/CD/CDi median errors are 7.54%/11.92%/14.88%. All 328 executable requests freshly run with unchanged outcomes. Expanded coverage adds original winglet input and overlapping normalization blockers. | Active focus: pre-stall winglet-junction velocity and section-force sampling, with original input/setup reconciliation. Retain safeguards and every unavailable target. Native discretization/startup and report/file twist remain unresolved. See [current report](isae-sa11-complete-scope-20261108.md). |
| 10 | **SA-12** | Dedicated adapter: 1,020 jobs, all 510 original rows and 4,080 required slots; ground flag/normal/height/pose are forwarded and independently checked. All 1,020 jobs complete; 4,080 scalar outputs are valid and 52 match printed precision. Historical Euler pitch remains unknown; pitch=alpha is conditional. | Review all outcomes and mesh differences, preserving raw CD/CDi and every row; resolve source-equation or historical-setting discrepancies without fitting. |
| 11 | **SA-13** | Eight registered figure series, 612 blocked slots: 239 finite original-discretization values, 237 finite modified-ASWING values, 136 gaps. Historical radius derivative uses backward differences; current spline derivative is consistent with the continuous equations, but exact discrete details and original models/settings are missing. | Recover independently attributable body/derivative inputs and run/sensor settings. Do not infer the missing radius multiplication/stencil placement from the backward-difference label or fit conditional outline models to the targets. |
| 12 | **SA-14** | Registered: 360 jobs, 360 required slots; 360 executable jobs. Of 360 raw-CL jobs, 325 computed and 35 failed the local subsonic guard; all 35 are on the n128 grid. Those failures remain required targets. The 426 span-export rows, fuselage-only model and non-CL outputs remain outside the adapter. | Diagnose the saved local-flow growth and source geometry/force sampling while retaining the subsonic guard and original parameters. Separately decode and pair the span tables before adding their section outputs; preserve the unpaired body-only model. |
| 13 | **SA-15** | 26 jobs, 182 slots, all blocked. Stability coefficient rotation is specified by Eqs218/224/225, but the R5.98 exporter and build-dependent .set startup remain unresolved. Driver gives speed380 and 13 incidences only. | Add an explicitly framed coefficient-conversion helper when enabling the adapter; do not copy body Cl/Cn directly as stability coefficients. Recover authoritative .set layout/settings or matching .pnt/.con before declaring the flight state known. |
| 14 | **P-2** | [Recovered primary inputs](isae-p2-recovery-20261105.md): four registered declared jobs, 312/312 archived CT/efficiency values pass at 5%; maximum error 0.633%. All 48 forward CP rows and four static CP rows identified. Measurement-only quadratic calibration reproduces all twelve printed coefficients; all CT/eta pairs bind to primary CP. | Preserve the qualification that the exact original regression/driver is absent. Retain literal-rounded-input diagnostics and strict differences. Independent power, wakes, aircraft coupling and the report's variable-CdA extension are distinct scopes; do not call the whole family validated. |
| 15 | **P-4** | No registered adapter. Twenty ASW jet-model curves are decoded: 2,000 scalar slots, ten axis NaNs. These are MATLAB model reproductions; independent power/density/CdA and the second propeller identity remain unresolved. | Resolve the DA4002/APC identity conflict and recover independent component inputs. Preserve decoded curves separately from experiments and ASW-m variants. |
| 16 | **P-5** | No registered adapter. Sixteen ASW sensor-bench curves are decoded: 1,600 slots, eight axis NaNs. Power/density/CdA, advance-flow and sensor conventions remain unresolved. | Recover the independent P5 GWS bench inputs first. Output-derived freestream candidates cannot substitute for known driving conditions; preserve all 800 GWS slots. |
| 17 | **P-3** | [Source audit](isae-p3-readiness-20261027/report.md): 84 finite ASWING-labelled scalars across 28 conditions and three channels (CN, Cn, CT); separate experiment and Leng-BEMT series each contain 84 scalars. No model, driver, producer or raw export is retained. No adapter or scalar slots are added. | Recover independent CP/power, speed/advance convention, RPM/density/scale, blade inputs and force/moment normalization, signs and origin before declaring a component comparison. Original print precision remains unknown; do not infer inputs from the target curves. |
| 18 | **ST-1** | Registered: 37 jobs, 200 slots from 197 native scalars across 27 files and all ten models. Two static jobs compute six positions, with two coarse-grid matches and no complete state match; 194 slots remain blocked. All 76 complex roots, including 25 real-only roots, remain required. One model imports; nine retain missing Engine End errors. Additional arrays and plots remain outside this denominator. | Preserve both mesh outcomes and qualified setup. Resolve original grammar, modal settings and output pairing before extending the other nine models; retain surplus scalers and undefined sensor triads without repairs or selected-frequency substitution. |
| 19 | **UA-1** | 148/148 harmonic, 12/12 linear phase, four zero-incidence periodic and the earlier first-cycle checks pass. The [inclined periodic refinement](isae-ua1-incidence-periodic-refined-20261101.md) passes 1/1: 9°, k=.94, A/c=.5, fine lift/circulation/rate errors 0.0172%/0.0339%/0.0150% at 320 steps/cycle. It resolves the recorded 160-step circulation failure (0.1273% versus the unchanged 0.1% limit), with production equations unchanged. All 3,842 comparison snapshots are audited. The 96 instantaneous-state checks remain passing. | Extend remaining periodic frequencies/amplitudes and 5° histories at k=.94. Preserve full forcing, BDF predecessors, fixed-axis lift and motion diagnostics. The one inclined periodic case does not establish spatial convergence or stall behavior. Native provenance remains unresolved. The [built-worker follow-up](isae-ua1-incidence-periodic-browser-20261102.md) closes runtime coverage for the refined 9° case: 14/14 gates, 2,561 states and zero rejected steps. Broader physical conditions remain; the current stalled supplement is linked above. The [5°, k=0.47 study](isae-ua1-periodic-a5-k047-20261102.md) has 14/14 gates passing on two time grids and passes overall; 3,842 states audited. Browser coverage of this condition remains pending. The [UA-1 stall/lag supplement](isae-ua1-stall-20261102.md) adds **72/72 passing instantaneous states** on two meshes. The first-cycle time study **passes**: **11/11 gates pass**, with fine lift/circulation/rate/pressure-drag errors **0.00868% / 0.00724% / 0.03068% / 0.02780%**. All 1,123 states on 160/320/640 steps are audited. The declared ±1.5 section limits exercise stall; they are supplemental settings, not recovered native UA-1 inputs. Production equations are unchanged. The repeated-stall comparison is reported below; Current UA-1 browser stall coverage is linked above; UA-2 stall and native agreement remain unfinished. The [source time-matrix improvement](isae-ua-source-mechanics-20261102.md) uses exact endpoint-average derivatives for internal loads and reactions. All **13 Python tests** and **4 browser-reader tests** pass. A retained 40-step stalled segment uses 450 rather than 612 matrix-building residual evaluations; median solve time falls **10.6%** across three paired runs. The built worker passes a 16-step continuation comparison after correcting a retained signed-zero verifier failure; maximum scaled Python difference is **1.57e-9**. Physical equations and tolerances are unchanged. Scientific case counts are unchanged; the four-cycle stalled periodic comparison is reported below. <!-- UA1-STALLED-PERIODIC-20261102 --> The [UA-1 repeated-cycle stall study](isae-ua1-stall-periodic-20261102.md) **passes all declared gates**. Completed grids audit **3,842 states**, **158 BDF continuation boundaries**, with zero rejected steps. The finest completed fourth-cycle lift/circulation/rate/pressure-drag errors are **0.01688% / 0.01152% / 0.03332% / 0.06629%**. Its fourth/third-cycle change is at most **0.000019%**. Physical equations and tolerances are unchanged. This adds one supplemental equation-based case; Native stall agreement remains open; current browser verification is linked above. A retained fine-grid job timed out while saving its history; recovery uses 20-step jobs with the same physical grid. <!-- /UA1-STALLED-PERIODIC-20261102 --> |
| 20 | **UA-2** | 222 native slots remain blocked. Zero-incidence coverage retains 16/16 first-cycle, 8/8 mesh, 2/2 periodic and 1/1 periodic mesh passes. Inclined coverage retains 64/64 instantaneous, 2/2 first-cycle and 1/1 first-cycle mesh checks. Inclined periodic coverage now passes 2/2 meshes at one condition, plus 1/1 periodic mesh check. The [40-strip follow-up](isae-ua2-incidence-periodic-n40-20261101.md) passes 18/18 gates at 9°, k=.95, A/c=.5: periodic lift/circulation/rate errors 0.003787%/0.008447%/0.003477%; cold/periodic mesh changes 0.043245%/0.049512%, below 0.1%. All 5,281 new snapshots and checkpoint joins are audited. All 330 jobs converge without rejection; production and limits are unchanged. Earlier 20-strip time-refinement results and retained failed attempts remain recorded. The [eight-cycle built worker](isae-ua2-incidence-periodic-browser-20261101.md) now passes 1/1 runtime checks and all 17 accuracy gates: periodic lift/circulation/rate errors 0.003787%/0.008446%/0.003477%, with all 5,281 snapshots audited in 42 batches. The original terminal cutoff-verifier failure is retained; corrected assessment uses the saved output with unchanged physics and tolerances. Ten focused verifier tests pass. | The [time-plot follow-up](isae-ua2-time-ui-20261101.md) removes measured per-selection curve rebuilding: 5,281 scalar samples remain, median plot-only scrub falls from 58.5 to 1.4 ms, and complete 17-state actual-app replay/export passes. The [storage audit](isae-ua2-history-storage-20261102.md) now measures 4.22 GB of snapshot JSON, with the 64 MiB limit crossed at 84 states. Exact metadata sharing passes all 330 segments / 660 endpoint checkpoints and 33-state UI continuation/export. The [chunked archive proof](isae-ua2-history-archive-20261102.md) preserves all 5,281 states / 660 checkpoints exactly in 252.5 MB; standalone Chromium verifies the entire persisted file after reload and reads every physical chunk. All 36 focused tests pass. The [workbench follow-up](isae-ua2-archive-ui-20261102.md) now checks the full physical history with indexed lift, complete selection/playback and a physical Earth-Z scan; small archive save/open/continuation, distribution exports, JSON projects and runtime Undo load pass. All 66 focused tests pass. Separate interface backlog: durable large-project attachments and automatic segment storage with transactional references, reload recovery and persistent undo. Unindexed scans remain costly; no physical states are omitted. Current priority is to assess the remaining UA-2 frequency/incidence/amplitude evidence, state its limits and then test ST-1 through ST-6; interface work does not gate that sequence. Arbitrary-model time-step accuracy and native provenance remain unfinished. The time-plot change leaves all 136 scientific solver modules unchanged. Neither UA family is complete. |
| 21 | **AE-4** | Declared sweep advances to **705/1,200** at 5%; selected 705/756, 728 paired, 23 mismatches, 16 unmatched, 12 unknown initial and 444 unrun. New [40–43 m/s batch](isae-ae4-40-43-20261113.md) passes 48/48; largest native error 0.664%. Mesh checks pass 16/24. | All integer 40–108 m/s points now have runs on both registered meshes, while 103 m/s pairing remains open. Both middle-pair components fail the mesh gate at each new speed. Earlier first-crossing growth-rate and 79 m/s frequency failures remain; native damping still disagrees at 96 m/s despite a passing independent full-pencil audit. Next fill 36–39 m/s with unchanged inputs, gates and caps. Preserve native settings, mode identity, spatial convergence, wall/frame support, 9,480 historical components and later branches/time histories. |
| 22 | **AE-5** | [Registered source ledger](isae-ae5-sources-20261105.md): 0/587 blocked (532 modal components, 55 ASWING boundary values). Driver has 22 speeds while export has 29 modal points. Literal GJ=8000/EInn=2.5 disagree with report 1.2/18499; pre-rename files are identical. One unchanged literal case solves in 14.15 s with all 16 full-matrix modal checks passing, without a native comparison. | Recover authenticated model and operating-point correspondence, retaining both boundary datasets. Alternate source has an unterminated Engine block. Any report-based reconstruction must be a separate declared bench and must not tune inputs to match eigenvalues. |
| 23 | **AE-6** | The [source-density correction](isae-ae6-density-20261105.md) fixes three configurations' input air. Eight fresh jobs pass 116/118 computed components: c/d pass both meshes and e/f pass their first coarse comparisons. Only a's lowest frequency fails. All 41 focused tests and the independent full-matrix audit pass. | Weight7a slow frequency, mesh convergence (18/44 so far), fine e/f grids and 6,564 unrun declared slots remain. Weight0 has 1,200 blocked slots. Preserve ST-4 duplication and superseded wrong-density evidence. Full sweeps, historical settings, other positions and flutter onset remain open. |
| 24 | **AE-7** | No registered adapter. Nonlinear aeroelastic time initialization, forcing/continuation, sample times and limit-cycle reduction are not yet paired to a current adapter. | Choose one intact driver/time-export pair, recover its base state and exact sample/forcing schedule, and verify the coupled time route before comparing amplitude or frequency. |
| 25 | **FFWT-3** | Registered source-only: 0/36,462 slots, including 35,256 native values and 1,206 missing-reference slots. All 27 jobs remain blocked; six models have out-of-range joint stations. | Resolve native attachment semantics or authenticated model correspondence; retain mismatched time grid and missing driver/output. Do not silently clip or rewrite stations. |
| 26 | **FFWT-4** | No shared adapter yet. The complete 63-node eighth-step Fixed-1 history passes 200/200 values (200/1,600 distinct targets), with median/max error 0.523%/0.681% and both adjacent time gates passing. Initial 159/287-node spatial checks pass 3/3. The [159-node history](isae-ffwt4-spatial-time-20261106.md) reaches 1,162/1,592 steps and 146/146 reached native matches, with maximum error 0.893% and native peak-time error 0.611%. The earlier step-842 state is independently confirmed outside the prescribed gust field. | Finish the 430 remaining steps and the planned spatial/time pairs on 159/287 nodes; use the version-2 field comparator retaining both original-output-time and denser-time 0.1% gates. Check remaining fields and other fixed/hinged histories, then register all original outputs. |
| 27 | **FFWT-2** | No shared adapter. Selected FFWT10/V15/DF21 trajectories reach 2.04 s: equilibrium start 10/25 computed matches; separate jig/restart 5/25, each with 3,980 further targets unrun. Independent sensor conversion and mechanics bookkeeping pass; 204 jig states audited, seven mechanical-reference and twelve earlier assessment tests pass. Four new local grids add 120 accepted steps; finest pair passes 5/5 accuracy gates but adds no native matches. | Refine the full startup history and spatial mesh; independently audit aerodynamic loads. Original startup/settings and report/model mass correspondence remain qualified; eight cached source trees reveal no alternate triple. Extend/register the full history without combining startup scopes. Retain 40 original import rejections without relocating sensors. |
| 28 | **FFWT-5** | No registered adapter. Exact tab/clean variant, incidence, base branch and flutter eigenvalue identification remain unbound; summaries cannot replace root histories. | Trace each Fig_5_14_Asw incidence table through its retained analysis script to the exact model and onset rule, then qualify a coupled modal sweep with original targets preserved. |
| 29 | **ST-6** | [Source review](isae-st6-readiness-20261027/report.md): **NO_ARCHIVED_ASWING_TARGETS_IDENTIFIED**. All 19 originals remain visible: 44 experimental rows, five MATLAB Euler curves and a modal schematic. Zero archived-ASWING targets or comparison jobs are justified. | Retain this source boundary. Reopen only with an attributable ASWING numerical export and its generating setup. Synthetic Euler regressions and experimental studies would have separate acceptance. |
| 30 | **AE-3** | Registered: 50 jobs, 725 slots. All 612 native comparisons compute: coefficients on two meshes, derivatives/mass/inertia/rates on nominal 80. Current frozen default gives 434 passes; 113 embedded targets remain source-blocked. | Audit the historical control and MM operating constraints using the full native comparison. Keep literal-model primary results, original ASWING, ASWING-m and qualified alternatives separate. Preserve the 725 targets and current 5% policy. |
| 31 | **AE-1** | [Completed bounded batch](isae-suite-ae1-20261027.md): all 200 jobs terminal, 196 computed and four unknown-initial-state blocks. All 100 original rows and six absolute outputs remain required at meshes 40/80: 1,200 slots, 1,176 valid, 98 strict matches and 24 unavailable. Matches are 49 distinct sensor-X cells; zero complete six-channel row matches. | Recover independent startup information and investigate retained source-equation/setup discrepancies without fitting. Preserve all initial rows, absolute Earth outputs, literal properties and historical-setting qualifications. |
| 32 | **AP-2** | [Registered source catalog](isae-ap2-reference.md): 237 jobs and 248 scalar slots; 234 executable mesh jobs cover all 117 MAT ratios and two endpoint CSV coefficient pairs. Three unpaired TXT outputs retain six blocked slots. Exact R5.92 exporter definitions and historical startup remain qualified. | Review full-grid results separately; recover exact CL/CD exporter semantics and independent TXT pairing. Keep stored-cell identity checks distinct from printed coefficient precision and preserve declared reconstructions. |
| 33 | **FFWT-1** | Current follow-up: 5/16 computed, seven later Jacobian flow-guard failures, four timeouts; 20 valid scalar outputs, zero strict matches. All eight mesh pairs unavailable. Source-rank proof now verified; other flare/incidence exports remain unregistered. | Diagnose the full source Newton/geometry derivatives and later convergence, preserving original equations, every row and the local-flow guard; then extend other archived variants. |
| 34 | **ST-4** | Primary published mechanics: 66/72 frequencies at 5%, all 24 configurations computed on both meshes. All 64 states and numerical gates pass; primary mesh changes <0.08325%. Direct native-export supplement now passes all 31 original frequency ordinals and 320 matrix checks on 128/192 meshes; it adds no primary votes. Separate named-mode check 54/72; original archive 93/3,749 retains 3,656 unavailable outputs. | Resolve unloaded inertia/input identity and three paper/source position correspondences. Recurring integration and the full native replay are complete; full paper replay remains pending. A source audit identifies mixed paper positions and a native/CSV conflict without replacing comparisons. Keep all six frequency failures, native mode identities/settings and airflow open. The modified unloaded diagnostic adds no primary passes. |
| 35 | **AP-1** | [New adapter and source engine support](isae-suite-st2-ap1-20261026.md): 26 jobs retain 15,470 scalar slots. Six positive-slope header jobs compute 78 values, none matching printed precision. All 1,001 span/operating rows remain retained; 20 records are blocked. | Resolve exact node/display sampling and translated one-sided resultants before full-row execution. Preserve literal zero lift slope and unpaired references; diagnose header differences from source equations without fitting. |
| 36 | **ST-5** | Sixteen static snapshots are registered (96,552 slots), representing all 24 complete original static triples. Four new elliptical cases: 13,583/25,920 qualified matches; 16/16 solves and final 56/56 mesh checks pass. [Evidence](isae-st5-elliptical-20261103.md). | Resolve roller/forward mesh failures and review modal/unpaired sources. Historical nodes, output precision and f_reac remain unresolved. |
| 37 | **ST-3** | Current primary mechanics: 84/86 published static ordinates and 9/9 modal frequencies at 5%. All readable targets, numerical and mesh/shape checks pass. The two clipped values stay required. Legacy registration remains 7 jobs and 1,098 slots; its static snapshot is separate and unchanged. | Integrate the new static scope into the recurring catalog. Preserve source torque scaling, both missing ordinates, qualified native startup/modal labels, and incompatible test.asw/test.txt torsion. Continue the mechanics sequence with ST-4. |
| 38 | **AE-2** | Registered: 550 jobs, 2,200 required slots; 526 executable jobs. All twelve sensor sweeps of the uncoupled and both coupled layups are included. The alleged A15 span export is an exact duplicate of an included sweep; no independent span data is present in the thirteen native text exports. Two extra models remain unpaired, one with an unterminated Engine block. | Open after handoff to AE-3: three unresolved conditions and twenty-two native mismatches. Exact sparse memory recovery is adopted and tested; full post-adoption replay and nonlinear convergence remain unresolved. The 5°/18 and 19 m/s fine-grid cold chains are independently accepted, retaining their native branch mismatches. Preserve the 96 unavailable values and all original outcomes. See the [source review](isae-ae2-supplemental-source-review-20261111.md). |
| 39 | **ST-2** | Current primary mechanics: 77/77 static ordinates and 14/14 modal frequencies under the declared setup. All 43 recurring jobs and 89 physical states complete successfully; combined reporting and 98 focused checks pass. Original 56/490 archive retained separately. An [eight-state attachment study](isae-st2-attachment-interpretations-20261109.md) verifies rigid-beam/pylon equivalence and distinguishes alternative extensions using native resultants. | Resolve native handling of active .558 attachments beyond the .55 endpoint without silently changing originals. Preserve the explicit static tip-pylon reconstruction, literal modal files and all unavailable archive values. Historical settings, legacy outputs and full-family compatibility remain open. |
| 40 | **P-1** | Registered: 6 jobs, 110 required slots; 6 executable jobs. Only isolated static CT at the supplied CP values is covered; independent power prediction, advancing flow and whole-aircraft coupling are not. | Audit the current six curve results and preserve CP as an input. Extend only to additional explicitly identified ASWING quantities whose driving inputs can be recovered. |
| 41 | **SA-1** | Registered: 22 jobs, 154 required slots; 22 executable jobs. All near/deep-stall failures and drag discrepancies must remain visible; sparse source coordinates are not a complete physical stall validation. | Paused at the user's request. Preserve the 19/154 result and unresolved differences; do not schedule new SA-1 work. |

The [ST-4 diagnosis](isae-suite-readiness/st4-tip-roundoff.json) confirms that decimal-equivalent tip stations differ by one binary64 ulp after scaling. This was established by parsing and required-station arithmetic only; no mesh, residual, or solve was run and no production fix is claimed. The [SA-6 preparation receipt](isae-suite-readiness/sa6-preparation.json) and its earlier batch are historical: 22 computed and 69 unsupported jobs, 132 finite values and 22 matches among 528 slots.

The [2026-10-28 SA6 batch](../../artifacts/isae/sa6-postprocessor-pairing-20261028/batch/report.json) completes the expanded static scope: 88 computed jobs and three zero-target inventories in 537.45 seconds. All 528 scalar slots are valid; the 88 matches are exclusively zero CY, and no complete six-channel row matches. All 1,056 numerical checks pass; the maximum recorded residual is 4.02434e-13 and all 88 workers are reaped. The [independent summary](../../artifacts/isae/sa6-postprocessor-pairing-20261028/summary/summary.json) and [saved-result analysis](../../artifacts/isae/sa6-postprocessor-pairing-20261028/analysis/summary.json) preserve all six coefficients. Eleven 35c states retain their shell binding; original MATLAB controls and exact Cl/Cn tokens support the other 33 states. Historical shell/startup, NODE and K/F settings remain qualified. The [remaining-output catalog](../../artifacts/isae/sa6-postprocessor-pairing-20261028/remaining-native-outputs.json) retains 3,300 additional native cells. All 264 F1 derivative cells, 1,584 state derivatives and 1,452 tensor entries now have separate conditional comparisons and explicit opt-in registered routes. The tensor scope distinguishes its original execution from saved-only validation replay, as recorded below. These scopes add no slots to the default static 528 and establish no whole-family pass.

The [conditional F1 batch](../../artifacts/isae/sa6-control-tangent-20261028/comparison/report.json) finishes all 88 analytic jobs and four independent finite-difference validation jobs in 501.11 seconds, with all 92 workers reaped. It retains all six channels at all 44 native states on nominal 64/128 meshes: **528 valid derivative slots from 264 distinct native cells**, with **88 matches exclusively zero CYdF1** (44 distinct cells). No complete six-channel derivative state matches. All four validation states pass coefficient and circulation checks at both fixed perturbation steps, 0.01 and 0.005 file-control units; production derivatives remain analytic. The [saved-only analysis](../../artifacts/isae/sa6-control-tangent-20261028/analysis/summary.json) independently checks 386 evidence pins, native precision, static-base equality, retained separation-wrench arithmetic and both finite-difference stencils, with no new solve. Its [roll/yaw figure](../../artifacts/isae/sa6-control-tangent-20261028/analysis/roll-yaw.svg) retains both meshes and every original sign. At the finer mesh, maximum relative roll-derivative errors are 5.63%, 5.70%, 12.00% and 15.08% for 15/20/30/35% chord; yaw errors are 31.72%, 33.06%, 38.04% and 40.45%. The largest mesh difference across all six channels is 0.443% when normalized by the larger absolute prediction, a descriptive difference rather than an error bound; the separate verifier uses mean magnitude and reports 0.444% after rounding.

The [literal-deck rigidity evidence](../../artifacts/isae/sa6-control-tangent-20261028/rigidity-evidence.json) establishes infinite stiffness under the original zero/omitted-stiffness convention. Elastic geometry response therefore vanishes for the same body anchor, fixed base, aerodynamic convention and mesh, and cannot explain these derivative discrepancies. Historical producer identity, global-frame constraints, derivative-response settings and aerodynamic NODE/K/F/startup remain unverified. The [analysis receipt](../../artifacts/isae/sa6-control-tangent-20261028/analysis/execution-receipt.json) also records the limitation that raw CP/HV fields were not retained: separation closure is independently replayed from saved six-vectors, while the formula itself is covered by source review and tests. The registered static result remains **88/528**; conditional derivatives stay outside its score and default static registry counts. Whole-family acceptance remains **0/41**, and **SA-1 remains paused**.


The [AE1 readiness audit](isae-suite-readiness/ae1-adapter-readiness.json) verifies all 100 rows and six sensor fields: 600 finite scalar values, including two initial states with unknown setup. Its literal zero-load Weight anchors at 0.558 lie beyond the beam endpoint at 0.55, but current exact null-point filtering now permits unchanged mesh/setup construction. Source records remain intact. Historical omission of those records is not an unchanged-input replay. The registered adapter retains all 100 rows at both meshes. Its bounded batch is now complete: 196 computed jobs and four blocked unknown-initial-state jobs, with no complete six-channel row matches. The same setup change supports both original ST2 modal models, while nonzero static Weight anchors remain invalid. No new modal comparison is counted.

Original import failures are preserved. Successful imports can still have attachment or setup errors: SA-10’s blocked tip-sail model is one example. Conversely, the older blanket singleton-stiffness/Jangle rejection descriptions for FFWT-3, FFWT-4 and FFWT-5 are stale: their 6, 9 and 7 current originals respectively parse. FFWT-2 currently has 13 imports and 40 rejections. These changes establish compatibility only.

Figures and summary spreadsheets remain candidates until their ASWING series, inputs and output definitions are established. The absence of a literal model is not automatically a blocker for a component comparison, and it does not authorize inventing one. Models with no proven reference target remain visible without requiring arbitrary solves.

Historical evidence is linked per family in the machine backlog and is not counted as a fresh pass. Unknown atmosphere, initial state, mesh, continuation, load conventions and startup settings remain distinct from missing algorithms. No coupled dynamic family is declared complete by the available vacuum or moving-frame implementation checks.

The [FFWT saved-result audit](isae-suite-readiness/ffwt-startup-regression.json), covering the first nine finished jobs, proves the prior row4 request and mesh were preserved and identifies the changed certificate guard and full-column fallback. That historical diagnosis is now followed by a separately proved and tested source-rank certificate in the new follow-up; later loaded-solver failures remain. The [completed-batch records](isae-suite-readiness/completed-batches.json) supply all 16 terminal outcomes: 10 timeouts and six initial-check failures.

The [completed ST-5/AE-2 expansion](isae-suite-st5-ae2-20261027.md) registers and executes the remaining ST-5 rigid 30 lb 80/20 snapshot and the two AE-2 coupled layups (eight sweeps, 184 rows). Their original model,
driver and export pairs are pinned in the [next original case pairs](isae-suite-st2-ap1-20261026/next-original-pairs.json).
The active priority is SA-11 pre-stall behavior; SA-2 stall-region work is deferred. Missing-family coverage remains queued for the 15 families without adapters; SA-1 remains paused. ST6 is a documented source boundary: its 19 originals contain experimental and analytical material, with no identified archived ASWING targets. It remains visible without inventing an executable adapter or acceptance denominator. AE1 has completed its bounded registered batch, with its output discrepancies and four unknown-initial-state jobs retained. P3 now has 84 identified ASWING-labelled scalar targets but remains outside executable coverage because independent inputs and normalizations are missing; the report does not establish these as MATLAB theory reproductions. The [AP2 source catalog](isae-ap2-reference.md) now retains all 117 MAT cells, both endpoint CSV coefficient pairs and all three unpaired TXT exports. Two endpoint sources remain byte-identical; the other 115 states are declared Engine-row reconstructions with unchanged non-Engine bytes. Original Cdp=.0045 and .005 remain distinct. MAT zero-tolerance checks concern stored binary64 identity, while endpoint coefficients retain native printed precision. The commented Var11/Var17 producer conflict and exact R5.92 CL/CD exporter definition remain unresolved. The current distributed-aerodynamic force mapping is conditional; no drag definition is substituted based on numerical closeness. Harder source/settings blockers remain visible. The [saved SA-12 diagnosis](isae-suite-st2-ap1-20261026/sa12-discrepancy.md)
shows that close-ground pre-stall drag differences cannot all be attributed to
post-stall settings. The swept-tip source review found no supported correction
to documented force-point sampling or same-surface core rules; those guards
remain intact.

The [state-derivative increment](isae-sa6-state-derivatives-20261028.md) completes all 88 analytic jobs and 24 perturbation workers in 532.54 seconds: 3,168 finite valid slots, 528 zero-side-force matches and no complete 36-value state match. All six columns pass both perturbation steps in four selected states; maximum coefficient error is 2.55e-8. Independent saved analysis verifies 765 pins and all original tokens, fixed-base maps, tangent/wrench arithmetic and perturbation stencils. The native/WASM witnesses agree within 6.92e-13 across 7,026 values; 115 numerical and 427 adapter/summary test cases pass across recorded final runs. The earlier checker failure is retained separately with all 20 started workers reaped; the corrected batch changes no numerical kernel or target.

The subsequent [state registration and influence diagnostic](isae-sa6-influence-linearization-20261028.md)
passes 485 focused adapter/runner/summary cases and one registered state job,
with 36 valid values, six zero-CY matches and all 13 numerical checks passing.
The `sa6-state-rigid` option adds 88 jobs / 3,168 slots in a separate ledger;
default static planning and earlier full comparisons retain their counts.
Eight selected diagnostic cases complete with all independent held-influence
perturbations passing. Current-base influence lagging reproduces all selected
sideslip zeros but yields no nonzero match; some incidence comparisons worsen.
The diagnostic is separate from registered scores and changes no kernel.

The state comparison exposes material sideslip mesh differences: maximum absolute change 0.00688908 in Cnb (14.78% relative to larger magnitude), and maximum relative change 92.21% in a small CXb channel. All original sideslip tokens print zero. The completed conditional influence diagnostic above explains the selected zero pattern but leaves historical exporter identity and nonzero disagreements unresolved; no convention has been selected by fitting. A separate original-output speed-scaling audit finds 50/264 pairs outside combined printed rounding bounds, with largest absolute gap 1.24e-4. These small consistency gaps do not explain the much larger nonzero comparison differences. All original targets and gates remain unchanged.

The separate [registered tensor batch](../../artifacts/isae/sa6-mass-tensors-20261028/batch/report.json) evaluates all 44 original files on two declared meshes: **2,904 finite slots from 1,452 distinct cells**, with zero aerodynamic or nonlinear solves. All 88 workers finish and are reaped in 382.60 seconds. The original report accepts 87 jobs, 2,871 valid values and **1,740 matches**; one job fails the adapter’s exact PSD-metric identity check after retaining its arrays. The original report remains unchanged. A [saved-only validation replay](../../artifacts/isae/sa6-mass-tensors-20261028/validation-replay/report.json) accepts all 88 jobs and 2,904 values with **1,760 matches: 1,320 real-tensor zeros and 440 nonzero apparent entries**. No complete 33-value row matches. The [independent saved analysis](../../artifacts/isae/sa6-mass-tensors-20261028/analysis/summary.json) passes all 22,410 checks and confirms 880 distinct cells match on both meshes. The replay performs no geometry/tensor evaluations or solves; it allows only binary64 roundoff in PSD-metric identity while retaining the original physical gate, numerical arrays, comparisons and printed precision. All 3,168 numerical checks pass. Final validation includes 23 tensor-math tests and 537 distinct adapter/summary cases; the earlier 531-case receipt remains historical. The production kernel remains unchanged at 129 modules.

The [tensor source audit](../../artifacts/isae/sa6-mass-tensors-20261028/source-audit.json) preserves physical twist of 4°, zero real mass and all 308 tiny nonzero apparent entries below 1e-8. Physical CG remains undefined; centroid-labelled tensors use the explicit archived (0,0,0) reference without inventing a CG. The [quadrature supplement](../../artifacts/isae/sa6-mass-tensors-20261028/quadrature-source-review.json) derives arithmetic-midpoint apparent inertia from endpoint acceleration loads and the source box equations for a straight, constant-property strip. It does not prove general variable-property quadrature or historical exporter sampling. The next task is that independent source-box discriminator, followed by consistency checks across apparent-acceleration consumers. The current baseline using Glauert midpoint sampling, original targets and default static **88/528** result remain intact; no NODE count or correction is selected by fitting.
