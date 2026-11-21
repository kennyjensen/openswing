# SA-7 force consistency and fore-wing mesh refinement

2026-11-07. Under the documented isolated fore-wing setup, **22/29 archived
rows conflict with a drag-only lower bound; 23/29 conflict with the combined
CD/CDi bound**, even allowing 5% error. This identifies an incompatibility
with the stated setup and output definitions, not its native cause. Every
original signed target remains in the comparison. SA-7 stays **682/812**.

Twenty-four fresh cold solves also rule out the tested mesh resolutions as
the explanation for the remaining lift and induced-drag errors. No production
aerodynamic equation, default or acceptance tolerance changed.

## Bound from the published equations

The original input describes one straight unswept wing: span 1.29 m, chord
0.22 m, section friction coefficient 0.006, pressure coefficient 0.002, and
reference area 0.55815 m². An independent text reader checks these values,
constant 2° twist, zero moment references, and absence of other wings,
bodies or engines without importing the OpenSwing parser.

For steady uniform flow at zero sideslip, the induced velocity at the straight
bound vortex is perpendicular to the freestream. The wind component of local
velocity remains U and its magnitude is at least U. Projecting the surface
profile force in equation 70 of the
[Technical Description](../../.reference/asw_theory.txt) onto the wind gives:

`CDp >= (span × chord / Sref) × (cdf + cdp) = 0.00406772373018`.

Separation drag contains a squared tangency velocity and is nonnegative.
Changing circulation or stall strength cannot remove this floor. Nonnegative
induced drag gives `CD >= 0.00406772373018`. For this single straight lifting
line, consistent near-field and Trefftz integration additionally gives:

`CD − CDi >= 0.00406772373018`.

These statements assume the published bound-vortex surface-velocity convention,
stationary uniform flow, declared section coefficients and reference dimensions,
and no additional gust, body, engine, image, or acceleration loads. The joint
bound also assumes consistent force/wake quadrature. It is not a general
constraint on an individual wing in a multi-wing aircraft, where another wing
can supply upwash.

Both bounds use exact rational arithmetic and original native decimal tokens.
Every value receives its full 5% allowance, or the original absolute interval
when larger; near-zero handling is unchanged. The largest allowed CD is
compared with the smallest allowed CDi, rather than just their printed centers.

At **0°**, where archived drag is still positive:

| Quantity | Value |
|---|---:|
| Archived CD | 0.00751575 |
| Largest CD allowed by 5% | 0.00789154 |
| Archived CDi | 0.00584995 |
| Smallest allowed CDi plus profile floor | 0.00962518 |
| Gap after both favorable allowances | 0.00173364 |

The joint failure starts at 0° and includes all 23 subsequent sampled rows.
The drag-only failure starts at 2° and includes 22 rows; 21 already have
negative archived CD. A standalone circulation or stall adjustment cannot
resolve these under the stated assumptions. Unretained native inputs, different
output conventions, or a producer/exporter issue remain possible explanations.
The affected reference values are not corrected or removed.

## Remaining non-drag errors

Angles −6°, 19°, 20°, 21°, 23° and 24° cover every remaining non-drag fore-wing
failure. The report's 40-node statement motivates nominal 39/40-interval
interpretations; 80 and 160 intervals test refinement. Required center-node
placement is retained. Both 39 and 40 requests yield 40 actual strips, with
different node positions. All section data, strength 40, width 0.05, evolving
influences, and native outputs stay fixed.

| Requested intervals | Non-drag checks | All seven outputs |
|---|---:|---:|
| 39 | 23/30 | 23/42 |
| 40 | 23/30 | 23/42 |
| 80 | 23/30 | 23/42 |
| 160 | 23/30 | 23/42 |

The low-lift CL error stays **9.47–9.49%**. At 160 intervals the five failed
CDi values remain **5.19–6.10% low**. From 80 to 160 intervals, maximum relative
changes are **0.00225% in CL**, **0.00289% in CDi**, and **0.00394% across all
five coefficients**. No candidate meets the predeclared extension condition;
no additional full-polar mesh sweep follows. These alternative comparisons add
no targets or passes to the main total.

## Independent verification

A reader with no production imports reconstructs equation-67 lift,
equation-70 profile force, and equation-72 moment from all 24 saved fields.
It checks the wind and spanwise velocity components, profile-drag floor,
near-field/Trefftz induced-drag equality, and moment/circulation and
efficiency/circulation identities. Maximum normalized equation discrepancy is
**2.66e−15**. All 168 diagnostic acceptance decisions are independently checked
using rational arithmetic. Maximum nonlinear residual is **1.83e−13**.

The 24 solves finish in two serial batches with one BLAS thread, in about
16.02 seconds after imports. Both processes exit successfully. This supports
the current implementation for this case; native producing settings remain
unverified.

Evidence: [plan](../../artifacts/isae/sa7-force-consistency-20261107/plan.json),
[audit and individual bounds](../../artifacts/isae/sa7-force-consistency-20261107/analysis.json),
[solver driver](../../artifacts/isae/sa7-force-consistency-20261107/run.py),
[independent reader](../../artifacts/isae/sa7-force-consistency-20261107/audit.py).

## Reproduce the selected comparison

The suite now accepts **`--comparison-scope sa7-documented`** with `polars`
and `extra_polars`. It substitutes the authenticated original fore input for
the later mismatched file, retaining all 812 target slots exactly once. The
existing source execution contract, signs, settings, tolerances and native
provenance qualifications remain. Other cases are unchanged.

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py \
  --adapters polars extra_polars --comparison-scope sa7-documented \
  --cases SA-7 --timeout-seconds 60 --plan-only \
  --output-dir artifacts/isae/my-sa7-run
```

To execute in small serial batches, repeat with `--resume --max-new-jobs 4`
in place of `--plan-only`. Keep the code, directory, selectors and timeout
unchanged between batches. No background solver is required.

Nine new selector tests and seven existing source-pairing checks pass. The
actual CLI plans **116 jobs / 812 slots**, with 58 authenticated fore-wing
jobs. A separate one-job CLI smoke run computes the original fore wing at 0°
with a successful worker exit and unchanged seven predictions. It correctly
reports **5/7** matches: Drag/CD still fail. The runner returns exit code 1
for these open comparisons, not for a solver execution failure. The full plan
is [retained](../../artifacts/isae/sa7-force-consistency-20261107/suite-plan/plan.json),
as is the [smoke report](../../artifacts/isae/sa7-force-consistency-20261107/suite-smoke/report.json).
