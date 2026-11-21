# Section stall parameters

The workbench exposes the published leakage factor `K_s` and transition width
`delta_cl` under **Section stall parameters**. The defaults remain 40 and 0.05.
Both are dimensionless. Larger leakage factors reduce the post-stall slope;
smaller positive widths sharpen the transition. Zero factor removes leakage.
Section `CLmin` and `CLmax` remain ordinary `.asw` beam properties.

The [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
section 5.7, equations 202–204 and printed pages 40–41, specifies the law and
these approximate default choices. This adds controls for existing numerical
parameters; it does not change the published leakage or pressure-drag equations
or claim a particular original-ASWING menu setting. The inspected primary PDF
has SHA-256 `ff3aadbf986644697e22d8d4e65ffcd596b279b45f39bba7b61ac0e58d22ee4c`.

Each calculation receives the chosen values. Edits invalidate earlier results.
Editable cases and computed archives retain the settings, and cases lacking
the new fields restore the original defaults. A time launch from a saved
equilibrium uses that equilibrium's parameters, shown with its other saved
conditions. A new steady, modal or frequency calculation uses current controls.
Turning stall off retains the parameters for later reuse.

The kernel now rejects nonnumeric, Boolean, nonfinite and negative factors,
and nonnumeric, Boolean, nonfinite or nonpositive widths. Invalid dormant
parameters are rejected even with stall disabled. The model's valid-input
equations and defaults are unchanged. Their numerical evaluation now avoids
overflow for very narrow transitions and cancellation for very broad ones.
The logarithmic difference is evaluated with `log1p`/`expm1` when its arguments
are close and with the positive linear part extracted when they are separated.
The derivative remains the sum of the original two logistic terms.

## Independent reference

For an unswept infinite span, fixed PG Mach zero and symmetric section limits,
the wind-aligned vortex/control-point construction gives the scalar equation

\[
a_0\sin\alpha-c_l\cos\alpha-K_s f(c_l)=0,
\qquad a_0=6.2832.
\]

The reference evaluates the logarithmic leakage using an independent stable
softplus implementation and a bracketed scalar root. For the sampled angles,
the positive cosine and nonnegative leakage derivative make the root unique.
The pressure-drag contribution is `4 (sin(alpha)-cl cos(alpha)/a0)^2`, added
to the specified friction and pressure profile coefficients. This reference
does not call the production vortex, circulation or force implementation.

Six factor/width combinations are checked at −25°, zero and +25° on three
aspect ratios, 5,900, 59,000 and 590,000. Each uses 16 lifting intervals.
The last aspect-ratio extension was necessary because zero leakage retained
a finite-span error above the original `1e-4` threshold at 59,000. The
threshold is unchanged; all nonzero-angle errors decrease by more than five
times at each tenfold span increase. The final 54 limiting calculations pass;
the maximum final lift/drag coefficient difference is 2.12819e-5.

Six ordinary finite-wing cases demonstrate parameter sensitivity. Two alternate
consistent unit systems preserve the dimensionless parameters and scaled
physical results. A disabled-stall calculation agrees with zero leakage.
These account for 63 native cases. Twelve further calculations check widths
`1e-310` and `1e100` at both signed incidences on the same three aspect ratios.
Their independent scalar reference uses direct logarithms in 450-digit Decimal
arithmetic. All four extreme-width refinement sequences pass the unchanged
coefficient tolerance and reduction checks. The native study totals 75 cases;
consistent-unit changes give maximum scaled difference 2.02061e-14.

A separate grid checks the leakage value and derivative at 270 combinations
of symmetric/asymmetric section limits, transition widths from `1e-310` through
`1e308`, and interior/exterior/boundary-adjacent lift coefficients. The reference
uses the exact input floats in 450-digit arithmetic and the original direct
logarithms, independently of the production rearrangement. Maximum scaled error
is 4.07422e-16. This is a sampled numerical-range verification, not a proof of
relative accuracy for every possible floating-point input.

The extremely sharp transition also exposed a separate continuation cutoff.
The former fixed minimum arclength step of `1e-7` stopped before closely spaced
corners in two independently solvable 16-equation piecewise-linear systems.
The cutoff now follows floating-point resolution in the existing normalized
metric: `64*eps*max(1,norm(y))`. The 600-attempt limit, physical residual
tolerances, correction/branch guards and exact unregularized endpoint solve
remain unchanged. Both independent systems recover their unique algebraic roots
within 2.22045e-16. The narrow-wing and prescribed-circulation-rate cases that
initially failed now converge with residuals below 2e-15. This does not establish
uniqueness of general finite-wing stalled roots.

All 113 targeted native tests pass: 62 stall-parameter checks, 12 aerodynamic
checks, 18 circulation-basis checks and 21 continuation checks. These include
pointwise/Fourier tangents with nonzero circulation rate at extreme widths,
known folds and competing roots, and the existing high-angle branch refinement.
The initial expanded batch retained one continuation failure among 111 tests;
the initial expanded reference study also stopped at the old cutoff. Both
failures and their original sources remain preserved.

Nineteen packaged-WASM cases compare 570 physical values with maximum scaled
native difference 5.55112e-16. Ten also check the independent limiting reference
inside WASM; thirty invalid-input cases reproduce the strict parameter guards.
The 270 high-precision leakage/derivative comparisons and both independent
corner systems also pass inside WASM.

## Browser verification history

The first browser workflow timed out after four numerical comparisons. The
remaining browser attempt was explicitly stopped; its terminal child exit is
−15. An unchanged-code retry used `LP_NUM_THREADS=1`, Mesa's
[documented rendering-thread control](https://docs.mesa3d.org/envvars.html#envvar-LP_NUM_THREADS).
It reached all six numerical comparisons and archive restoration, then timed out
before the stall-off solve. The old-case/default and invalid-input workflow
passed. The saved-equilibrium workflow exceeded its 60-second startup wait while
the page reported loading numerical libraries. That run exited with status 1.
The first run on the stable kernel completed its main workflow with all six
comparisons, archives, the stall-off equivalence and rendered captures, but its
supervisor later disappeared without a terminal record. Its overall result is
retained as incomplete. All tested source and asset hashes still matched.

After confirming the processes were absent, each unchanged workflow was rerun
as a separate job with longer startup and workflow time limits. All three passed
with recorded zero child exits, as did their supervisor: legacy defaults/invalid
inputs, saved-equilibrium time launch, and the six-setting/archive/stall-off
workflow. All numerical, archive, offline and WebGL assertions were retained.
The saved-equilibrium launch uses its saved factor 10 and width 0.15 despite
current controls of 80 and 0.01, and preserves the equilibrium loads through
the time snapshots. Final desktop/mobile control captures were inspected.
All 50 standalone JavaScript tests also pass on source-matched files.

The first study/test batch incorrectly expected the low-level rigid solver to
return browser-enriched condition metadata. The study now records its explicit
input condition, while browser tests check exported settings. Original failed
jobs remain retained. The physical comparisons and tolerances were not weakened.

## Reproduction and limits

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-stall-parameters.py
.venv/bin/python scripts/plot-stall-parameters.py
.venv/bin/python -m pytest -q tests/test_stall_parameters.py tests/test_aero.py tests/test_circulation.py tests/test_circulation_solve.py
npm run build
node scripts/test-stall-parameters-wasm.mjs
OPENSWING_WEBGL_DRIVER=mesa npm run test:browser -- tests/browser/stall-parameters.spec.js
```

The native data and figures are `stall-parameters.json`, `.svg`, `.pdf` and
`.png`. Packaged-WASM and offline browser verification are separate gates;
their final outcomes must be read from the checks record when available.
This increment was developed and tested in an isolated copy. The preceding
complete native baseline passed all 1,118 tests in 69 file subprocesses; its
source-matched terminal records and interrupted attempts are retained in
`native-regression-20261008.json`. That baseline predates the two numerical
changes here. The 113 targeted checks and native/WASM/browser evidence above
apply to this increment. Full regression of the changed kernel and the final
bundle audit have separate records; the baseline must not be relabeled as
coverage of the new kernel.

The finite-wing 90-degree case, general stalled-root selection, swept-line
refinement, measured post-stall accuracy, exact ASWING executable parity and
broader aircraft/flutter validation remain unresolved. All 40 broad
requirements remain Partial; the full project goal remains incomplete.
