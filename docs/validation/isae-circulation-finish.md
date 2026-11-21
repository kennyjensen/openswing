# Circulation correction at the end of coupled equilibrium

2026-10-25. The ISAE fine-mesh comparison exposed a numerical convergence
problem in the browser and in selected native states. OpenSwing now tries a
circulation-only correction at fixed geometry when the other coupled equations
already satisfy the original internal tolerance. It accepts that candidate only
after a fresh evaluation of every physical equation meets the unchanged target
and reduces the full residual norm. No force law, input geometry or geometry formulation, vortex core,
discretization, load assumption or tolerance was changed.

The current built web interface completes the formerly stalled nominal-120,
5-degree, 30-m/s case in **7.97 seconds**, after a separate **14.95-second**
runtime startup. The offline browser check passes 690/690 checks and compares
18,969 numeric result values with the current native result. The largest
absolute difference is 3.38e-10; every value satisfies the predeclared 2e-8
absolute plus 2e-8 relative comparison tolerance. An independent saved-data audit passes another 375 checks, including full force/moment balance. The browser's reported full residual is 2.43e-14 and the independently reduced norm of the saved fresh native residual is 1.92e-14. Both satisfy the unchanged internal 1e-12 target; the output comparison tolerance is a separate check. The current worker's 111
module hashes match the production and served sources. The rendered wing and
wall were also visually checked. These timings are measurements on this host,
not a general browser performance guarantee.

## Evidence and cause

The retained built-browser attempt at nominal 120 panels, 5 degrees and 30 m/s
timed out after 120 seconds without a final result. The same captured request
completed natively in 3.478 seconds and four load steps. All 111 Python kernel module bytes and
physical inputs matched; scalar versus object panel settings and an explicit
zero circulation-mode entry are equivalent representations.

A bounded WASM diagnostic stopped before the first continuation retry. At
half load its full residual stalled around 1.07e-12, slightly above the internal
1e-12 target, while increasingly small line searches were accepted. A saved-state
probe located the remaining error in circulation rows. Both the approximate
and full coupled Newton corrections perturbed the geometry by about 2e-16 and
made that remaining flow residual worse. Switching to the full tangent alone
did not fix this state.

Holding the mechanical state bitwise fixed and correcting circulation reduced
the fresh full residual from 1.094600706403649e-12 to 5.989299672653283e-14.
The changed circulation still changes aerodynamic loads; the candidate is
accepted because those loads also satisfy the full coupled equations. The
diagnostic does not establish a universal roundoff bound or guarantee every
future aircraft will converge.

The original speed sweep retained two ordinary nonconvergence failures:
nominal 120, 5 degrees, 4 m/s; and nominal 60, 7 degrees, 40 m/s. Neither failed
state was accepted or counted as validated. The original sweep, sources,
partial plots and independent audit remain in the evidence archive. A separate
current-source sweep starts all 198 states cold, including both baselines.

## Implementation and regression checks

Only `openswing/structured_static.py` changes among the 111 numerical modules.
This finishing step applies to the structured cold-equilibrium path; requests
with an initial state or unsupported options still use the existing full solver.
The private helper refuses an existing lagged-field context, gates mechanical
and appended operating rows, captures fresh fixed-geometry circulation
derivatives, and changes only circulation coordinates. It exits that capture
before evaluating the candidate's complete residual. A singular or unavailable
derivative, nonfinite correction or failed physical check leaves the usual
coupled Newton path available. Cache contexts are restored and invalidated.

The target remains `min(requested_tolerance, 1e-12)`. No candidate is accepted
on a circulation-only norm, correction size, elapsed time or a stored residual.
The source transition is recorded in the promotion receipt and both served
kernel copies match the production sources.

Seven new checks pass natively and in WASM. They cover the actual saved browser
stall, a fresh-network residual, bitwise unchanged mechanical state, rejection
when corrected circulation unbalances real nodal loads, appended operating
rows, lagged contexts, and unavailable/singular/nonfinite derivatives. The
targeted native suite has 44 distinct passing checks across focused runs.
One existing hinged-model test failed unchanged production as well: it assumed
four load steps and tangent reuse despite adaptive hinge stepping. Its assertion
now retains the physical equilibrium comparison and respects that existing
hinge behavior; the focused test passes.

Two private candidate cold cases (4 and 30 m/s at nominal 120) completed in four
load steps in both runtimes. Their 18,972 numerical result values per case agree
within the declared 2e-8 absolute plus 2e-8 relative comparison tolerance. These
private runs preceded the final context guards; the current-source scientific
sweep and actual built-browser check are reported separately.

This is a numerical implementation correction. Experimental agreement,
historical operating-state reconstruction and full ASWING compatibility remain
separate validation questions.

## Reproduction and evidence

Run the focused native fixture checks with
`python -m pytest -q tests/test_circulation_finish.py`. Run their browser-runtime
mirror with `node scripts/test-circulation-finish-wasm.mjs` after installing the
project dependencies. These checks use a diagnostic iteration state, not an
accepted equilibrium checkpoint.

The [implementation summary](isae-circulation-finish.json),
[source transition](isae-circulation-finish-source.json),
[independent browser audit](isae-circulation-finish-browser-audit.json) and
[conditional ISAE curves](isae-ae1-literal-curves.md) describe the separate checks.
The [raw evidence archive](isae-ae1-literal-curves-20261025-evidence.zip) retains
the failed attempts, private variants, current browser results, numerical
inputs, source snapshots and terminal process receipts. It does not bundle
Python/Pyodide packages or browser executables. No hosted deployment is claimed.
