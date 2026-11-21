# Smooth saved-state velocity histories

Saved-equilibrium launches now accept one smooth cubic Earth-velocity target
table with two or more distinct, increasing times. Interior spline knots no
longer cause an unsupported-scope error. The saved deformation, pose, velocity,
angular velocity and circulation are held at launch while the existing
right-side consistency solve completes algebraic settings and accelerations.
The original before-input state remains separately owned. The numerical
residual, interpolation, integration methods and tolerances are unchanged.

The [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
specifies splined time inputs and doubled-time discontinuities. OpenSwing uses
natural cubic segments; the exact ASWING endpoint convention remains unverified.
This extension permits smooth segments only. It retains the existing restrictions:
one Earth-velocity actuator target, a nonrotating force-only mixed frame,
unchanged loads, no controller/gust/disturbance, compatible initial target value,
and a table ending strictly beyond the requested interval. Multiple targets,
rotating saved launches, doubled knots, cutoff transitions, forcing replacement
and broader saved input changes remain unfinished.

New launch checkpoints carry `saved_history_scope` version 2. Actual version-1
checkpoints remain restorable and resumable under their original two-knot
contract. They are not reinterpreted as new spline records. The original/candidate
continuations of a retained version-1 checkpoint have byte-identical complete
JSON output, without exclusions. Recorded-step replay and original forcing
ownership remain binding.

## Independent mechanics

The original fixture has a 2 kg tip mass, a massless axial spring with
`EA/L = 500 N/m`, and a root actuator. Its saved state has tip displacement
`q = -0.0016 m`, zero relative velocity, frame acceleration `0.4 m/s²`, and
root thrust `0.8 N`. The three-point velocity table is `(0,0)`, `(0.04,0.024)`,
`(1,0.792)`. Independent natural-spline algebra gives

```
g(t) = 0.596 t + 2.5 t³                         (t ≤ 0.04)
g(t) = 0.024 + 0.608 u + 0.3 u² - (5/48) u³    (u = t - 0.04)
q'' + 250 q = -g'(t)
root thrust = -500 q
```

At launch, frame acceleration changes to `0.596 m/s²`, relative tip acceleration
to `-0.196 m/s²`, and the saved shape, velocity and `0.8 N` thrust remain fixed.
The reference integrates the piecewise quadratic acceleration analytically.
For discrete comparisons, it independently integrates Lagrange polynomials to
construct the Radau stages and solves a six-variable linear oscillator system.
BDF references derive coefficients from actual time intervals and differentiate
the prescribed velocity with that same stencil. No kernel matrices, residuals
or interpolation routines are imported by the result checker.

The actual public launch takes three Radau steps through the interior knot.
Seven additional public continuations cover a split at 0.02 s, BDF1, BDF2,
and 0.01/0.005 s refinement for Radau and BDF2. All cases pass the original
pointwise gates: position `1e-9 m`, relative velocity `1e-8 m/s`, actuator force
`1e-7 N`, frame velocity `1e-9 m/s`, and frame/relative acceleration `1e-7 m/s²`.
All stored checkpoints restore, inputs remain unchanged, and no step is rejected.
BDF2 retains order 2 across the smooth knot; it does not restart with BDF1 there.

Actual endpoint errors against the continuous oscillator at 0.06 s are:

| Method | Maximum step (s) | Position error (m) | Relative velocity error (m/s) |
| --- | ---: | ---: | ---: |
| BDF2 | 0.02 | 2.1111e-5 | 8.2727e-4 |
| BDF2 | 0.01 | 5.3664e-6 | 2.3547e-4 |
| BDF2 | 0.005 | 1.2173e-6 | 6.1790e-5 |
| Radau | 0.02 | 1.4871e-10 | 3.8903e-9 |
| Radau | 0.01 | 3.7555e-12 | 2.8419e-10 |
| Radau | 0.005 | 1.4249e-13 | 5.0281e-11 |

These are fixture errors, not global accuracy guarantees. Refinement reduces
the observed continuous error. The fine Radau velocity comparison is affected
by nonlinear/finite-difference error; this table does not establish fifth-order
convergence at those magnitudes. A small nonlinear residual alone does not
remove temporal truncation error.

## Integration record

The frozen one-file candidate passes 90 focused tests. The main selection first
passed 147 tests and failed one older clock-shift fixture. The same fixture also
fails on the unchanged baseline: it shifts only outer checkpoint times while
leaving the accepted-step record at its original time. The corrected test checks
the frame-consistency layer directly at a large clock value, and an additional
test explicitly requires the complete inconsistent checkpoint to be rejected.
All 22 frame tests then pass. This yields 149 distinct passing current selected
tests; the original failed attempts remain retained. Ten relevant JavaScript
unit tests pass. Collection is 1,663 tests, not a full-suite pass.

The integrated kernel differs from the numerical candidate only in two corrected
docstrings and the forcing report's obsolete initialization limitation text.
The saved-spline implementation itself is byte-identical to the tested candidate.
The mobile workspaces, editor palette and mounted performance changes remain in
place.

The first production-browser attempt completed and exported the actual three-step
Radau launch. Its independent mechanics check passed, with maximum force error
`2.4320e-9 N` and frame-acceleration error `6.1140e-8 m/s²`. The workflow then
failed because the test expected the literal phrase “right-limit” while the
interface correctly said “completed right state.” That attempt remains FAIL.
The corrected follow-up reopens the exact exported result through the public
solution-archive UI and checks mobile display, export and actual checkpoint
continuation. It does not repeat or claim a new initialization solve. Its
follow-up passes in 120.929 seconds (141.625-second process wrapper), with no page
errors or external requests. The 390-pixel plot was visually inspected, CSV
exports work, and two resumed Radau steps pass independent mechanics with
maximum force error `1.3127e-9 N`. These records jointly establish the tested
launch/display/continuation behavior; they do not relabel the first workflow PASS.

Reproduce a public launch and checkpoint continuation with
`.venv/bin/python scripts/verify-saved-spline.py --run --report output.json`.
Check an exported complete trajectory without importing the solver with
`--result exported.json --report mechanics.json`. The browser workflow is
`tests/browser/saved-spline.spec.js`. The complete ASWING goal remains active;
all 40 broad requirements remain Partial.

The [machine-readable record](saved-spline-histories.json) gives exact source
hashes and results. The [portable evidence archive](saved-spline-histories-evidence.zip)
contains 376 members and has SHA256
`60fe67f66f701f31a3203af9b4a403d5ff6cc1e9b6d0055e56ca6fc177365d5a`. Its CRC, member hashes and
fresh-extraction verifier pass. Extract it and run `python verify.py` with NumPy
installed to recompute the independent mechanics without importing OpenSwing.
Source/offline distribution auditing is separate from this numerical evidence.
