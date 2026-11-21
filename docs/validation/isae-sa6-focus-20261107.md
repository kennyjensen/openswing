# SA-6: wake choice isolates the remaining roll discrepancy

2026-11-07. Frozen influences are now the default for new Python/browser
analyses and the registered SA-6 comparison, following the user's instruction
and ASWING's documented K/F default. The primary count is **470/528** native
static comparisons at 5%, retaining stall strength 40. The previous
current-wake setting remains a separate historical comparison at **346/528**.
All **58 remaining frozen-setup failures are rolling moment**, with absolute
relative errors **5.09–8.25%**, median **6.08%**. This is a comparison of two
complete settings, not a combination of their best outputs.

| Native output | Current-wake baseline | Frozen influences, strength 40 |
| --- | ---: | ---: |
| Axial force CX | 0/88 | 88/88 |
| Side force CY | 88/88 | 88/88 |
| Lift CL | 86/88 | 88/88 |
| Rolling moment Cl | 88/88 | 30/88 |
| Pitching moment Cm | 84/88 | 88/88 |
| Yawing moment Cn | 0/88 | 88/88 |
| **Total** | **346/528** | **470/528** |

The wake change gains 182 comparisons and loses 58. Baseline failed CX errors
have median 17.43%, range 9.56–24.64%; Cn errors have median 23.74%, range
18.26–31.67%. The two CL failures are about 5.27%; four Cm failures are
5.10–5.96%. Frozen influences resolve those failures, while reducing roll
agreement. They do not independently validate the entire case.

![Fine-mesh coefficient errors](../../artifacts/isae/sa6-wake-comparison-20261107/coefficient-errors.svg)

## What changed, and what did not

The retained driver never toggles OPER/K/F. The manual displays F enabled
and defines its coefficients at undeformed geometry and zero wind angles.
That supports the frozen setup as a documented-default reconstruction;
it does not recover the original startup state. The progress dashboard now
selects frozen strength 40 explicitly, retaining the same 528 targets. The
+124 passes reflect adoption of that documented default; no equations, stall
parameters or tolerances changed. Current-wake and strength-20 alternatives
are not combined with this total. Explicit choices in saved cases remain
unchanged, and older saved states without the flag retain current influences.
Newly planned optional F1/state/mass scopes inherit the frozen setting, but
no derivative or mass pass count is changed without its own fresh comparison.
Other families retain their recorded explicit comparison settings and scores;
this default adoption is not a new execution of the full ISAE suite.

Both alternatives preserve every literal model, original control command,
12-degree incidence, 20 m/s speed, density, reference axes, section properties,
stall strength 40, width 0.05, meshes, and numerical validity gate.
The baseline rescored at 3% is still 290/528; frozen strength 40 is still
388/528. These reproduce the earlier results. The baseline's 56 new accepted
checks therefore come from the user's 5% allowance, not changed physics.

The earlier frozen/strength-20 diagnostic remains 528/528 static and
528/528 F1 matches, with 2,780/3,168 state matches at 3%. The native strength
is unverified. That alternative is not adopted as a production correction.
Three models without paired numerical exports and the separate derivative
and mass scopes remain open.

The [independent section reference](frozen-stall-reference-20261107.md)
checks both frozen and wind-aligned smooth stall against a separate scalar
solution, including both control and incidence derivatives. All 14 new tests
pass; no production correction follows from that check. The finite-span
roll discrepancy and historical setup remain unresolved.

## Execution and verification

After changing the defaults, the registered adapter was rerun for **all 88
states** in four serial batches of 22, one BLAS thread and a 768 MiB cap.
All passed their numerical gates; total batch time was **24.54 seconds**.
A separate audit reparsed all native tokens, confirmed **470/528**, retained
three unpaired inventory models, and matched the prior frozen study within
**3.34e-16** in every coefficient. The [new plan](../../artifacts/isae/sa6-frozen-default-20261107/plan.json)
and [full comparison](../../artifacts/isae/sa6-frozen-default-20261107/analysis.json)
retain the new source hashes. The prior sources are copied in that artifact's
`before/` directory; historical studies and progress observations are untouched.
The focused native regressions passed **216/216**, covering the default,
explicit opt-out, old saved conditions, physical frozen loads, and SA-6
static/control/state/mass registration and comparison contracts.
Additional flow-survey, saved-time and equilibrium checks cover 23 passing
cases. Three survey fixtures initially assumed current-wind volume sources;
they now independently integrate both frozen and current source conventions
(all six parameterized checks pass). No physical equations or gates changed.
The browser migration test passes: a new exported case records frozen
influences, while an older imported case missing the setting restores current
influences. Two initial browser-launch failures were local Chromium dependency
and resource-path issues; the existing complete Chromium installation with its
local shared libraries runs the test successfully.

The preceding paired study completed **176 fresh cold solves** in eight serial batches of 22 calls,
using one BLAS thread and a 768 MiB address-space cap. Each batch has a
60-second external timeout; none fails or times out. Summed batch time is
175.52 seconds, including each batch's imports. Every model and circulation
solve is initialized afresh; only interpreter imports are shared.

The preceding 22 separate-process baseline solves take 173.97 seconds in the
runner timing scope. All 22 agree with the new serial results to within
2.78e-17 scaled error. The solver-free audit reparses all original native
coefficient tokens and independently accumulates the saved strip wrenches;
maximum coefficient reconstruction error is 8.88e-16. It checks all 1,056
alternative/reference decisions, every source hash, and all eight completed
batch receipts. The repeated alternatives represent 528 independent static
comparison slots, not 1,056 independent reference targets.

## Next focused work

The [complete default-setting F1 comparison](isae-sa6-frozen-f1-20261107.md)
now passes **370/528** derivative checks separately from the static score.
All 88 bases are numerically valid, and all 48 selected nonlinear-stencil
coefficient checks pass. The largest rolling-sensitivity discrepancy occurs
in the 35%-chord high-deflection tail, where the computed lower-stall
transition becomes influential. This supplies a more specific source-audit
lead; it does not justify a parameter change or add static passes.

The [complete independent finite-wing reconstruction](isae-sa6-frozen-independent-20261107.md)
now verifies the current 88 static/F1 states and four independent cold solves.
An inferred native profile-normal force component differs by 11.92–12.84%
under the default, beyond rounding uncertainty. Use that force/moment identity
to distinguish stall/setup and native load-convention differences; the tested
local equations and vortex fields supply no production correction.

Prioritize the rolling response of the post-stall aileron with frozen
influences at documented strength 40. Establish a mathematical or source
explanation for its 5–8% discrepancy before changing a coefficient or an
accepted setting. The existing strength-20 match is useful evidence but is
not proof of the original native parameter. Reuse the completed studies of
mesh, Fourier closure, stall speed/width, initialization and rate conventions;
do not repeat their rejected branches without new evidence.

The broader SA rerun is deferred after 457 jobs, including its retained
SA-10 timeout and incomplete stopped job. No solver is left running from
that batch. The project goal and full SA-6 validation remain incomplete.

- [Complete paired plan](../../artifacts/isae/sa6-wake-comparison-20261107/plan.json)
- [Every comparison and failure percentage](../../artifacts/isae/sa6-wake-comparison-20261107/analysis.json)
- [Execution receipt](../../artifacts/isae/sa6-wake-comparison-20261107/terminal.json)
- [Serial producer](../../artifacts/isae/sa6-wake-comparison-20261107/run.py)
- [Independent audit](../../artifacts/isae/sa6-wake-comparison-20261107/audit.py)
- [Separate-process baseline control](../../artifacts/isae/sa6-rerun-20261107/report.md)
- [Earlier frozen/strength-20 comparison](isae-sa6-frozen-stall-20261031.md)
- [Earlier derivative comparison](isae-sa6-frozen-derivatives-20261031.md)
