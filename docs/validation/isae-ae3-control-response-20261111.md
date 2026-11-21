# AE-3: coupled control response and operating constraints

Observed 2026-11-11 UTC. The full coupled control derivative agrees with
independently reconverged nonlinear solutions at the two endpoint speeds.
A separate interpretation of the original script's roll constraint, combined
with a lift-control coefficient supplied by sibling files, reduces the rolling
moment errors to **0.252% and 28.502%**. This is useful setup evidence, but it
does not recover the exact archived input or validate AE-3.

The [primary comparison](isae-ae3-current-20261111.md) remains **50/725 at 5%**:
72 computed values, 22 mismatches and 653 uncomputed targets. These diagnostics
add no native-reference votes and change no production equations or defaults.
Original ASWING, modified ASWING-m and experiment remain separate.

![AE-3 control and constraint comparison](../../artifacts/isae/ae3-control-response-20261111/control-response.png)

## Coupled derivative verification

The diagnostic restores the original flexible, nominal-80 states (82 intervals)
at F1 = 1 file unit. All accelerations and angular rates remain fixed at zero.
It solves the complete implicit system `J dx/dF1 = -R_F1`, including moving
source and receiver geometry in the induced field. Exact mechanical blocks,
analytic circulation/control blocks and fourth-order local geometry stencils
use existing source-equation implementations. The full sparse matrix has
1,078 unknowns and 342,918 nonzeros. Exact beam elimination reduces the factored
system to 580 unknowns without dropping matrix entries.

This is a bounded diagnostic implementation, not adoption of a general or fully
analytic derivative backend. The existing production derivative route retains
its centered full-state Jacobian. The lagged geometry matrix used to accelerate
some Newton solves is not substituted for the physical derivative.

Eight independent production solves reconverge F1 at ±0.001 and ±0.0005 about
the original setting. All six coefficient derivatives pass the predeclared
gate `max(1e-8, 0.0005 × |nonlinear derivative|)` at both step sizes. Refinement
also passes that gate. The rolling derivatives at the finer step are:

| Speed (m/s) | Implicit dCl/dF1 | Reconverged dCl/dF1 | Absolute difference |
|---:|---:|---:|---:|
| 27.0934 | −0.00156300485909 | −0.00156300485852 | 5.660e−13 |
| 59.4556 | +0.00127283067056 | +0.00127283008605 | 5.845e−10 |

The accepted derivative assessment has **132 checks**: 24 tangent checks,
72 physical checks on reconverged states, 24 coefficient comparisons and
12 nonlinear step-refinement comparisons. Zero-rate source-airflow and steady
source residuals agree both at equilibrium and at two off-equilibrium probes.
That parity check applies to this case and does not establish general operator
equivalence under motion.

The successful tangent workers took 3.89–4.07 CPU seconds and 6.81–7.53 wall
seconds. This is a local measurement, not a browser or general speedup claim.

## What the original script may be selecting

The authoritative [reference index](aswing-authoritative-references.md) and
its [checksummed catalog](aswing-authoritative-sources.json) were checked.
The original `Roll_rate.sh` commands six speeds and F1 = 1, then selects
`%`, `4 23`, `P`, `d` before convergence and `MM` output.

The [original manual](../../reference/aswing_doc.txt), sections describing
constraint selection and modification, identifies coordinates as **column,
row** and `P` as applying the selection to all operating points. The
[extended manual](../../reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf),
Fig. 1.5, p. 12 and the explanation on p. 13, places roll acceleration in
column 4; active flap/engine rows precede net force/moment rows. With the
literal model's one flap and no engine, this layout implies row 23 is net
rolling moment. The [inspected figure](../../artifacts/isae/ae3-control-derivative-r3-20261111/reference-review/extended-manual-p12.png)
is retained.

**This row mapping is conditional on the archived build using that layout.**
Its actual mask, defaults and toggle result have not been recovered. Printed
zero angular rate alone does not prove zero angular acceleration. The tested
alternative frees `angular_acceleration.x` and constrains net `moment.x` to zero,
with all angular rates still zero. It retains the original root attachment in
body coordinates and uses the production moving-airflow source operator.

Drela's [steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
§8.3, Eqs. 212–213, pp. 50–51, includes acceleration responses and net-wrench
constraints in the coupled derivative system. Its matrix reuse discussion
supports exact factor reuse; it does not establish the particular `MM`
constraint convention used in these archived exports. That distinction remains
to be audited.

Jan's [Part IV](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf),
p. 13, distinguishes a mounted rolling-moment experiment from a freely rolling
rate experiment. Neither description alone authenticates this zero-rate,
nonzero-acceleration interpretation. The report also says the original
experimental mass/inertia distributions were unavailable. Keep the native-file
comparison distinct from reproducing those experiments.

## Endpoint results and the independent control input

The literal `Straight_20O.asw` lift-control slope is 0.0581 and its moment-control
slope is −0.0102. Original sibling `Straight_60O.asw`, `Straight_80O.asw` and
`Straight_95O.asw` files supply 0.0686 for the lift-control slope. Jan's p. 13
prose lists 0.0581/−0.0107, while separately stating that original ASWING uses
constant highest-Reynolds-number coefficients. These conflicting inputs are
retained, not silently reconciled by fitting a value.

The final alternative changes **only** the lift-control distribution scale in
a copied model from 0.0581 to 0.0686. Its stations, other distributions, records,
constants and references are checked against the original. No original model
is edited. Both combined-setting cases are actual nonlinear solves.

| Setup | Cl at 27.0934 m/s | Error vs native | Cl at 59.4556 m/s | Error vs native |
|---|---:|---:|---:|---:|
| Archived original ASWING | −0.002056 | — | +0.000450 | — |
| Literal input, fixed acceleration | −0.001562894 | 23.98% | +0.001272751 | 182.83% |
| Literal input, free roll acceleration | −0.001648125 | 19.84% | +0.003971412 | 782.54% |
| Sibling lift slope, free roll acceleration | −0.002050818 | **0.252%** | +0.000578259 | **28.502%** |

The combined alternative's CX errors are 2.094% and 2.230%. Four constraint
states pass **44 checks**, covering fresh residuals, support balances, full
fluid and distributed aerodynamic wrench reconstruction, root position/frame,
zero rates and net rolling-moment balance. The independently exported apparent
fluid force/couple is subtracted when checking distributed aerodynamic
coefficients; the full fluid wrench is checked separately.

There is also a specific clue in the archived finite-versus-derivative gap:

| Speed (m/s) | Native finite Cl / native CldF1 | Literal free-roll Cl / fixed-acceleration CldF1 |
|---:|---:|---:|
| 27.0934 | 1.054900 | 1.054460 |
| 59.4556 | 3.082192 | 3.120141 |

Similar ratios support investigating acceleration constraints. They do not
prove that these two quantities share the archived derivative convention.
The literal model's absolute discrepancy persists, and changing the constraint
alone makes the high-speed discrepancy worse. The remaining 28.5% combined
error is still a failure even though Cl is small near reversal.

## Retained attempts and reproducibility

All **17 launched children** are terminal and reaped: 15 zero exits and two
retained harness failures. Successful accepted diagnostics total **176 checks**.
Numerical jobs ran serially with one BLAS thread and unchanged 512 MiB address
space, 15 CPU-second and 25 wall-second limits. Browser/build checks remain held.

- The first tangent worker omitted the required empty `loads` argument and
  exited before producing a response; its receipt and traceback are retained.
- The first-order geometry diagnostic passed its internal checks but produced
  a spurious near-zero CL derivative of −5.1524e−8. The independent nonlinear
  check rejects it at the original 1e−8 gate. Fourth-order geometry removes this
  error; no gate was loosened. The planned first-order high-speed tangent was
  superseded without execution.
- The first roll solve converged, but its static coefficient oracle included
  apparent-fluid terms. That failed report is retained. The same saved state
  was re-audited with the corrected independent decomposition; it was not solved
  again or counted twice among accepted states.

The saved-data [assessment](../../artifacts/isae/ae3-control-response-20261111/assessment.json)
checks source hashes, all terminal receipts, physical gates and derivative
refinement. It includes the earlier failures and adds no native votes.
[Derivative CSV](../../artifacts/isae/ae3-control-response-20261111/derivative-comparison.csv),
[constraint CSV](../../artifacts/isae/ae3-control-response-20261111/constraint-comparison.csv)
and [native finite/derivative CSV](../../artifacts/isae/ae3-control-response-20261111/native-finite-derivative.csv)
retain the values behind the plot. The
[assessment/plot script](../../scripts/summarize_isae_ae3_control_response.py)
uses saved results and performs no additional solves.

Next, audit the constraint-mask and `MM` derivative convention, then check the
independently sourced alternative across the remaining speeds and a second
mesh before adopting a benchmark setup. Preserve all 725 targets and the
original failures. The high-speed error, full derivative/inertia coverage,
ASWING-m comparisons and exact historical inputs remain open.
