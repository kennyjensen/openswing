# SA-11 winglets: explicit current-wind Fourier checks

2026-11-07. Eight small serial calls test 5 and 19 sine modes per logical beam
on N48/N96, for both bundled winglet models. Conditions are explicitly 30 m/s,
5 degrees incidence, zero sideslip, current-wind influences, automatic PG Mach,
and the existing stall and core settings. Geometry and production modules are
unchanged. Four saved pointwise states are reused only after verifying their
complete conditions, input hashes and production-module hashes.

| Model | Intervals/beam | Pointwise maximum local Mach | 5 modes | 19 modes |
|---|---:|---:|---:|---:|
| Upper winglets | 48 | 0.181903 | 0.263231 | 0.181593 |
| Upper winglets | 96 | 0.353519 | 0.458430 | 0.353804 |
| Upper and lower winglets | 48 | 3.048750, rejected | 0.392853 | 2.038005, rejected |
| Upper and lower winglets | 96 | 3.469369, rejected | 0.658265 | 2.603952, rejected |

Six Fourier states compute and two reject. The largest projected residual is
1.892e-15, but this does not establish local satisfaction of the flow equations.
The maximum local residual, normalized by the 30 m/s flight speed, is:

| Model | Intervals/beam | 5 modes | 19 modes |
|---|---:|---:|---:|
| Upper winglets | 48 | 0.614659 | 0.298729 |
| Upper winglets | 96 | 0.600699 | 0.425918 |
| Upper and lower winglets | 48 | 7.674009 | 9.208852 |
| Upper and lower winglets | 96 | 4.499024 | 6.489449 |

These residuals include the existing stall leakage; they are the unprojected
equations, not a newly imposed acceptance criterion. The documented Fourier
method allows nonzero local residuals while enforcing their weighted projections
([steady theory, equation 201](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=40)).
Their size and sensitivity still require resolution studies before trusting
the local field. Five modes make the upper/lower model executable, but raising
the mode count restores the Mach rejection, and its N48-to-N96 total drag
changes by -12.69%. Successful execution is not a demonstrated fix.

For the upper model, 19-mode CL, CD, CDi and Cm change by +0.1525%, -0.3342%,
+0.0708% and +0.1450% with mesh refinement, respectively. Its maximum local
Mach still nearly doubles. Stable integrated coefficients alone do not
establish local-flow convergence.

The guide and theory do not establish an original SA-11 mode count or a
connected-surface Glauert mapping. These checks retain OpenSwing's existing
per-logical-beam representation. They do not establish native ASWING parity,
justify selecting five modes, or resolve the transonic archived comparisons.
No defaults, comparison scopes or ISAE completion fractions change.

The calls total 2.014 seconds; the longest takes 0.619 seconds. The process
finished successfully. An independent saved-result audit verifies all eight
requests, applied conditions, source/module pins, mode counts, subsonic gates
and recorded artifacts. No solver runs remain active from this study.

Evidence:

- [Reproducer](../../scripts/verify-isae-sa11-winglet-modes.py)
- [Plan and provenance](../../artifacts/isae/sa11-winglet-modes-20261107/plan.json)
- [Raw results](../../artifacts/isae/sa11-winglet-modes-20261107/results.json)
- [Analysis](../../artifacts/isae/sa11-winglet-modes-20261107/analysis.json)
- [Independent audit](../../artifacts/isae/sa11-winglet-modes-20261107/independent-audit.json)

This is separate from the older 48-request Fourier archive, whose applied
influence settings cannot be established from its recorded requests alone.
That archive is preserved; see the [runner correction](isae-sa11-circulation-settings-20261107.md).
