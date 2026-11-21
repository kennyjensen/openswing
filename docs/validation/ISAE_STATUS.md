# ISAE comparison status

Updated 2026-11-13. All 42 listed rows remain (SA-9 is absent upstream).
**Default native-reference tolerance is now 5%.** Numerical, equation, mesh and
near-zero absolute gates are unchanged. No whole family is declared validated.
Counts are scalar comparisons, not independent cases. Historical archive
scopes include mesh repeats; SA-11's primary paper-focused scope below does not.

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
The [adapter guide](isae-ae3-adapter.md) links the evidence and
replay commands. The one-thread **512 MiB /15 CPU /25 wall-second** limits are
unchanged. The complete
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

**Retained ST-4 results:** The [completed mechanics
comparison](isae-st4-mechanics-current-20261109.md) now matches
**66/72 published ASWING frequencies at 5%**, with median error 0.2028%.
The six failures span 5.556–19.703%, median 14.073%. All 64 physical states,
72 primary mesh/shape checks and 2,048 matrix checks pass. The primary scope
now compares complete three-frequency sets; the original named-mode rule
remains 54/72, and the historical 93/3,749 archive stays separate and intact.
This is an explicit scope/method change, not a production solver correction.
A source-backed unloaded-inertia diagnostic matches all three frequencies
within 0.327% but adds no primary passes. Remaining discrepancies concentrate
in the unloaded input and three source-position/data correspondences.
All 18 focused checks pass. ST-2's completed
mechanics replay passes 77 static and 14 modal targets at 5%; original-input
attachment compatibility and historical output conventions remain open.
ST-1's recent modal gains came from documented
input reconstructions and a corrected torsion-mode identification rule;
production structural equations were unchanged.

The [direct ST-4 native-export refinement](isae-st4-native-refinement-20261109.md)
now passes **31/31 frequencies** on 128/192 meshes: maximum native error 0.8128%,
mesh change 0.06841%, continuous-reference error 0.05472%, and minimum shape
MAC 0.99999949. All 320 saved-matrix checks pass. The earlier 20/31 refinement
result and interrupted 256 attempt remain intact. A lossless evidence writer
reduces serialization overhead; all production equations are unchanged.
This overlapping supplement adds no primary votes: the paper result remains
66/72, with all six original failures retained.

The [ST-4 recurring runner](isae-st4-recurring-20261109.md) now
completes the full native-export scope: five jobs, ten fresh states, all
frequencies and numerical gates passing. The paper replay stopped after 16
completed configurations when focus moved to ST-5; eight remain unfinished.
Its full earlier comparison still supports the totals above. The
[source-row audit and plot](isae-st4-source-rows-20261109.md)
identify mixed paper positions independently of OpenSwing predictions and
a 7.93% disagreement between a CSV frequency and its paired ASWING export.
All original comparisons remain; no tolerance, model or primary count changed.

The [current ST-4 airflow check](isae-st4-airflow-current-20261109.md)
completes four small serial solves on two 40-node spacing hypotheses. Modified
cosine reduces the sensitive low-frequency error from 48.94% to 1.48% and
restores the slow pole's negative sign, but its magnitude remains 24.62% off.
All 192 saved-matrix/pairing checks pass. Exact historical nodes and convergence
remain unresolved, so these diagnostics add no passes or primary scopes.

The [loaded ST-2 attachment check](isae-st2-loaded-attachments-20261109.md)
now verifies pylon/rigid-extension equivalence in vibration: four fresh serial
states, six positive modes per state and 96 matrix-equation checks pass.
Frequency differences between the physical representations are below 7e−12
relative; maximum mesh change is 0.373%. An independent point-motion/inertia
audit also passes. Public history retains the same out-of-range inputs from
the first structural upload, so the native parsing question remains open.
This adds no native targets or accepted passes; production code is unchanged.

**ST-3 retained status:**
The [fresh ST-3 static comparison](isae-st3-static-curves-20261109.md)
passes **84/86 at 5%**: all 84 readable ASWING ordinates match on both meshes,
while two clipped source values remain unavailable in the denominator.
All 80 serial states pass equilibrium and independent gravity force/moment
checks. Fine-grid median/maximum errors are 0.08725%/0.43472%; maximum mesh
change is 0.00743%. Fourteen source/extraction checks pass. The
[overlay plot](../../artifacts/isae/st3-static-curves-20261109/replay/comparison.png)
shows all twelve curves. Production equations and properties are unchanged.

The [current ST-3 modal comparison](isae-st3-modal-current-20261109.md)
remains **9/9 at 5%**, with maximum error 2.6592%, nine mesh/shape checks and
144 independent matrix checks passing. Its original strict result stays 8/9.
The prospective [mechanics scope](isae-st3-mechanics-scope.json)
is now primary: **93/95** distinct scalar targets. This explicitly replaces
the historical static snapshot as the primary static scope; **930/1,080**
remains separate and unchanged. Mesh repeats and overlapping archive values
add no votes. The static replay preserves the script's torque-axis scaling
and signed loads; it does not fit the experimental curves. Native startup,
modal labels, broader archive compatibility and regular-catalog integration
of the new static scope remain open. ST-1 and ST-2 retain their documented gaps.

**ST-2 retained status:**
The [complete published static-curve replay](isae-st2-static-curves-20261109.md)
now passes **77/77 ordinates at 5%**, with median error 0.0645% and maximum
0.4217%. All six bending/torsion curves and both skin labels are covered.
Maximum-load refinement changes stay below 0.0203%; all 47 serial states pass
equilibrium and independent gravity force/moment checks. Production equations
and properties are unchanged. This uses the disclosed rigid-tip attachment
reconstruction; original out-of-domain attachment handling remains unresolved.
The [current modal refresh](isae-st2-modal-current-20261109.md)
also passes **14/14 native frequencies**, with median error 0.0858%, maximum
0.8657%, mesh change below 0.303% and shape MAC above 0.999995. All ten overlapping
named Table 4 values agree within 0.489%; they add no extra votes. The modal
source files are unchanged. Archived tip moment/force ratios independently
support the static reconstruction's 8 mm spanwise and 50 mm chordwise arms.
The explicit [mechanics scope](isae-st2-mechanics-scope.json)
is now primary: **91/91 scalar comparisons under the declared setup**. The
overlapping 56/490 archive scope remains separate with its unavailable values
intact. This is an explicit scope change. Literal static-file attachment
compatibility, exact historical settings and other archive fields remain open.

The supplementary [spanwise replay](isae-st2-span-profile-20261109.md)
matches **275/368 archived fields**, including 275 of 276 mechanical values.
All 138 internal-force and moment values match within printed precision on
both meshes; maximum nonzero mechanical error is 0.4641%. The sole mechanical
mismatch is root y at 6.89e−17 m versus effectively zero. All 92 unavailable
legacy display fields remain required. Original coordinates support the
modified-cosine grid; maximum refinement change is 0.0112% of field peak.
This overlapping tip-pylon reconstruction adds no primary comparison votes.

The [complete recurring replay](isae-st2-mechanics-complete-20261109.md)
now finishes all 43 jobs and reproduces **91/91** matches. All 89 physical
states complete without failure or retry. The combined-summary importer is
fixed and independently authenticates the full result and physical artifacts.
All 98 focused mechanics/reporting checks pass. Production equations, targets,
tolerances and completion fractions are unchanged. The workflow integration
is complete; native attachment/input semantics and legacy outputs remain open.

The [attachment-interpretation study](isae-st2-attachment-interpretations-20261109.md)
now independently reproduces the static pylon using an explicit rigid extension
and joint, with main-wing positions agreeing to 2.11e−15 m. Only this tested
extension reproduces all 138 printed force/moment values; finite-stiffness
extensions miss the printed tip bending moment, while moving the load onto
the tip removes that moment entirely. All eight revised states pass numerical
and mesh checks. This supports the physical reconstruction without establishing
native out-of-domain parsing. Primary counts and comparison scopes are unchanged.

**ST-1 retained status:**
The [mechanics suite](isae-st1-thin-modal-20261109.md) now
tracks **201/201 static coordinates and 20/22 named modal frequencies** at 5%.
These independent scopes give 221/223 primary matches. This explicitly replaces
archive completeness as the main ST-1 progress measure; the original 9/200
archive inventory remains visible and unchanged below. All five report modal
configurations now have computed comparisons. Two unresolved reference
correspondences remain in the denominator.

The static curves cover four layouts and nine root conditions, with worst
nonzero error 0.762%. Seven modal matches use original properties (max 0.365%);
four [cross-ply matches](isae-st1-cross-modal-20261109.md) use a
documented physical-property reconstruction (max 1.096%). Nine thin-blade
matches use positive physical mass and ideal face orientations (max 1.071%).
All modal mesh changes are below 0.586%, with matching displacement/rotation
shapes (MAC >0.999867).
The coupled blade's reported “1T = 95 Hz” is reproduced as a predominantly
in-plane mode at 95.026 Hz. Its torsional branch is at 137.09 Hz (44.305% from
the literal label target). Sampled gravity continuation supports a label issue,
but native eigenvectors are unavailable, so this remains unpassed. The other
unpassed entry is the thin face-down printed 218 Hz versus computed 21.760 Hz
(90.018%); the original postprocessor and the opposite-face row say 21.8 Hz.

Original modal scripts enable the documented MODE vacuum toggle. Production
equations are unchanged. The thin first-torsion shape has a root sign change
explicitly described by Minguet. The old zero-sign-change identification rule
was corrected for this bent/coupled blade; its original reports are retained.
The [recurring mechanics runner](isae-st1-mechanics-runner-20261109.md)
is now registered: 50 source/contract tests and its three-coordinate static
smoke pass. Its modal integration smoke and full replay remain pending after
the switch to ST-2; the accepted counts above use the prior reviewed studies.
The [original thesis audit](isae-st1-material-source-review-20261109.md)
resolves cross-ply shear and thin-blade coupling magnitudes. The cross-ply
retry passes both meshes after an earlier startup timeout; both attempts are
preserved. Read the static and modal
fractions separately; the pooled count is dominated by static curve samples.
The archive still retains three raw-position mismatches and 188 unavailable
slots; neither its denominator nor its strict roundoff gates was silently relaxed.

**SA-12, SA-13 and SA-14 remain open.** The [full current CL-table refresh](isae-sa14-current-polar-20261109.md)
now passes **281/360 at 5%**, or 277/360 at 3%, against the same original slots.
Of those 281 matches, 188 use converged native rows; 93 match finite archived
values whose convergence flag is off. Remaining failures are 69 high-angle
local-Mach rejections, eight finite-body low-angle CL mismatches and two strict
near-zero comparisons. All 174 archive-unstalled states are numerically valid.
The [closing geometry check](isae-sa14-low-angle-20261109.md)
finds a cubic-radius bulge in the nominally cylindrical middle. An explicitly
modified flat-middle model reduces the zero-angle CL discrepancy by 95.75%,
without resolving it or adding passes. Spline endpoints and export-inferred
meshes have little effect. The small 5° body increment also has the wrong sign
despite passing total CL. No production physics changed. SA-13's source uncertainties are retained below,
and SA-12's physical ground-image calculation is retained.
The [continuous-curve force-law check](isae-sa13-continuous-laws-20261109.md)
finds that the published NACA corrections reduce some errors but do not resolve
the archived curves on the disclosed outlines. Geometry scale, R33's large
radius-table gap and supplied derivatives remain material uncertainties.
No force-law change or additional native pass follows from this diagnostic.
A contemporary R101 description gives a fineness ratio of 5.5, supporting
investigation of the report's factor-two convention conflict without rescaling
the geometry to fit it; the original test-model radius table is still missing.

The [full JSON lift replay](isae-sa13-discrete-bridge-20261109.md)
now reproduces 180 valid station values on the disclosed linear-radius models
through complete rigid solves. Public strip forces and moments recover the
station densities after translating the moment reference; global force/moment
and coefficient checks also pass. JSON solve calls take 0.05–0.13 s, with
6.75–9.72 s complete process times including imports and source checks. The
load plots now explain their interval-average convention; four existing
plotting-data checks pass. This adds no original-case pass; SA-13 stays 0/612.

The [pressure-output investigation](isae-sa13-pressure-geometry-20261109.md)
now reproduces all 56 finite red pressure ordinates as **100 × backward radius
slope squared − 5**. The additive offset is inferred, not a documented physical
normalization. The adapter records this exact source identity while retaining
the unresolved pressure mapping; all 22 adapter checks pass. Together with
the lift finding below, all 239 finite red-curve values are explained
algebraically. This adds no native solver passes or changes to the 0/612 scope.

The [discrete-load investigation](isae-sa13-discrete-loads-20261109.md)
now reproduces all 183 available red-curve lift ordinates algebraically from
the stored radii and next-station slopes, without fitting. It identifies RS1's
9° angle and R101's maximum-diameter normalization. The unchanged production
force kernel matches 180 valid station values to roundoff on an explicit
linear-radius reconstruction. Interval averages differ from those station
values by up to 28–64% of curve peak; this is an observable mismatch, not a
force-law failure. Two terminal zeros, one invalid-radius interval and all
missing values remain accounted for. Full setup/output mapping, continuous
curves and pressure remain unresolved, so the primary count stays **0/612**.

The [SA-13 geometry follow-up](isae-sa13-primary-geometry-20261109.md)
recovers six numerical bow radii from the cited primary report and records a
conflict between its text and figure nose coordinates. These constrain a
reconstruction but do not recover the original ASWING inputs. SA-13 stays
**0/612**; no SA-13 solver sweep or completion change is implied. SA-14's earlier
deferral remains recorded; the fresh six-point follow-up is linked above.

A [body-integration correction](isae-sa13-body-quadrature-20261109.md)
now splits quadrature at material spline knots. On the unchanged RS1 diagnostic
outline, the 32-interval strip-force error falls from 0.0855% of peak strip force
to roundoff; the coarse pressure-field integration error also decreases.
38 targeted implementation checks pass, including a mixed aero-structural case.
This adds sampling cost and changes no force law or frozen-influence default.
It adds no native SA-13 pass; browser/build checks remain held.

The [current SA-13 equation/integral audit](isae-sa13-load-integrals-20261109.md)
adds five passing body-force/volume-field checks, separate from native passes.
The archived continuous/discrete load integrals differ substantially; the
subsequent discrete-load audit above resolves the red-curve radius/derivative
relation and normalization. The modified continuous curves remain unresolved.
All original figure coordinates verify. The initial repository
folder also contains only the same four figures; no model/driver was recovered.

**Retained SA-12 investigation:**
The [fresh six-state SA-12 baseline](isae-sa12-current-pilot-20261109.md)
passes **16/18 lift/drag checks at 5%, or 16/24 including unchanged tiny-Cm
gates**. All six states are numerically valid and independently replayed.
The two lift/drag failures are the closest-ground unflapped point: CD is
33.72% high and CDi 6.38% low; CL is within 3.57%. Direct stall drag is
negligible there. The historical 2,324/4,080 SA-12 count is unchanged: this pilot is
a subset, not a full rerun or an additional progress scope.

The [pose/influence follow-up](isae-sa12-pose-diagnostics-20261109.md)
now finds **12/12 sampled lift/drag checks within 5% (12/16 with tiny Cm)**
using the unchanged production solver with zero pitch and frozen influences.
Worst error is 2.92%; the difficult point's raw-CD error drops from 33.72% to
2.92%. Four production states agree with independent circulation/field/force
calculations to roundoff. This is a disclosed alternative, not a recovered
historical setting: the scripts toggle K/F once and their initial state and
Euler pose are unavailable. A different image-wake interpretation also gets
close but fails the ground boundary condition; it is not adopted. Primary
counts and defaults are unchanged.

The [flapped-model follow-up](isae-sa12-flap-pose-20261109.md)
now completes four paired points: baseline **10/16** versus frozen/zero-pitch
**11/16**, including four tiny-Cm failures per setup. The alternative reduces
close-ground CD errors from 7.86%/6.73% to 0.54%/0.51%, but fails CDi at h/c=2
by 5.03%. At nominal infinity the current-influence baseline agrees within
0.135%, while frozen errors reach 4.55%. Thus frozen settings are not established
as a general correction. The combined eight-state frozen alternative is
23/24 lift/drag (23/32 including Cm), kept separate from the primary total.
All eight new production states and independent image/force/wake replays verify.

The [matched native AVL ground controls](isae-sa12-avl-ground-20261109.md)
now agree at all four points to better than 0.000002% in CL/CD/CDi, with matching
circulation and local velocity. These are common inviscid, unstalled controls
using the exact native lattice; they support the current-influence ground-image
operator but add no archived ISAE passes. Two targeted ground regression tests
also pass after making the test's wake assumption explicit. Production defaults
are unchanged. Remaining focus is the archived ground/pose/wake and raw-drag
conventions; post-stall repairs remain deferred.

The [flapped image-wake diagnostic](isae-sa12-flap-image-wake-20261109.md)
now matches all twelve sampled CL/CD/CDi values within 0.93% using zero pitch
and images with reflected endpoints but unchanged trailing-ray direction.
This strengthens a historical-approximation hypothesis, but the operator leaves
0.38–0.66 m/s of induced flow through the ground at the finite-height samples.
It is not adopted and adds no primary passes. The physical replay control
matches production to roundoff; five serial diagnostics and all reference
decisions verify. The actual modified-ASWING implementation remains unproven.
Eight new physical-boundary regressions also pass on 32/200-interval cosine
meshes at both wind-angle signs and with zero/finite vortex cores. They verify
the optimized image field and detect the endpoint-only approximation; they
add no archived ISAE passes.
The solved Horseshoes view now draws reflected bound lines and wake legs,
including frozen and Earth-view geometry, to help inspect these settings.
Twelve related JavaScript checks pass; browser rendering has not been rerun.
Both unchanged original SA-12 models are now selectable under ISAE aerodynamics,
with a [baseline setup guide](isae-sa12-examples-20261109.md).
Their source/public copies match the pinned originals; no new solve or pass is
implied by adding them to the menu.
An explicit **Apply SA-12 baseline** button now applies each closest-ground
pilot setup through the existing case loader, clearing prior constraints and
equilibrium input without solving. Ten JavaScript/project checks pass; all
141 solver source hashes match the pilot. Browser execution remains unverified.

A [source-only SA-13 follow-up](isae-sa13-pressure-reference-20261109.md)
keeps **0/612** and all missing entries. One original-discretization pressure
ordinate is 173.20% of freestream dynamic pressure under the Cp interpretation;
the declared incompressible Bernoulli formula permits at most 100%. The
normalization/postprocessing needs clarification in addition to the missing
original inputs. No SA-13 solver sweep or new pass follows from this audit.

**SA-11 retained status: the paper's lift curves and drag at equal lift.** The
updated [paper-focused suite](isae-sa11-lower-coverage-20261108.md)
passes **21/48 at 5% (43.75%)**: 21 reference mismatches, two rejected solutions
and four missing comparisons. It retains four configurations and both Figure
22 speeds, testing CL at 1°, 3°, 5° and CD at CL 0.3, 0.5, 0.7. Each curve
uses one disclosed setup. No experimental drag allowance is included.

This follows the purpose stated in Jan Part I, p.35 and Figure 22, p.39:
compare the lift curves and drag at equal lift for four wingtip configurations
at two speeds. The targets are documented ASWING results. The 48-check score
gives each configuration equal weight; changing the scope from the original
archive is not itself a solver improvement.

The latest [upper/lower coverage update](isae-sa11-lower-coverage-20261108.md)
adds six serial runs: five accepted, one rejected. Four missing comparisons
are resolved, with no new passes. At equal CL = 0.3, drag is 11.26% / 12.38%
high at the two speeds. At 3°, lift is 21.21% low at 240 m/s; the 272 m/s
state rejects at normal Mach 1.042. CL = 0.5/0.7 at both speeds still lack
valid brackets and remain required. The direct stall-pressure term explains
less than 0.6% of the low-lift drag discrepancy; indirect effects on circulation
remain separate. The deferred follow-up concerns lower-winglet loads and
interactions at low lift, with unchanged original CLmax = 0.8 and deferred post-stall repairs.
All 48 decisions and 912 source/artifact hashes independently verify.

Bare wing is **2/12**, planar extension **8/12**, upper winglet **11/12** and
upper/lower winglets **0/12**. The upper-winglet same-angle suite still passes
294/294; its new equal-lift drag check is 5.25% high at CL 0.7 and the faster
speed. The lower-speed CL 0.7 bracket is now complete and passes at 4.19% error.
The preceding alignment used 89 new solves and four identical saved
states; all verified, with no rejection in that update. The original baseline also changes
main-wing airfoil data (slope 7 versus 6.34, zero Cdf, much larger Cdp). A separate
control therefore removes winglets from the same model while keeping identical
main-wing data and nodes; post-stall repairs remain deferred.

That [same-main-wing control](isae-sa11-same-mainwing-20261108.md)
is now complete: all 50 states are valid. Its bare-wing alternative passes
6/12 diagnostic samples: lift errors 1.23–1.38% low, equal-lift drag errors
5.52–11.54% high (median 9.17%). It is not substituted into the primary score.
Six further controlled calls at 240 m/s keep both winglets at exactly 16
intervals and change only the shared main mesh from 32 to 62 intervals. At
CL = 0.5 the finer-main trial matches the native Trefftz drag reduction within
0.115% and the lift increment at 3° within 2.97%, while total drag benefit changes
from 37.03% too strong to 18.22% too weak. All 56 new states and independent
field/force/Decimal checks pass their numerical gates. This identifies strong
main-mesh sensitivity in near-field drag; it establishes neither a solver fix
nor convergence. Primary 21/48 and original 1,060/9,184 stay unchanged.
[Control plots and downloadable model](../../public/isae-sa11-paper/same-mainwing.html)
are served at `/isae-sa11-paper/same-mainwing.html`. This led to the following
near-field load sampling/accumulation investigation on this controlled pair.

The [wake-interaction follow-up](isae-sa11-winglet-interactions-20261108.md)
localizes the sensitivity: nine saved-state audits put 89.79% of the total drag
change in finite-origin main-wing/winglet interactions, almost entirely at the
outer 125 mm of projected main-wing span. Six valid new solves change only the
outer two main intervals per side (46 total), preserving all 28 interior
intervals and both 16-interval winglets. This reproduces 94.18% of the whole-main
mesh change. At CL = 0.5 and 240 m/s, the local trial matches the Trefftz benefit
within 0.31% and the lift increment at 3° within 1.77%; total drag benefit is
still 15.00% too weak. These are qualified alternative-input diagnostics, not
new primary passes or proof of convergence. Primary 21/48 stays unchanged.
[New plot and evidence](../../public/isae-sa11-paper/wake-interactions.html) are served
at `/isae-sa11-paper/wake-interactions.html`. This led to the following separation
of local main-tip source/receiver placement from circulation changes.

The [full-field factorization](isae-sa11-tip-factorization-20261108.md)
now separates them: at 2.75°/3°, receiver quadrature explains only 0.90% of the
cross-beam drag change; main circulation steps and winglet response explain
47.5% and 51.6%. Large separated finite-origin receiver terms cancel with
half-wake terms. Independent winglet equations reproduce the saved response;
stall is negligible. Eight main-only Fourier trials compute, but do not fix
the sensitivity: the 20-mode/local-tip case has 53.15% CD error and 26.04%
local flow defect despite a tiny projected residual. Six pass every tight
numerical diagnostic; two coarse-mesh/30-mode cases retain conditioning-related
failures. No default, tolerance or primary count changes. That study leaves
main-tip circulation sampling and coupling unresolved. [Plot and complete evidence](../../public/isae-sa11-paper/circulation-sampling.html)
are served at `/isae-sa11-paper/circulation-sampling.html`.

[Comparison page and plots](../../public/isae-sa11-paper/index.html), served at
`/isae-sa11-paper/`. The new score was independently verified from saved
states. Its first version used zero new solves; v2 aligned frozen influences
and filled one bracket, and v3 resolves four upper/lower missing comparisons.
The primary progress curve selects
the explicit paper-focused scope; the earlier change from 9,184 to 48 targets
was a scope change, not solver improvement.
The original archive stays **1,060/9,184**, including all unavailable values,
and is not combined with the new fraction. All 48 new targets remain required.

## Earlier SA-11 investigation: original archive and separate diagnostics

The entries below preserve the preceding investigation and its then-primary
archive scope. The current primary scope is the paper-focused suite above.

**SA-11 original-suite rerun:** applying the same minimum horseshoe spacing
raises the primary score from **163/9,184 (1.77%) to 1,060/9,184 (11.54%)**:
897 gained, none lost. All 328 executable requests were freshly run; 322 now
compute, six reject local Mach and 984 original requests remain unavailable.
The [rerun report](isae-sa11-original-minimum-spacing-20261108.md)
retains four configurations, sixteen polars, 0°–10° and both cosine 64/128
requests, coarsened only to enforce the fixed 16.466 mm minimum. Original
files and all other settings are unchanged. The separate
report-derived upper-winglet check is **294/294 = 100%** over 0°–5° at two
speeds with minimum spacing; the upper/lower diagnostic is **11/42 = 26.19%**
at six sampled points. These use disclosed corrected inputs and a different
mesh scope, so their passes cannot be added to the original total. At that stage,
the progress plot tracked the original full suite and did not display
those alternative diagnostics. The large denominator must not be read as the
completion fraction of the recently passing upper-winglet subset.

The [extended-wing drag budget](isae-sa11-extension-drag-budget-20261108.md)
now verifies twenty predeclared points/controls at 0°–5°. Near-field vortex
drag accounts for 93.76–97.14% of the change between the two meshes; profile
drag changes at most 0.449%, with negligible stall leakage. Frozen influences
remove only 2.78–7.14% of the checked discrepancies and gain no passes.
Independent force/moment reductions and exact primary-result replays pass.
The subsequent saved-field receiver audit reproduces Drela's construction
within 4.45e-16 m. Independent zero-core vortex algebra agrees within 7.73e-15
of freestream; all three alternative receiver probes worsen drag. These
diagnostics leave the primary score unchanged. The subsequent
[discretization comparison](isae-sa11-extension-discretization-20261108.md)
completes eighteen valid 3° states. Fourier 20/30/40 counts change CD error by
at most 0.182 percentage points and change no 5% decisions; smaller pointwise
meshes leave CD 9.86–14.07% low. Independent projected/linear circulation
checks pass. Physical-mesh force stability and native setup interpretation
remain open; no added primary passes or changed scope.

The [fixed-minimum refinement check](isae-sa11-extension-mesh-limit-20261108.md)
adds twelve diagnostic solves at 3°/5° and 240/272 m/s: nine valid, three
center-Mach rejections. Requests 256/512/1024 produce only 160/172/178 actual
intervals. Finest accepted CD errors are 1.22–1.50%, but CD still changes
1.02–1.27% on the last refinement; no stable force limit is established.
All three faster 5° cases reach M_perp ≈ 1.152 at the center sweep break.
Independent velocity, force and bound-source checks agree. Drag changes
mostly outside the two center-adjacent strips; the next audit will examine
their nonuniform-mesh force integration. Primary passes and scope are unchanged.

That [pairwise force audit](isae-sa11-extension-drag-pairs-20261108.md)
now attributes 80–86% of the last two drag changes at 240 m/s, 3° to adjacent
finite-origin wake interactions. A closed-form straight-pair check explains
the strongest non-center terms within 0.27%. However, three count-preserving
node-redistribution trials still change CD by 2.24% and 1.12% and match the
archive slightly worse. This rules out simple width smoothing as a sufficient
fix; no production mesher, equations, primary score or scope changes. Full
discrete load recovery and native sampling remain the next source-audit topic.

**Earlier SA-11 focus: pre-stall discrepancies.** The requested
[minimum horseshoe spacing](isae-sa11-minimum-spacing-20261108.md)
is implemented throughout each selected beam, with a Nodes control and an
importable mesh preset. The report-derived upper-winglet comparison now passes
**294/294 diagnostic checks**: all 42 points from 0°–5° at 240/272 m/s have
complete moments and every output is within 5%. Maximum normal Mach is 0.812;
largest error is CD, 4.829% high. The 16.466 mm minimum produces 16 actual
winglet intervals even when more are requested. All 29 new and 39 existing
mesh checks pass; independent reductions and default-control replay pass.
This remains a disclosed report-minus4 subset; the primary 1,060/9,184 scope is
not replaced or combined with it. Browser execution is still held, with the
new UI syntax checked and the Python inspection/solve path verified.

The subsequent [upper/lower-winglet check](isae-sa11-two-winglet-spacing-20261108.md)
transfers that minimum unchanged to six prescribed points and passes
**11/42 diagnostic comparisons**, with five complete states and one lower-root
Mach rejection. At 0°, CL error is 2.81–3.28%, CD 7.22–8.91%, CDi 4.89–6.08%,
and Cm magnitude 4.42–5.10%. Larger 5° lift errors occur with substantial
stall-transition leakage: this source sets CLmax 0.8, while upper-only uses
default 2.0 and the archived upper/lower CL curve remains nearly linear.
The faster rejected root is dominated by its own wake leg, independently
verified at 333.38 m/s and 4.054 mm distance. All six small serial solves and
independent reductions are complete. Next focus is the 0° upper/lower case;
post-stall repairs remain deferred. These alternative checks are not added
to the original primary denominator or progress curve.

A
[native capture package](isae-sa11-native-capture.md) now preserves
the original input, Joint-only correction and report-minus4 alternative separately,
with a proposed two-angle capture procedure. Its source/model checks pass;
native execution remains unavailable. This adds no aerodynamic passes or scope.
The latest [winglet-spacing study](isae-sa11-winglet-spacing-20261108.md)
gives accepted solutions with **uniform 16/32 intervals per winglet**: CL, CD,
CDi, Cm and efficiency all match archived alpha-1° values within 3%. Main-wing
intervals stay at 32; geometry, zero core and equations are unchanged.
Tip-clustered 16/32 also matches. Finer 64/128 meshes again reject local Mach;
that sensitivity does not erase the successful comparisons or impose a new
passing criterion. The subsequent
[fixed-uniform32 polar check](isae-sa11-uniform-polar-20261108.md)
completes all 42 points from 0°–5° at 240/272 m/s: **31 complete states match
all seven archived outputs within 2.22%**. Matching ranges are 0°–4° at 240 m/s
and 0°–3.25° at 272 m/s. The eleven higher-load points still reject the local
section-moment law, despite converged circulation and pre-stall sections.
This is **217/294 diagnostic comparisons** on one fixed mesh, not an addition
to the primary total. All fourteen small serial batches and the independent
saved-field checker complete. The first attempt's JSON-flag export failure is
retained. The minimum-spacing follow-up above now completes the prescribed
uniform16 comparison across that same interval. These runs use the disclosed report-minus4 alternative;
primary fractions and scope are unchanged.
The earlier [root-position diagnostic](isae-sa11-root-translations-20261108.md)
completes twelve small serial calls. On the disclosed report-minus4 control,
doubling intervals raises local Mach 1.534→2.668 although CL/CD errors stay
within 0.70%/2.06%. A 0.25 mm outward shift gives finite moments but CD errors
6.35%/10.59%; aligned roots instead worsen bound-induced velocities. These
alternative geometries add no primary passes. The
[paper audit](isae-sa11-reassessment-20261108.md) confirms that
the illustrated .70/.80 ASWING curves match archived tables at 48 samples;
the [incidence checks](isae-sa11-angle-response-20261108.md)
also leave both roots rejected. Stable local flow under refinement and the
full-polar moment comparison remain open.
The [browser diagnostic](isae-sa11-browser-diagnostics-20261108.md)
now marks and lists all rejected sections, including both winglet roots in the
tested example; source attribution remains attached to the worst section.
Its [partial surface-force panel](isae-sa11-partial-forces-20261108.md)
now also exposes finite lift/drag contributions, with the undefined moment and
excluded loads explicitly identified. These rejected-state diagnostics add no
accepted solutions or native matches; the comparison fraction is unchanged.
The [saved-field drag decomposition](isae-sa11-drag-closure-20261108.md)
rules out the beam/bound force measure as the cause of the near/Trefftz gap on
this grid. The invalid roots account for about 42% of that gap; main-wing
interactions dominate its receiver-sampling change. No new accepted states.
Its own-wake follow-up reproduces the sampling-sensitive term in closed form;
this is an expected geometric sampling effect, not a new self-influence fix.
Post-stall
repairs are deferred at the user's request. The
[earlier expanded refresh](isae-sa11-complete-scope-20261108.md) covered
**all sixteen archived polars** and passed **163/9,184 at 5%** before minimum
spacing: 47 valid states,
281 local-Mach rejections and 984 unavailable original requests. All 328
executable requests were freshly run, with unchanged outcomes and predictions
within 1.02e-15 scaled difference. The denominator doubles because upper and
upper/lower winglets are now included; this is broader coverage, with no new
numerical matches. Their original Joint scaling/attachment conflicts remain
explicit, alongside the eight .75/.78 normalization-conflict tables. Overlapping
blockers are counted once. Original targets and unavailable values remain.
Zero-incidence diagnostics place every section well inside its stall limits;
the [section-input diagnostic](isae-sa11-section-inputs-20261107.md)
now identifies a likely source of the baseline lift bias: its slope is 7.0,
versus 6.34 in every other SA-11 input. The fixed donor slope brings four
pre-stall CL comparisons within 0.124%; transferring its drag inputs too
leaves CD 5.32–6.27% low at 1°. These alternative inputs are not promoted to
the primary count. Native producing parameters and swept-tip velocity remain open.
The [frozen-influence follow-up](isae-sa11-frozen-inputs-20261107.md)
rules out that toggle as the explanation at these points: transferred-input CD
remains 5.18–6.08% low at 1°, with no change in diagnostic passes. Saved forces
and moments satisfy the published load equations to roundoff; velocity-field
fidelity and exact native inputs remain unresolved.

The latest [native AVL comparison](isae-sa11-winglet-polar-20261108.md)
identifies a second input conflict: the report gives upper-winglet twist −4°,
while the supplied file gives +4°. Using the report's sign, native AVL agrees
with archived lift within 0.561% and CDi within 0.332% across 21 angles from
0° to 5°. OpenSwing circulation agrees with native AVL within 0.082%, but
every production state tested in that earlier polar still fails local Mach. The
[practical-resolution checks](isae-sa11-practical-resolution-20261108.md)
also fail that guard after circulation convergence. A
[source audit](isae-sa11-command-grouping-20261108.md) finds
inconsistent command sequences and no retained startup settings. These are
diagnostic findings, with no new passes or scope changes. SA-11 remains the
priority; SA-2 stall-region work is deferred.
Six subsequent [native AVL chord/span checks](isae-sa11-native-chord-refinement-20261108.md)
retain lift/CDi agreement within 0.369%/1.345% at 1° while local root velocity
still increases with span refinement. A coarse native case below Mach 1
reaches 6.50 on its finer span mesh. This strengthens the distinction between
integrated-loading agreement and unresolved local flow; no pass count changes.
The subsequent [root-mesh audit](isae-sa11-native-root-conformity-20261108.md)
aligns native chordwise origins over the shared wing/winglet root chord without
moving the planform. Peak normal Mach drops from 2.49/10.30 to 1.09/2.86 on
the two span meshes, but local velocity still grows and near-field vortex drag
changes 10.62% with refinement. This identifies mesh sensitivity, not a valid
production repair; it adds no passing comparisons.
The [adjacent-bound check](isae-sa11-shared-bound-corner-20261108.md)
independently predicts the remaining sharp-corner velocity growth within
0.0005%. Published bound-point force sampling is retained. Failure diagnostics
now identify bound-source distance and exactly shared corner geometry; 23
focused tests pass, with no aerodynamic or comparison-count changes.
The [length-allocation check](isae-sa11-allocation-and-speed-20261108.md)
also fails: all six pre-stall states reject local Mach even when winglet
interval counts follow beam length. Independent integration reproduces their
wake-dominated peaks. A new archived speed-pair audit finds CL/CD/CDi/efficiency
unchanged within printed precision at every .75/.78 row for three configurations,
while Cm changes; the upper/lower-winglet pair behaves differently. This supports
differing fixed/speed-dependent global PG settings, but does not recover the
exact value or startup state. No primary pass, scope or equation changes.

The [fixed-PG candidate check](isae-sa11-fixed-pg-candidate-20261108.md)
now finds baseline .75/.78 lift/CDi agreement within 0.4% at 0°/1° using zero
global PG, the separately supplied cant0 normalization and slope 6.34.
Production Cm is within 0.2%, but total CD remains 42.70–46.82% high. This
candidate does not explain the upper-winglet archive: all nine winglet states
still reject local Mach before stall, despite circulation agreeing with native
AVL within 0.124%. Two extension comparisons expose a curved-ASW/straight-AVL
conversion mismatch and are retained as blocked. Twelve native runs and eighteen
production calls are terminal; original producing inputs remain unverified.
At that stage the primary fraction stayed **163/9,184**; those alternatives
added no passes. The minimum-spacing rerun above now supersedes that count.
Two subsequent [full-scale cant0 checks](isae-sa11-cant0-candidate-20261108.md)
do not explain the upper .75/.78 archive: native CL is 4.87–6.95% high and CDi
12.75–19.34% low. Both direct rigid-aerodynamic states still reject local Mach
without stall. The original invalid joints and unpaired source remain explicit;
matching reference area is insufficient to reassign an archived polar. No new passes.
The [Chreim source review](isae-sa11-chreim-review-20261108.md)
checks the wake criticism cited by ISAE. The alternative formulation shares
Drela's control-point slope factor but changes wake geometry and section-lift
velocity; it supplies no verified SA-11 repair or native startup settings.
ISAE explicitly reports not observing the cited wake instability. This was a
source review only: no solver runs, new passes or scope changes.
The subsequent [curved-extension comparison](isae-sa11-curved-extension-20261108.md)
now samples the original spline at every ASW node, with identical source
endpoints and explicitly different receiver rules. Native CL/CDi errors are
below 1% in all six checks. The four conditional zero-PG/.75 production states
have CL/CDi errors below 0.075%/0.692% and total CD errors of 2.46–4.05%.
Their historical setup remains unverified. The original .70 fine-grid state
still rejects local Mach before stall; native local fields also exceed unity.
Exact native-core replay explains a separate curved-bound field difference,
without changing production. No primary pass or scope changes.

The [browser airflow diagnostics](isae-sa11-browser-diagnostics-20261108.md)
now mark rejected force points and their strongest bound/wake contributors in
the aircraft view, with source distances and a downloadable request/kernel
record. This exposes the existing SA-11 failure evidence without changing the
aerodynamics or accepting rejected loads. No new primary passes or scope changes.

The [paired-speed moment check](isae-sa11-moment-speed-20261108.md)
now isolates a receiver-sampling effect: with identical vortex endpoints,
whole-beam sampling reduces the baseline moment-increment error from 7.11–23.15%
to 1.17–2.18%. Three extension replays agree within 0.624%; the fourth exceeds
local Mach at the higher speed. This supports the published section-moment law,
but does not authenticate historical setup or fix the winglet junction. Two
small serial solves completed; the primary fraction and scope are unchanged.

The [additional input search](isae-sa11-independent-input-search-20261108.md)
finds only aerodynamic placeholders in the author's older repository. A
retained independent AVL thesis concerns a different aircraft, so neither
source resolves the SA-11 conversion or missing native setup. The winglet
junction remains the priority; no new solves or primary passes are claimed.

The [whole-beam receiver sweep](isae-sa11-whole-beam-polar-20261108.md)
now covers all 21 archived 0–5° rows of the disclosed report-minus4 alternative.
Formal CD error falls from **12.63–44.13%** in the earlier
[native-receiver diagnostic](isae-sa11-rejected-force-budget-20261108.md)
to **0.043–0.241%**, with unchanged vortex endpoints and the existing production
sampling rule. Formal CL error is **0.587–0.730%** in magnitude. All 21 states
still reject at exactly two winglet-root receivers, with maximum local Mach
**1.223–2.849** and negligible stall drag. Nineteen new serial calls and two
reused states are independently checked; no primary passes or scope changes.

The [separate wake check](isae-sa11-whole-beam-wake-20261108.md)
also puts formal CDi within **1.390–1.537%** and span efficiency within
**2.930–2.984%** across those 21 states. These two outputs become slightly
less accurate than with the native-receiver override, while total drag improves;
settings are not mixed. The offset-root wake mechanism persists, and all full
states remain rejected. No new physical solves, accepted moments or passes.

The [root-moment follow-up](isae-sa11-root-moment-envelope-20261108.md)
finds that total CM at 5% cannot identify the required local-flow correction.
Matching the printed values by changing only the two undefined root section
moments would require Mach above 0.999997 under that fixed-force hypothesis.
The receiver movement is on the main wing; root points stay fixed to rounding.
Saved-field and independent high-precision checks add no solves or passes.

SA-10 is deferred. The [complete fresh comparison](isae-sa10-focus-20261107.md)
passes **1,610/2,268 at 5%** across all six original configurations: 269 valid
states, one local-Mach rejection and 54 original attachment-input blockers.
The faster Newton corrector removes the reproduced timeout while preserving
predictions to roundoff. The +354 displayed matches reflect the 3%→5% allowance,
not improved aerodynamic agreement. Louvered is the weakest executable
configuration at **277/378**; induced drag and post-stall loads remain the
main computed discrepancies. No family is declared fully validated.

SA-7 is deferred. The [correctly paired comparison](isae-sa7-focus-20261107.md)
passes **682/812 at 5%**: full aircraft **406/406**, isolated fore wing
**276/406**. The original fore-wing input matches the report's 1.29 m span and
0.22 m chord; the later repository file describes a different aircraft while
retaining the old output table. The previous **406/812** pairing remains a
source-mismatch diagnostic. The +276 displayed matches come from correcting
the input pairing, **not a solver improvement**. All original target values
and denominators remain; alternative predictions are not combined. The 130
failures are Drag/CD (116), low-lift Lift/CL (4), and post-stall CDi (10).
All 58 refreshed fore-wing jobs converge. Frozen-setting pilots gain no
matches; both supplied drivers explicitly toggle F to evolving influences.

The [force-equation and mesh audit](isae-sa7-force-consistency-20261107.md)
finds 23 of 29 fore-wing rows incompatible with a conditional CD/CDi lower
bound even at 5%. Twenty-four converged mesh checks gain no matches; maximum
80/160 coefficient change is below 0.004%. The native producing setup/output
definition remains unresolved. The `sa7-documented` runner option now reproduces
the selected pairing directly; counts remain **682/812**.

SA-6 is deferred at **470/528** static and **370/528** supplemental F1 checks.
Its 58 static failures remain rolling moment, with typical error 6.08%
(5.09–8.25%). The prepared profile-load feasibility study has no completed
88-state batch. The broad SA rerun remains deferred after 457 finished jobs;
its original seven-family snapshot is retained at **2,034/2,604**, with SA-10
partial in that older run. The separate SA-10 refresh above is complete.
Small serial jobs use one BLAS thread. FFWT-4 remains deferred at
**200/8,000**.

The [supplemental SA-6 F1 comparison](isae-sa6-frozen-f1-20261107.md)
is complete at the same frozen/strength-40 default: **370/528** derivative
checks pass at 5%, with all 88 bases numerically valid. Failed rolling
sensitivities have median error 7.29% and maximum 17.01%. Selected analytic
derivatives agree with fresh nonlinear perturbations. These derivative
targets stay separate from the primary static 470/528; no static pass is added.
An [independent section-equation check](frozen-stall-reference-20261107.md)
passes for both influence modes and their control/incidence derivatives.
It supports the implemented smooth stall law but adds no native-reference passes.
The [complete finite-wing reconstruction](isae-sa6-frozen-independent-20261107.md)
also agrees for all 88 states and their F1 responses. A derived native
profile-normal force component has current predictions 11.92–12.84% above the
native value; printing precision cannot explain it. This diagnostic adds no
tracked targets; primary counts are unchanged.

[Timestamped progress plots and update instructions](isae-progress.md)
are available in the workbench's **ISAE progress** link. Tracking starts with
the current observed fractions; earlier change times are not inferred.

The [FFWT-4 complete source audit](isae-ffwt4-sources-20261106.md)
expands its tracked scope from the fixed-wing subset to all **40 archived
histories and 8,000 values**. Existing matches are retained once: **200/8,000
pass at 5%**. Of the 7,800 uncomputed values, 4,800 belong to three PM2 models
with out-of-range point-mass attachments; the original audit retained six
mesh rejections. These now use the qualified rigid-pylon handling below.
The driver-selected PM2 files must not be
replaced with the simpler alternatives. The Flare20 driver explicitly sets
16° sideslip. All 15 inventory tests pass; no new native pass is claimed.
The [rigid-extension study](isae-ffwt4-rigid-extension-20261106.md)
adds 44 passing checks: synthetic endpoint loads and reduced steady matrices
agree for both body and lifting-surface charts. A prescribed-history BDF
counterexample prevents claiming exact finite-step equivalence. Point airflow,
general integrated histories and native attachment handling
remain open; the affected native histories stay uncomputed.
The [integrated attachment comparison](isae-ffwt4-rigid-time-20261106.md)
now completes six synthetic vacuum histories: all six finest-step quantities
agree with an exact oscillator within 0.0577%, with second-order convergence.
All 12 individual-point motion checks also pass 0.1%. The six literal rejected
objects have zero drag area, volume, spin and intrinsic inertia. This narrows
the active physics but does not establish native out-of-range input semantics.
The [continuous dynamic-matrix comparison](isae-ffwt4-rigid-dynamic-20261106.md)
now passes ten cases and 30 separate full-matrix checks. Complete inertia and
velocity terms match independent rigid-body formulas to 8.47e-12 and 5.06e-11
(scaled arithmetic errors); all 24 reference-formula tests pass. This closes
the matrix gap for the tested rigid vacuum models.
The [production attachment implementation](isae-rigid-attachment-production-20261106.md)
now loads all three literal PM2 models without rewriting their sources or
moving the physical masses. It records the endpoint-pylon policy in outputs
and saved states. Attachment/null-object and station/wall regressions pass
84 and 44 checks; both time formulations pass checkpoint tests, and 21 built
browser checks pass. The first small Flare20 coupled preflight hit its
150-second limit: the full startup rank matrix took 78 seconds, followed by
very small load increments. Native attachment semantics and the PM2 coupled
histories remain unvalidated; no additional native pass is counted.
The [startup follow-up](isae-ffwt4-startup-20261106.md) reduces
first nonzero-load startup from 82.5 seconds to 4.3–8.0 seconds in retained
runs and completes the loaded full matrix in 8.65 seconds. All 52 rank/predictor
and 27 matrix/network checks pass with unchanged acceptance gates. The final
150-second single-job attempt ended before full equilibrium. Built WASM matrix
checks and all 21 browser import/load/checkpoint checks passed for that kernel.
The [serial-continuation study](isae-ffwt4-continuation-20261106.md)
now completes the literal 55-node Flare20 equilibrium: **17 accepted load steps
in six jobs**, zero rejections, and rebuilt final residual **4.61e-13**. All 40
continuation/rank checks and 32 built-browser restart checks pass. The driver mesh, other PM2 equilibria and gust
histories remain required; coverage stays **200/8,000**.

The [Flare20 mesh study](isae-ffwt4-pm2-mesh-20261106.md)
now completes 107 nodes in seven serial jobs, with 17 accepted steps, no
rejections and rebuilt residual 9.65e-13. The root moment changes **0.0448%**
from 55 nodes, passing its 0.1% spatial gate; hinge changes of 0.113°/0.018°
and other field differences still require refinement. The initial native
root-moment diagnostic differs by 2.78%, without adding a native pass. The
211-node attempt timed out in the unloaded rank fallback; its mechanical
singular-value ratio is 8.17e-11 against the unchanged 1e-10 gate. Further
invertible scaling raises that ratio to 1.57e-10 in a read-only diagnostic;
this motivated the production refinement below.

The [bounded rank refinement](isae-ffwt4-rank-refinement-20261106.md)
is now implemented and passes **66 native regression checks**, including
released mechanisms and redundant constraints. It preserves the 1e-10 rank
gate and physical equations. The 211-node case now saves two accepted load
steps in 42.72/44.67-second jobs, with rebuilt residuals below 7.80e-13.
All **29 built-browser checks pass**, including a complete page/worker restart;
the two browser steps take 39.41/37.96 seconds and agree with native states
to 3.75e-16 on the normalized coordinate scale.
The [211-node follow-up](isae-ffwt4-pm2-211-20261107.md)
now completes full load in 17 accepted steps, with zero load rejections and
rebuilt residual 2.06e-13. One process timeout with complete saved output is
retained and independently revalidated; subsequent single-step jobs all exit
successfully. The 107/211-node pair passes **0/7 mesh checks**: root moment
changes **0.195%**, and per-beam displacement/finite rotation changes
**0.108–0.236%**, above the unchanged 0.1% numerical gate. Mesh accuracy and
gust comparisons remain open; 21 new audit/comparison regression tests pass.

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
matching Python states to 3.07e-16 on the normalized coordinate scale. The
subsequent diagnostic linked above isolates circulation discretization and
identifies a promising endpoint-spacing refinement. No full field accuracy,
native K/F default or attachment semantics is established.

The [FFWT-4 full-history refinement](isae-ffwt4-spatial-time-20261106.md)
has reached **1,162/1,592 steps** on the 159-node mesh, through 2.164225 s and
past the end of the prescribed gust. All **146/146 reached native values**
pass at 5%, with
median/max error **0.763%/0.893%**, zero rejected steps and maximum residual
9.975e-9. Error at the native peak time is **0.611%**. The full-history
field checker passes 59 focused tests and now explicitly retains both the
original 200-output-time gates and the denser shared-time gates. This partial
finer-mesh run does not yet establish full-history
spatial/time accuracy. It repeats existing targets, so the tracked fraction
remains **200/8,000** across the full archive, including **200/1,600** in the
fixed-wing subset, from the completed 63-node history.

The [FFWT-4 initial spatial study](isae-ffwt4-spatial-20261106.md)
now passes **3/3** checks between 159 and 287 nodes: root moment, displacement
and rotation-vector changes are 0.0106%, 0.00762% and 0.0215%, below 0.1%.
The finest initial native error is 0.778%. The 63-node initial moment differs
from that result by 0.221%, so full-history spatial accuracy remains open.
These repeated t=0 comparisons do not increase native coverage.

The [FFWT-4 eighth-step study](isae-ffwt4-eighth-step-20261106.md)
passes **200/200** values in its complete first history, or **200/1,600**
across all eight fixed-wing histories. Median/max native error is 0.523%/0.681%.
All 1,592 refined steps converge without rejection through 2.9651 s. The latest
adjacent-grid time accuracy now passes **2/2**: total root moment changes
0.0132%, and its gust increment changes 0.0373%, both below the unchanged
0.1% limit. This resolves the preceding 0.113% increment failure. All 797
shared ticks and the original 200 native ticks are checked. The original
coarse grid still fails the increment gate; spatial/all-state accuracy,
other histories and shared registration remain open. Repeated native targets
count once, so the progress fraction is unchanged.

The [operator-reuse follow-up](isae-ffwt4-operator-cache-20261106.md)
preserves the complete output of a four-step continuation and reduces repeated
operator construction. It changes no comparison fraction or accuracy gate;
whole-solver timing improvements remain unproven.

The [FFWT-3 source audit](isae-ffwt3-sources-20261106.md)
adds all 27 archived history/driver jobs: **0/36,462 blocked slots**, comprising
35,256 retained native values and 1,206 missing-reference slots. Every literal
model has out-of-range joint stations; fresh meshing confirms the incompatibility
on two grids. Sensors are in range. One driver/output time grid also differs,
and two files lack their corresponding driver/output. The independent summary
verifies the complete denominator; no physical solve or native pass is claimed.

The [FFWT-2 full-startup refinement and independent aerodynamic checks](isae-ffwt2-history-refinement-20261106.md)
now complete: 408 accepted steps, zero rejected steps, and 42 small serial jobs.
The .005 s history still passes **5/25 computed native values**, or **5/4,005**
required values. Only roll rate passes; failed medians are acceleration 160.56%,
aircraft bank 7.49%, and tip banks 64.83%/31.83%. Full-history refinement passes
only **1/5** strict numerical accuracy gates, so time convergence remains open.
Independent aerodynamic checks pass for 27 snapshot records; all eight vortex
reference tests pass. Their maximum absolute Cl is 0.3900, with no stalled strips.
No production equation or physical parameter changed. FFWT-3 is now registered
with the source blockers above; FFWT-4's first complete fixed history passes
its native comparisons, with the remaining coverage qualified above.

The [5% reassessment](isae-five-percent-20261105.md) prioritizes
previously zero-pass scopes and distinguishes rescored saved predictions from
new solves. Other rows explicitly retain their historical thresholds until
rescored; UA equation checks are intentionally unchanged. Missing outputs remain
in denominators. Seven families still lack a shared comparison adapter; the
newly registered AE-5 adapter explicitly retains its unresolved source pairings.

The [FFWT-2 mechanics/refinement audit](isae-ffwt2-mechanics-20261106.md)
independently checks all 204 saved jig-start states and passes seven mechanics
reference tests. Four fresh local grids accept 120 steps without rejection;
the finest pair passes **5/5 numerical accuracy gates** over 2.00–2.04 s.
Native agreement remains **5/25 computed values**, or **5/4,005** in the full
selected table. Only roll rate passes. Failed median errors are acceleration
159.69%, aircraft bank 7.38%, and tip banks 64.52%/31.95%. The separate
equilibrium-start scope retains **10/25**, or **10/4,005**. All 3,980 unrun
values remain required per scope. The local restart transient does not explain
the native discrepancy. The follow-up above adds a full-startup finer grid and
independent aero checks; time/mesh convergence, historical startup and shared
registration remain open. The earlier
[matrix optimization](isae-ffwt2-time-tangent-20261106.md)
retains its strict parity and 38.1-to-33.1-second controlled timing improvement.

[AE-5's source audit](isae-ae5-sources-20261105.md) records
**0/587 blocked comparisons**. Its driver commands 22 speeds, but the modal
export has 29 indexed points; the literal stiffness also differs substantially
from the report. One literal source case solves in 14.15 seconds and passes
all 16 full-matrix modal checks, without claiming an archived-output match.

The [P-2 input recovery](isae-p2-recovery-20261105.md) adds its
first complete declared comparison: **312/312 archived CT/efficiency values
pass at 5%**, with a maximum discrepancy of 0.633%. Original power tables and
measurement-derived drag inputs now cover every stored coordinate. The missing
original driver and exact regression settings remain qualified; no production
equation was changed to obtain these matches.

SA-15's declared-setup scope is now in the shared runner: 84/182 pass, with all
26 solves and 312 numerical checks passing; its archived startup remains
unrecovered. AE-4 now reproduces the first declared 69–70 m/s flutter bracket
on both meshes. Its shared adapter now retains all eighteen modal exports and a
1,200-component declared sweep. The earlier selected batches passed 11/40. The current 101 m/s pair
adds 8/8, bringing the selected total to 19/48 and leaving 1,152 further sweep
components unrun. Accumulated sampled evidence is now 75/96, with overlaps
kept separate from the primary 19/1,200 sweep. An independent full-matrix solve confirms that the
103 m/s mismatch is not a missed root in our local modal search. These
conditional matches do not establish exact historical setup or whole-family
validation. SA-13 and native UA-2 remain blocked by reference evidence.

The [AE-6 source-density correction](isae-ae6-density-20261105.md)
fixes the adapter's reuse of Weight7a air density for other models. Eight fresh
solves across all five runnable configurations now pass **116/118 computed
components at 5%**. Weight7c and Weight7d pass on both meshes; Weight7e and
Weight7f pass their first coarse comparisons. Only Weight7a's lowest frequency
still fails. All 41 focused tests and the independent full-matrix audit pass.
The selected total is **116/132** with blocked outputs; the complete declared
scope is **116/6,696 so far**, with 6,564 further slots unrun. Mesh convergence,
full sweeps, historical setup and native mode identity remain open.

| Case | Test | Passing checks | Typical error in failed checks | Status |
|---|---|---:|---|---|
| [SA-1](isae-sa-rerun-20261107.md) | Straight wing, lift and drag | 154/154 pass at 5% | — All retained scalar outputs pass. | Fresh 2026-11-07 rerun: all 22 jobs numerically valid. Historical setup qualification remains. |
| [SA-2](isae-sa-rerun-20261107.md) | Swept wing, lift and drag | 50/70 pass at 5% | Drag/CD 5.23–10.79%; failed CD median 9.25%. | Fresh rerun: all ten jobs numerically valid on default cosine meshes. Separate historical spacing diagnostic passes 70/70; production defaults are unchanged. |
| [SA-3](isae-sa-rerun-20261107.md) | Elliptical wing | 308/308 pass at 5% | — All retained scalar outputs pass. | Fresh 2026-11-07 rerun: all 44 jobs numerically valid. Historical setup qualification remains. |
| [SA-4](isae-sa-rerun-20261107.md) | Crescent wing | 528/588 pass at 5% | Failed fine-grid CL 62.6%, CD 8.09%, CDi 6.07%; small zero-incidence loads also remain. | Fresh rerun: 78/84 jobs numerically valid; six circulation failures leave 42 unavailable values. The separate drag table passes 294/294. Historical modified-spacing/I−2/K≤40 diagnostic remains separate at 562/588 under 3%; native settings remain unresolved. |
| [SA-5](isae-sa-rerun-20261107.md) | Wing with 45° dihedral | 166/168 pass at 5% | Remaining drag/CD errors 5.27% low on the coarse mesh. | Fresh rerun: all 24 jobs numerically valid; all fine-mesh values pass. Eight gains relative to the recorded 3% baseline reflect the larger allowance. Historical spacing/PG diagnostics remain separate; no production setting changed. |
| [SA-6](isae-sa6-focus-20261107.md) | Aileron rolling and yawing moments | Default frozen influences, strength 40: **470/528 pass at 5%**; previous current-wake setting: **346/528 pass** | Only roll Cl fails under the default: median 6.08%, range 5.09–8.25%. | All 88 registered states rerun and numerically valid. Primary scope follows ASWING’s documented K/F default; native startup remains unverified. The previous current-wake result and older frozen/strength-20 diagnostic (static 528/528, F1 528/528, state 2,780/3,168 at 3%) remain separate. Three models remain unpaired; derivative and mass scopes stay separate. |
| [SA-7](isae-sa7-focus-20261107.md) | Tandem wings, configuration 1 | 682/812 pass at 5% | Failed fore-wing CD median 150.46%; CDi median 5.58% (5.19–6.10%); low-lift CL 9.49%. | Current OpenSwing with documented geometry: full aircraft 406/406; fore wing 276/406. All 116 jobs valid. Original fore input agrees with report dimensions. Former mismatched-file 406/812 stays separate; +276 is a source-pairing correction, not an algorithm gain. Frozen pilots add no passes. |
| [SA-8](isae-sa-rerun-20261107.md) | Tandem wings, configuration 2 | 422/504 pass at 5% | Failed fine-grid full CL 9.07–23.94%; fore-only CL 9.91–32.29%, CD median 12.69% (6.03–15.26%). | Fresh rerun: all 72 jobs valid; full 228/252, fore-only 194/252. Forty-nine gains reflect the allowance change. Near-zero CDi/CM comparisons also fail. Earlier strength-20 and omitted-body-flow diagnostics remain separate; published body physics is retained. |
| [SA-9](isae-suite-backlog.md) | Missing upstream case | — | — Absent upstream. | Absent from the ISAE archive; excluded from the 41 families. |
| [SA-10](isae-sa10-focus-20261107.md) | Winglets and tip sails | 1,610/2,268 pass at 5% | Failed comparisons, both meshes: CL median 5.32% (max 8.19%); CD 7.23% (max 53.97%); CDi 6.53% (max 9.37%); CM 5.33% (max 10.40%). | Complete fresh scope: 269 valid states, one local-Mach rejection and 54 original attachment blockers; no timeouts. Faster Newton corrector preserves predictions within 2.93e-14 scaled error. +354 matches reflect the allowance change. Straight wing 358/378; extension 286/378; Louvered 277/378; tip sails 60/40/80 330/378, 80/60/40 359/378, 60/45/30 0/378. Original settings and denominators retained; alternate strength-20 study remains separate. |
| [SA-11](isae-sa11-lower-coverage-20261108.md) | Swept wing with Whitcomb winglet | 21/48 pass at 5% — paper-focused scope (43.75%); original archive retained separately: 1,060/9,184 (11.54%) | Paper-suite failed errors median / max: bare wing 7.12% / 18.90%; extension 7.41% / 8.76%; upper winglet 5.25% / 5.25%; upper/lower 11.82% / 36.42%. No numerical errors assigned to missing/rejected results. | Same 48 Figure 22 targets, four configurations and both speeds; CL at 1/3/5 degrees and CD at equal CL 0.3/0.5/0.7. Now 21 pass, 21 mismatch, two rejected, four missing. By configuration: 2/12, 8/12, 11/12, 0/12. Six new upper/lower runs (five accepted, one rejected) resolve four missing checks without new passes: equal-CL0.3 drag errors +11.26%/+12.38%; alpha3 lift -21.21% at240m/s, rejected at272m/s. Original CLmax=.8 and all fixed mesh/physics settings retained. Independently checked 912 hashes and all 48 decisions. [Original suite and all 984 unavailable requests preserved](isae-sa11-original-minimum-spacing-20261108.md); same-angle upper-winglet result remains 294/294, not added to either score. |
| [SA-12](isae-sa12-flap-image-wake-20261109.md) | Ground effect and flaps | Historical 3%: 2,324/4,080 pass | Historical failed CL median 4.13% (max 4.58%); CD 9.63% (max 99.8%); CDi 4.7% (max 7.8%). Fresh paired flap baseline fails CD by 6.73–7.86%; frozen alternative fails CDi by 5.03%. | Kept open. Paired flap pilot: baseline 10/16, frozen/zero-pitch 11/16 at 5%. Four physical inviscid controls agree with native AVL within 0.000002%. Endpoint-only image diagnostic matches sampled flap CL/CD/CDi within 0.93% but violates ground impermeability; not adopted, no new ISAE passes. Historical K/F, Euler pose and modified image implementation remain unresolved. |
| [SA-13](isae-sa13-discrete-bridge-20261109.md) | Airships and fuselages | 0/612 pass | — Native error percentage unavailable: the red pressure curve equals shifted squared radius slope; its mapping to Cp remains unresolved. | Kept open. Full current JSON solves reproduce 180 valid lift stations on explicit linear-radius reconstructions. All 239 finite red-curve values have geometry identities. Full native setup/output mapping and modified continuous curves remain unresolved; 136 entries unavailable. All 22 adapter checks remain separate from native comparisons. |
| [SA-14](isae-sa14-current-polar-20261109.md) | Swept wing–fuselage interference | 281/360 pass | Failed finite-body CL median 17.86%, max 2395.72% near zero; absolute CL errors 0.00667–0.00869. Two constant-body tiny-reference failures differ by 7.99e−10. | Full current CL-table refresh at 5%: 291 valid states; 69 N128 local-Mach rejections at ≥18.5°. Eight finite-body low-angle failures remain. Of 281 raw-table matches, 188 use converged native rows and 93 use conv=0 rows; all 360 slots retained. Current same-data 3% count is 277; historical 3% count was 115. Exact historical setup and local-load agreement remain open; no physics change or full-family validation claim. |
| [SA-15](isae-sa15-suite-20261105.md) | Diamond joined-wing interference | Historical 0/182 blocked; shared conditional scope 84/182 at 5% | Failed CD median 7.79%, max 16.63%; CL 8.49%; efficiency 12.73%. Tiny lateral residuals remain. | All 26 runs and 312 numerical checks pass; independent summary verified. Cm 26/26, CL and efficiency 24/26 each. Of 98 failures, 78 are tiny lateral residuals. Moderate-angle drag error exists without stall; high-angle sensitivity is mostly stall leakage. Original .set/output identity remains unverified. |
| [UA-1](isae-ua1-checkpoint-periodic-browser-20261103.md) | Plunging airfoil, 2D | 148/148 harmonic; 12/12 linear phase; 4/4 zero-incidence periodic; 1/1 inclined first-cycle; 2/2 inclined periodic; 1/1 browser periodic checks pass; 72/72 supplemental stall states; 1/1 stalled first-cycle checks pass; 1/1 stalled periodic checks pass; 1/1 stalled browser checks pass | Current-source harmonic amplitude error 0.0016521%; phase 0.0006092 degrees. Current repeated-stall fine lift/circulation/rate/pressure errors: 0.01688% / 0.01152% / 0.03332% / 0.06629%. All 12 accuracy gates pass. Coarse rate/pressure errors 0.1210%/0.2564% remain recorded; refinement resolves them.  Current browser errors: 0.01688% / 0.01152% / 0.03332% / 0.06629%; 13/13 gates pass. | Equation references, not native executable output. Current-source harmonic 148/148 and four-cycle stall supplement are verified; the latter checks 3,842 states and 190 restart boundaries. Complete stalled-browser worker verification now passes: 2,561 states, 319 restart boundaries, maximum scaled Python difference 2.727e-09. Full-history UI verification is a separate open scope. Other counts retain earlier attached-flow, phase and runtime studies. Supplemental stall limits are declared as ±1.5. Whole-family and native-ASWING validation remain incomplete; prior failures and studies are linked in the report. |
| [UA-2](isae-ua2-harmonic-matrix-20261103.md) | Plunging wing, 3D | 0/222 native; 16/16 zero-incidence first-cycle; 2/2 zero-incidence periodic; 64/64 inclined states; 2/2 inclined first-cycle; 1/1 inclined mesh; 2/2 inclined periodic; 1/1 inclined periodic mesh; 1/1 browser periodic checks pass; 30/30 independent harmonic matrix checks pass; 6/8 current Python and 6/8 current browser interval checks pass | Periodic lift/circulation/rate errors about 0.00379% / 0.00845% / 0.00348%; position 0.0349% of heave amplitude. Periodic mesh change 0.0495% (limit 0.1%). Earlier uniform rate error 1.53% and coarse periodic position error 0.1385% retained; native comparisons blocked.  Current harmonic maximum scaled complex difference 5.455e-11.  Legacy local acceleration 2.87–2.89e-8 m/s² exceeds the 2e-8 absolute limit; its zero target has no meaningful percentage error. | Inclined periodic checks pass on 20/40 strips at one condition: 9°, k=0.95, A/c=0.5, eight cycles. The 40-strip spatial study passes 18 gates; the 20-strip built worker passes 17 gates with 5,281 snapshots audited and no rejected steps. The original final cutoff-verifier failure is preserved; corrected assessment uses the retained output with unchanged physics and tolerances. Time-plot scrubbing is optimized with all samples retained; full-app replay/export passes for one 17-state segment. Exact metadata sharing passes 330 segment / 660 checkpoint comparisons and 33-state UI continuation/export. The full 5,281-state physical history now works in the actual workbench through a 254.7 MB indexed archive. Lift opens in 0.95 s; an unindexed-quantity scan takes 96.1 s with progress. Complete state/checkpoint samples, 33-state archive save/open/continuation, distribution CSVs, small JSON project save/open and runtime Undo load pass; 66 focused tests pass. Large project attachments, automatic durable segment storage, broader conditions and native provenance remain unfinished.  Current displacement correction: 27 focused tests and all four fresh intervals pass;two retained legacy failures; all intervals computed. Current public/dist kernels and browser verification are complete. |
| [P-1](isae-p1-aswing-current.md) | Static propeller, blade-count effects | 110/110 pass | — No failed CT checks; maximum absolute error 2.22e-16. | All six stored thrust curves match using recorded power inputs. |
| [P-2](isae-p2-recovery-20261105.md) | Propeller in forward flow | Declared input reconstruction: 312/312 pass at 5% | — All pass; maximum discrepancy 0.633%. | All 24 archived model curves and 52 coordinates included. Primary CP tables recovered; drag-input reconstruction uses only original forward-flow measurements and reproduces all twelve printed coefficients. Exact historical fitting/driver settings remain unavailable. The polynomial curves include the report's variable-CdA extension; no independent power or whole-family validation claim. |
| [P-3](isae-suite-backlog.md) | Propeller P-factor in oblique flow | Not registered | — No registered comparison. | Comparison adapter missing. |
| [P-4](isae-suite-backlog.md) | Static propeller jet and swirl | Not registered | — No registered comparison. | Comparison adapter missing. |
| [P-5](isae-suite-backlog.md) | Forward-flow propeller jet and swirl | Not registered | — No registered comparison. | Comparison adapter missing. |
| [AP-1](isae-suite-st2-ap1-20261026.md) | Propeller jet effect on wing lift | 29/15,470 pass at 5% | Failed avg CD median 56.39%, max 71.20%; only three header states. | Saved 78 computed header outputs rescored; 15,392 unavailable outputs remain. Header input echoes are not independent physical tests. |
| [AP-2](isae-suite-ap2-20261027.md) | Propeller position and wing lift/drag | 84/248 pass at 5% | Failed CL/CD ratio median 37.98%, max 148.52%; failed CD 16.61%. | Saved 242 computed outputs rescored on both meshes; six unavailable checks remain. Full original position grids retained. |
| [ST-1](isae-st1-thin-modal-20261109.md) | High-aspect-ratio structure | 201/201 static; 20/22 named modal at 5%; separate archive: 9/200 | Static max 0.762%; matched modal max 1.096%. Two literal reference conflicts: coupled torsion label 44.305%, thin-down printed 218 Hz 90.018%. The 95 Hz frequency exists within 0.027%; thin 21.760 Hz agrees with the postprocessor's 21.8. Raw archive position failures: median 23.43%, range 12.85–35.85%. | Primary mechanics scope is now 221/223: all nine static curves plus all 22 report frequency cells. Thirteen modal matches use documented cross-ply/thin-blade reconstructions. All configurations computed; one label and one printed-value conflict retained. Twenty-two compared shapes agree across meshes (MAC >0.999867), with frequency changes <0.586%. Thin first-torsion identification permits the root sign change described in the primary literature. Original 200-slot inventory remains separate and intact. No production tuning or experimental fitting. |
| [ST-2](isae-st2-modal-current-20261109.md) | Pazy wing structure | Archive 56/490; mechanics static 77/77 + modal 14/14 at 5% | Static median 0.0645%, max 0.4217%; current modal median 0.0858%, max 0.8657%. Supplementary span mechanics max 0.4641%; lone mechanical failure is root y, absolute error 6.89e−17 m. | Primary mechanics scope is 91 comparisons, including all six static curves and both seven-frequency modal exports. Static tip-pylon reconstruction has independent native moment/force support; modal files are literal. All numerical and final mesh/shape gates pass. The [full 43-job replay](isae-st2-mechanics-complete-20261109.md) reproduces these counts, with combined-report authentication and 98 focused checks passing. The separate [spanwise reconstruction](isae-st2-span-profile-20261109.md) matches 275 of 368 fields, retaining 92 unavailable display values; every internal-force/moment value matches printed precision. It adds no primary votes. Original archive remains separate: 56 tiny real parts and 378 unavailable outputs retained. Literal attachment compatibility, historical settings and full-family validation remain open. |
| [ST-3](isae-st3-static-curves-20261109.md) | Low-aspect-ratio structure | Mechanics static 84/86; modal 9/9 at 5%; historical static 930/1,080 | Current static median 0.08725%, maximum 0.43472%; modal median 0.08031%, maximum 2.6592%. Two static references are unavailable; no readable target fails at 5%. | Primary mechanics scope is 93/95: all twelve published static curves and nine original modal frequencies. All 80 fresh static states, 86 mesh checks, six modal states, nine shape/mesh and 144 matrix checks pass. Static scripts retain their signed loads and 1.3734 torque-axis factor. The two source-clipped values remain required. Historical snapshot stays separate and unchanged. Native startup, modal labels, incompatible test.asw/test.txt, legacy compatibility and new static catalog integration remain open. No whole-family pass is claimed. |
| [ST-4](isae-st4-mechanics-current-20261109.md) | Concentrated weights and modes | Mechanics frequencies 66/72 at 5%; separate named-mode check 54/72; archive vacuum 93/3,749; historical conditional airflow 4/30 strict; supplementary direct exports 31/31 | Primary median error 0.2028%; six failures median 14.073%, range 5.556–19.703%. Direct-export maximum error 0.8128%, with mesh change <0.06841% and continuous-reference error <0.05472%. Historical airflow slow-root errors remain 43% / 139%. | Primary is all 24 published three-frequency sets, compared by ascending rank on both meshes. All 64 original-model states, 72 primary mesh/shape checks and 2,048 matrix checks pass; 18 focused checks pass. The [direct-export refinement](isae-st4-native-refinement-20261109.md) closes all 31 original frequency ordinals with 320 matrix checks; it overlaps and adds no primary votes. All original values, named-mode results, old 3,656 unavailable archive outputs and failed attempts remain. Recurring integration and the full fresh native replay are complete; the full paper replay remains pending. The source-row audit documents mixed positions and a native/CSV inconsistency without replacing targets. Unloaded input, three position/data conflicts, native settings/identities and airflow remain open. |
| [ST-5](isae-st5-mechanics-current-20261110.md) | Joined-wing structure | Mechanics **16,687/16,688** at 5%; historical strict: rigid 13,833/25,920; roller 14,708/25,920; forward-only 10,670/18,792; elliptical 13,583/25,920. | Sole primary failure: near-zero Fn differs by 0.0000381 lb (13.12%). Maximum final mesh change 0.03865%. Converged paper moments differ by at most 0.412% of curve peak (descriptive). Historical full-field/finer-grid errors remain in the linked reports. | All 16 original static cases qualify: 80 physical states on five grids, all 224 final convergence checks and six accounting tests pass. Explicit primary scope change: each computed structural observation once, native match on archived stations plus independent convergence. Historical fields, repeated meshes, unbound outputs and unavailable modal evidence stay separate. No production physics changed. The [paper overlay](../../artifacts/isae/st5-convergence-current-20261109/converged-paper-moments.png) retains all twelve joined-wing curves. Modified-link versus literal-roller law, exact node generation and reaction display remain open; the [recurring runner](isae-st5-recurring-20261110.md) now registers all sixteen cases, with a four-case fresh replay and independent import verified. The [force audit](isae-st5-force-audit-20261110.md) verifies decoding; four coordinate probes explain at most 9.44% of the miss and add no passes. All sixteen [browser presets](isae-st5-browser-presets-20261110.md) are prepared and source/data checked; UI execution remains held. The [normal-load audit](isae-st5-reaction-display-20261110.md) finds at most 0.01966% error on all 992 physical intervals; 200 display-only rows remain separate and no primary votes are added. |
| [ST-6](isae-st6-elastica-20261104.md) | Column buckling | No native target. Elastica: 2/2 static, 4/4 modal, 1/1 offline worker case. Distributed-mass modes: 8/8 branches. Self-weight: 2/2 fine static, 2/2 modal bracket, 1/1 growth-rate and 2/2 browser cases. Earlier analytical cases: antisymmetric 11/11, symmetric fixed-fixed 9/9, cantilever 19/19. | Fine elastica position error ≤0.003899% of length; pole error ≤0.012321%. Retained N8 elastica pole errors 0.437%/3.246%. Distributed-mode fine errors ≤0.02244%, mesh change ≤0.06735%. Earlier self-weight coarse N8 load/shape errors 0.6345%/0.8257% remain recorded. | [Elastica study](isae-st6-elastica-20261104.md): mirrored ±99° bent equilibria, both stable mode pairs, mesh/shape/mirror checks and 40 native pencil checks pass. Eight reference tests and 21 offline worker groups pass; browser scope is the coarse control. [Distributed-mode study](isae-st6-distributed-modes-20261104.md) covers the first four straight-column branches at two loads in native Python. Earlier [self-weight browser verification](isae-st6-self-weight-20261104.md) retains 430/430 checks. Original fixtures, dynamic buckling trajectories, other branches and native ASWING agreement remain open; the archive contains no native model/output pairing. |
| [AE-1](isae-ae1-full-current-20261110.md) | Pazy wing steady deflection | Current frozen **1,170/1,200 at 5%**; historical updated baseline 98/1,200 strict | Six near-zero Z failures: 31–35 µm, 7.88–46.12% (median 14.00%). Computed median error 0.14299%. | Both complete positive-speed sweeps checked on both meshes: 1,176 computed values, zero unrun, 24 unknown-start values. All 5,684 physical checks pass. All 504 computed 7° comparisons pass. Fine-mesh tip-Z RMS error 0.240/0.122 mm at 5°/7°. Exact native settings remain unknown. |
| [AE-2](isae-ae2-sparse-recovery-20261111.md) | Low-aspect-ratio wing steady deflection | 2,070/2,200 at 5% (last full replay, before recovery adoption) | Twenty-two computed failures: eighteen at 5° have median 267.995%, range 227.303–356.743%; four at 1°/16 m/s have median 12.2094%, range 8.6983–15.7294%. | 523 states /2,092 computed values; 12 unresolved outputs and 96 unavailable references retained. Exact sparse allocation recovery adopted with 16 regression tests and 20 AE-2 control checks passing. The 20 m/s fine-grid case still stops at 92.1631% load due to nonlinear nonconvergence. No new native votes; full post-adoption replay pending. Focus moved to AE-3 at user request. |
| [AE-3](isae-ae3-frozen-influences-20261111.md) | Aileron reversal | **434/725 pass at 5%** (frozen influences) | Cl median 51.42% (23.38–182.84%); CX 51.04%; failed non-tiny derivatives 52.04% (7.52–6188.16%). Mass/inertia: 55/78 failed references <=1e-8; other 23 median 228.62%. Largest mass cross-term error 8.92645e-5. | All 612 native comparisons computed: 50/72 coefficients, 174/252 derivatives, 174/252 mass properties and 36/36 rates pass. 178 measured mismatches; 113 source-blocked embedded values retained. Documented frozen default replaces the adapter override; original model and numerical gates unchanged. 870 base-check records (including inherited evidence), 258 auxiliary checks pass. The earlier 83 passing regressions are supplemented by the now-passing summary check; four reporting/registry checks were rerun after a standalone import-path fix. All numerical children reaped. Full conditional sweep and refined endpoint remain separate diagnostics. Frozen320 computes, but cosine-grid Cl error is nonmonotone (28.49%, 12.99%, 24.31%). Fully nested164/328 changes only0.64% but retains36–37% native error; rigid-grid changes stay <=0.102%. Roll-feedback audit adds92 passing checks: high-speed acceleration amplification3.12–3.16x is confirmed nonlinearly within0.00013%. Native coefficient/derivative ratios are similar; remaining nested82/164 fixed-acceleration CldF1 errors26.95%/34.10% remain open. Forcing/spanwise audits pass 96/129 checks; output-chain and rigid controls add 175 passing checks. Mesh changes arise mainly through circulation redistribution; direct projection contributes <0.02%. Constrained sparse warm correction adopted: 43 regressions and 46 numerical checks pass; two roll-target jobs take about 5.4s versus 24.7s in saved dense runs. No native votes added; cold/checkpoint paths unchanged. Eight independently reconverged control solves pass 130 checks; both response conventions match their tangents, while the conditional held-acceleration CldF1 gap stays 26.95%. Fourier19/38/76 gives conditional high-speed Cl errors12.56%/10.53%/5.70%, but full82 returns28.49%; no mode-convergence claim or default change. Continuation origins are now saved; the split38-mode state matches all1,035 components exactly. Fixed K38 on82/164/328 gives errors10.53%/22.12%/25.17%; the finest pair changes2.43%. All135 physical/mesh checks pass. Exact Fourier assembly optimization cuts498 geometry groups to18, with17 native regressions and1,035-component cold parity. K76 on82/164/328 gives errors5.70%/20.58%/24.16%; final mesh/mode changes2.88%/.81% meet5%. All150 physical/setup and16 K76 matrix checks pass. Exact cold replay fails by7.99e-14 but existing 2e-10 parity passes. The current-kernel pointwise replay passes 47 checks and retains the 8.97% fine-grid gap. Independent fields/loads pass 38 checks; the coupled gap is 10.56 times the fixed-shape circulation effect. Failed zero-core reference controls are retained and resolved by quadrature/90-digit arithmetic. The full coupled tangent adds 38 passing checks and predicts the Cl increment within 0.062%; structural/frame gains are 3.33x/3.17x. Aileron-boundary residuals dominate, while tips contribute -5.07% of the signed correction. No new primary votes or representation-convergence claim. Historical inputs/MM constraints and ASWING-m data remain open. |
| [AE-4](isae-ae4-40-43-20261113.md) | Pazy wing flutter | Shared declared sweep: **705/1,200 so far at 5%**; earlier overlapping sample: 86/108 | 23 paired components fail: median 9.02%, range 5.50–117.18%. All new 40–43 m/s comparisons pass; largest error 0.664%. | Primary selected 705/756: 728 paired, 16 unmatched, 12 unknown initial; 444 unrun. New batch passes 48/48; 16/24 mesh gates pass. All integer speeds 40–108 have runs on both meshes, with unresolved native pairing at 103. Both middle-pair components fail the mesh gate at every new speed. Earlier first-crossing and 79 m/s frequency failures remain; at 96 m/s the higher pair decays in native ASWING but grows on cosine80/160. [Independent complete-pencil audit](isae-ae4-aerodynamic96-20261113.md) passes 4,708 A/M columns and 5,196 checks without new native votes. Next fill 36–39 m/s. Preserve historical settings, spatial convergence, 9,480 historical components and later branches/time histories. |
| [AE-5](isae-ae5-sources-20261105.md) | Low-aspect-ratio wing flutter | 0/587; source pairing blocked | — No valid paired solver-error percentage. | All 532 modal components and 55 ASWING boundary values retained. Driver has 22 speeds versus 29 modal points; literal GJ/EInn differ from the report. Unchanged literal source solves at IAS9/beta15, with all 16 full-matrix modal checks passing; this is a diagnostic, not a native reference pass. No whole-family validation claim. |
| [AE-6](isae-ae6-density-20261105.md) | Nacelle position and flutter | Shared declared: 116/6,696 so far at 5%; computed sample 116/118 | Only Weight7a lowest frequency fails: 39.54–42.40% low, median 40.97%. | Fixed a comparison-setup density error. Eight fresh solves: Weight7a 22/24, Weight7c 28/28, Weight7d 36/36 across two meshes; Weight7e 14/14 and Weight7f 16/16 coarse. Selected total 116/132 includes 14 blocked slots; 6,564 further slots unrun. All 41 focused tests and full-matrix audit pass. Mesh gates remain 5/12, 7/14, 6/18 for a/c/d; e/f fine meshes unrun. Weight0 has 1,200 malformed-model slots. ST-4 duplication, full sweeps, historical settings, native mode identity and flutter onset remain open. |
| [AE-7](isae-suite-backlog.md) | Limit-cycle oscillations | Not registered | — No registered comparison. | Comparison adapter missing. |
| [FFWT-1](isae-suite-followup-20261026.md) | Folding wingtips, static behavior | 18/64 pass at 5% | Failed root moment median 7.92%, max 10.43%. | Five retained valid equilibria (20 scalar outputs) rescored. Eleven other jobs failed or timed out; mesh pairs remain unavailable. |
| [FFWT-2](isae-ffwt2-history-refinement-20261106.md) | Folding wingtips, rolling performance | At 5%: equilibrium start 10/4,005 (10/25 computed); separate jig/restart scopes 5/4,005 (5/25 computed), including full-startup dt=.005 | Full-startup refined failed acceleration median/max 160.56%/199.81%; aircraft bank 7.49%/7.56%; sensor 2 bank 64.83%/73.30%; sensor 3 bank 31.83%/32.12%. Earlier scopes retained. | New full-startup grid accepts 408 steps in 42 serial jobs without rejection; only 1/5 full-history numerical accuracy gates passes. Native agreement remains roll rate only. Independent aero audit passes 27 snapshot records and eight reference tests; sampled Cl ≤0.3900, no stall. Earlier mechanics audit covers 204 states; local restart refinement passes 5/5. All histories end at 2.04 s, retaining 3,980 unrun values per scope. Finer full-history time/mesh refinement, historical startup/settings, other models and shared adapter remain open. |
| [FFWT-3](isae-ffwt3-sources-20261106.md) | Folding wingtips, qualitative gust response | 0/36,462 blocked | — No computed values; error percentage unavailable. | All 27 history/driver jobs registered: 35,256 retained native values plus 1,206 missing-reference slots. All six literal models have out-of-range joint stations; one time grid differs, one driver and one output are missing. No source repair or endpoint clipping is assumed. |
| [FFWT-4](isae-ffwt4-sources-20261106.md) | Folding wingtips, quantitative gust response | All 40 archived histories: 200/8,000 at 5%; fixed-wing subset: 200/1,600 | Complete Fixed-1 median/max error 0.523%/0.681%; finer partial history 0.763%/0.893%. Frozen 419-node initial moment error 0.3842%. Its seven failed original mesh checks change 0.142–0.256%; seven failed sided load components change 0.112–0.664%, against 0.1%. | All five drivers and 40 histories are inventoried. Complete Fixed-1 matches 200/200; its finer history remains at 1,162/1,592 steps with 146/146 reached matches, counted once. Literal PM2 models use qualified rigid pylons; their 4,800 gust targets remain uncomputed. The [memory fix and 419-node equilibrium](isae-circulation-finish-memory-20261107.md) complete 19 serial jobs; 50 Python, seven WASM and 19 built-browser checks pass. Frozen 211/419 passes 0/7 original mesh gates and 11/18 sided load gates. Field/mesh accuracy, other histories, historical K/F and attachment semantics, and shared registration remain open. |
| [FFWT-5](isae-suite-backlog.md) | Folding wingtips and flutter | Not registered | — No registered comparison. | Comparison adapter missing. |

[Detailed evidence and investigation history](isae-status-notes.md).
Use `--relative-tolerance 0` to restore strict reference acceptance.
