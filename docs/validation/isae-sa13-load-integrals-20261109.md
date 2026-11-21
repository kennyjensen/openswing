# SA-13: equations, archived load integrals and input history

**Subsequent finding:** the [discrete-load audit](isae-sa13-discrete-loads-20261109.md)
recovers the exact radius/next-station-slope formula and normalization for all
183 finite red-curve loads. A current-kernel replay confirms 180 admissible
station densities. This resolves the discrete-curve leads below while retaining
the continuous-curve, pressure and complete native-setup questions.

Observed 2026-11-09 UTC. **SA-13 remains 0/612**; SA-12 remains open.
Five focused checks of the current body-force and volume-field implementation
pass. A source-only check finds substantial differences between the integrated
continuous and discrete ASWING-labelled curves. Normalization and the relation
between radius and supplied radius derivative need resolving before those
curves can identify an OpenSwing solver error.

## Current equations and checks

Drela's steady description, **printed p.16, Eqs.68–69**, gives

`f_lift = rho V_perp (V · s_hat) d(pi R²)/ds`.

For a straight isolated body in uniform flow, with zero profile and acceleration
loads, its body-transverse component obeys

`f_z/q = sin(2 alpha) dA/ds`, where `A = pi R²`.

Thus an integral between two stations depends only on their cross-sectional
areas. It avoids differentiating a noisy plotted radius distribution.
This is body-transverse force, not wind-axis lift; neither convention is
silently substituted for the other.

`openswing/volume.py::body_loads` implements the printed steady force term.
`VolumeField` and `source_doublet` implement **p.34, Eqs.162–163**: the area
derivative source strength, transverse doublet strength, PG coordinate
transformation and `R/2` core. The printed doublet numerator contains the
unregularized squared distance; the code retains it.

The current five focused checks in `tests/test_volume.py` pass:

- Three angles for a constant-radius body's field against an independent
  closed-form regularized doublet integral.
- A varying-radius source/doublet field against adaptive integration, including
  invariance to a change of beam parameter and exclusion of its own body field.
- Zero net potential force and the volume-dependent Munk moment for a closed
  body in uniform flow.

These checks cover their stated conditions. They do not establish the unknown
SA-13 inputs or validate every body-flow feature. They ran serially with one
BLAS thread and 512 MiB / 15 CPU-second / 25 wall-second limits: **5 passed,
10 deselected in 8.70 s**, exit 0. No solver equation or default changed.

## Integrating the original plotted curves

Each row below compares the integrals of the continuous and discrete archived
ordinates over the same interval. The x intervals use the existing closed
outline's length; values are integrated piecewise linearly between original
samples, with no extrapolation or bridging of missing entries. A ratio of one
would mean equal integrated ordinates over that interval.

| Hull | 5–25% length | 10–40% | 40–80% | 60–90% |
|---|---:|---:|---:|---:|
| R33: continuous / discrete | 1.010 | 1.372 | 0.603 | 0.754 |
| R101: continuous / discrete | 0.515 | 0.570 | 0.445 | 0.364 |
| RS1: continuous / discrete | 0.481 | 0.563 | 0.362 | 0.392 |

For the aft intervals, both integrals are negative and their ratios are
positive. These are not pointwise solver-error percentages or acceptance
decisions. The sparse plotted samples do not supply an integration-error bound
for the unknown underlying curves.

Jan Part I **§6.2, p.40**, says the blue curve uses a modified implementation
with a supplied radius derivative, while the red curve uses backward
differencing. The integrals show that we cannot assume the difference is only
oscillation around the same load distribution. Coarse/digitized curves,
nonconservative differencing, different normalization, or a supplied derivative
that corresponds to a different smooth radius definition remain possible.
The data do not identify which explanation applies.

## R101 normalization lead

NACA-TR-405 **Figure 8, printed p.132 / PDF p.10**, uses `f/q` in feet for a
33.01-inch R101 model. Figures 6–7 instead use `f/(qD)` for RS1 and R33.
The ISAE axes label all three as `cl(s)` without recovering that conversion.
Using the existing outline without fitting its shape gives the following
ratios of archived integral to Eq.68's area-change prediction:

| R101 interpretation | 5–25% | 10–40% | 40–80% | 60–90% |
|---|---:|---:|---:|---:|
| Continuous, primary `f/q` in feet | 0.978 | 1.057 | 0.971 | 0.769 |
| Discrete, primary `f/q` in feet | 1.900 | 1.855 | 2.184 | 2.113 |
| Discrete, alternative `f/(qD)` | 0.937 | 0.915 | 1.077 | 1.042 |

This makes a normalization mismatch a useful hypothesis for R101; it does
**not** prove the original postprocessing or justify changing its acceptance
mapping. The physical diameter inferred from the outline is conditional.
Both interpretations are retained, including the unfavorable intervals.

For RS1, using the primary 9° incidence, the discrete curve's ratios to Eq.68
are 0.906, 0.891, 1.029 and 1.024; the continuous curve's are 0.436, 0.502,
0.372 and 0.401. The report's alternative 10° incidence is also retained in
the analysis. That angle change does not remove the integrated discrepancy.
Recovering the actual radius and supplied derivative remains essential.

## History search

The upstream folder's history leads through the February 2025 rename from
`1_Aerodynamics` to `1 - Aerodynamics`. The initial SA-13 directory at commit
`ec5eb2d8f8789ec537a167c7e0922c109146a741` contains the same four figure blobs
as the pinned current archive, with no model or driver. This search recovered
no missing inputs. It covers this repository path and its renamed predecessor;
it does not establish that no other copy exists.

The raw API responses and checksums are retained in
[`reference/isae-sa13/history-20261109/`](../../reference/isae-sa13/history-20261109/audit.json).
The [initial upstream directory](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/ec5eb2d8f8789ec537a167c7e0922c109146a741/1_Aerodynamics/SA%20-%20Steady%20Aerodynamics%20Cases/SA%20-%2013%20-%20A-D%20-%20Airships%20-%20Fuselages%20-%20Lift%20and%20Dynamic%20Pressure%20Distribution)
provides the public provenance.

## Reproducible evidence and consequence

The standard-library [audit](../../scripts/audit_sa13_load_integrals.py)
records all twelve curve-pair intervals and forty equation/normalization
comparisons. [Saved analysis](../../artifacts/isae/sa13-load-integrals-20261109/analysis.json)
authenticates eleven sources. An
[independent Decimal verifier](../../artifacts/isae/sa13-load-integrals-20261109/verify.py)
integrates original line segments analytically and obtains radii directly from
the original upper/lower outline series; maximum arithmetic disagreement is
`1.08e-15`. Its [receipt](../../artifacts/isae/sa13-load-integrals-20261109/verification.json)
confirms all 476 finite and 136 unavailable native entries remain.

A separate [original-MAT verification](../../artifacts/isae/sa13-load-integrals-20261109/mat-verification.json)
confirms all twenty stored series and 1,530 coordinate pairs, including missing
values, exactly against the four original figures. It took 7.78 s and
50,076 KiB peak RSS under the same resource limits, without production imports
or solver calls. The current
[body-test receipt](../../artifacts/isae/sa13-load-integrals-20261109/body-tests.json)
records the separate five passing implementation checks.

The next useful comparison must reconcile geometry, supplied radius derivative
and force normalization together. Changing the production derivative method
to match one curve now would conflate those unknowns. Keep both ASWING variants
and their original denominators, and retain the separate
[pressure](isae-sa13-pressure-reference-20261109.md) and
[primary-geometry](isae-sa13-primary-geometry-20261109.md) conflicts.
