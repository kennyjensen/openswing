# SA-7 lift-force receiver audit

2026-10-31. Evaluating the lift force at a control point or beam-axis point
does not explain the negative drag in the archived historical fore-wing
table. Every tested alternative loses existing matches and gains none. The
published bound-vortex evaluation remains in production; registered counts,
sources and tolerances are unchanged.

The Technical Description explicitly places the velocity in the
Kutta–Joukowski force, equation 67, at the bound vortex. Equations 155–159
distinguish that point from the control point and define the section-normal
rotation. Inspection of the current section-angle and flap formulas found
no disagreement with those rotation equations. The separate native fore-wing
drag anomaly motivates this output-convention check; a closer archive match
would not alone justify replacing the published force law.

## Predeclared scope

Eight cold cases cover alpha −6°, 3°, 10° and 24° for both the full SA-7
aircraft and the previously recovered historical fore-wing model. Each uses
the existing 128-interval request, literal geometry and section data, current
influence geometry, zero PG Mach, stall strength 40 and width 0.05. The
historical fore-wing source pairing remains qualified; the native executable,
startup and mesh have not been recovered.

After each unmodified base solve, the diagnostic substitutes one velocity
in the lift output and its equation-72 quarter-chord couple:

- Bound-vortex velocity: the documented production calculation.
- Control-point velocity.
- Beam-axis velocity with the panel's own bound segment excluded.
- Beam-axis velocity including that bound segment.

Circulation, leakage, ordinary profile drag, separation drag and other loads
stay fixed. These are **output-only recomputations**, not equilibria with new
force laws. The comparison includes all five affected native outputs: Lift,
Drag, CL, CD and CM. Unchanged CDi and efficiency are excluded from these
diagnostic denominators. Original references, including negative drag, and
the provisional 3% gates are retained.

## Results

| Lift velocity | Full aircraft, four states | Historical fore wing, four states |
|---|---:|---:|
| Bound vortex, production | 20/20 | 9/20 |
| Control point | 12/20 | 8/20 |
| Beam axis, own bound excluded | 11/20 | 8/20 |
| Beam axis, all bound segments | 11/20 | 7/20 |

There are **zero gains** from any alternative in either model. None recovers
any of the four sampled fore-wing Drag/CD pairs. Moving the force velocity
upstream can produce negative drag, but neither its magnitude nor its
variation with incidence matches the archive:

| Fore-wing alpha | Native CD | Bound vortex | Control point | Beam axis, own bound excluded | Beam axis, all bound |
|---|---:|---:|---:|---:|---:|
| 3° | −0.005239 | +0.017178 | +0.059995 | −0.055987 | −0.065909 |
| 10° | −0.071742 | +0.046287 | +0.184046 | −0.189094 | −0.220991 |
| 24° | −0.276855 | +0.149057 | +0.384603 | −0.248226 | −0.298766 |

Across all four sampled fore-wing conditions, failed CD errors have median /
maximum magnitudes of **159.18% / 427.91%** for the documented calculation,
**297.73% / 1,245.25%** at the control point, **93.31% / 968.75%** at the
beam axis excluding its own bound, and **115.55% / 1,158.15%** with all bound
segments. These percentages describe this diagnostic sample, not the full
registered family. Near-zero reference drag amplifies relative errors.

The predeclared extension criterion requires all eight sampled historical
Lift/Drag scalars to match, with no full-aircraft loss. No alternative meets
it, so no full-polar receiver sweep follows. This rules out the three tested
receiver substitutions as standalone explanations; it does not identify the
native exporter or establish that every possible output discrepancy is known.

## Verification and execution

All eight retained bases converge and reproduce their saved default outputs
within the 2e-10 parity gate. An independent scalar implementation reconstructs
the complete documented lifting-surface force and moment, the receiver
substitutions, and the own-bound finite-filament velocity. It checks all 1,536
strips and re-scores all 160 diagnostic decisions against original native
tokens using exact rational arithmetic.

Maximum normalized nonlinear residual is **1.52e-13**. Maximum normalized
force error is **6.96e-17**, moment error **4.45e-16**, and output-replay error
**4.45e-16**. The own-bound velocity reconstruction agrees within **1.10e-16**
of flight speed. No production kernel was changed.

The corrected serial run takes about 3.39 seconds after imports. One preceding
solve returned successfully but its diagnostic result was lost to a `lift`
reporting-key error. That attempt and traceback are retained; total nonlinear
call accounting is **nine returned calls, eight retained and verified bases**.
The reporting lookup was corrected without changing the selected cases or
hypotheses. Both processes are terminal; the corrected run exits 0. No browser
or parallel worker was launched.

The registered SA-7 scope remains **395/812**, with historical fore-wing
**246/406** reported separately. The previously qualified full-aircraft
strength-20 result remains **404/406**. This audit neither promotes the
historical pairing to authenticated reproduction nor adds registered passes.

Evidence:

- [Plan and source pins](../../artifacts/isae/sa7-force-receivers-20261031/plan.json)
- [Completed serial run](../../artifacts/isae/sa7-force-receivers-20261031/terminal.json)
- [Independent verification and scalar comparisons](../../artifacts/isae/sa7-force-receivers-20261031/analysis.json)
- [Producer](../../artifacts/isae/sa7-force-receivers-20261031/run.py) and
  [scalar verifier](../../artifacts/isae/sa7-force-receivers-20261031/verify.py)
- [Initial diagnostic error and accounting](../../artifacts/isae/sa7-force-receivers-20261031/attempt1/failure.json)
