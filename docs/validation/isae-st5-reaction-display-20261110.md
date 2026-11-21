# ST-5: distributed normal-load output (`f_reac`)

The existing saved gravity forces and geometric midpoint frames reproduce all
**992 physical-interval `f_reac` values** across the sixteen original static
cases, with maximum relative error **0.01966%** and absolute error
**0.00000548 lb/ft**. This identifies a limitation of the earlier scalar-weight
comparison diagnostic; it does not require changing the gravity-force equations.

The full archive contains **1,192 rows**. Its other **172 duplicate-station
rows and 28 terminal dummy rows** remain retained. They have no corresponding
physical interval in the current mesh and are not silently assigned one.
Alternative display reconstructions cover those rows separately.

ST-5's primary mechanics result remains **16,687/16,688**. This investigation
adds no primary passes, changes no source/model/production equation and runs
no new solve. It concerns distributed applied loading in **lb/ft**, not the
remaining internal-force `Fn` mismatch in **lb**.

## Documented quantity

Drela's [user guide](../../reference/aswing_doc.txt), spanwise variable 25,
defines `f_reac` as the normal component of gravity, acceleration and
apparent-mass loading. It is not the ground-support reaction. For these static,
zero-airflow cases, [steady theory](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf)
Eq. 78 gives the gravity part. With the file gravity directed along body −z,

\[
f_{\rm reac}=\hat n\cdot(\mu_{\rm total}\mathbf g)
=-(mg+Dmg)n_z .
\]

`mg` and `Dmg` are weight per unit material length in the input units; their
sum divided by file gravity is mass per unit length. The negative `Dmg` used
for the bench loads follows Jan's [Part III](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf),
§4.5, pp. 40–44. No experiment is used as an acceptance target here.

The earlier diagnostic used the scalar weight evaluated at the arithmetic
parameter midpoint. It omitted the normal projection and did not use the
endpoint-averaged weight of the actual discrete gravity operator. Changing
that diagnostic is separate from changing the already-converged forces.

## Predeclared sampling comparison

Eight expressions were declared before inspecting their errors, each evaluated
with current OpenSwing frames and, separately, the decoded archived angles.
All rows, original printed half-units and final dummy values are retained.
The table shows the current-frame predictions on the same 1,192 rows; these
are overlapping alternatives, not independent validation scopes.

| Weight and normal used | Within original printed half-unit | Within 5% plus printed half-unit | Largest absolute difference, lb/ft |
|---|---:|---:|---:|
| Parameter-midpoint scalar weight, earlier diagnostic | 46 | 1,142 | 0.188175 |
| Endpoint-average scalar weight | 46 | 1,192 | 0.120431 |
| Endpoint-average weight × arithmetic mean normal | 478 | 1,192 | 0.121343 |
| Endpoint-average weight × normalized mean normal | 695 | 1,192 | 0.000005481 |
| Endpoint-average weight × normal from averaged Euler angles | 705 | 1,192 | 0.000005482 |
| Average of the two endpoint normal-load components | 164 | 1,192 | 0.121343 |

The two remaining midpoint-weight alternatives and the archived-angle results
are in the [full summary](../../artifacts/isae/st5-reaction-display-20261110/summary.json).
All rows of both unit-normal reconstructions agree within **0.01966%**.
Using archived rather than OpenSwing angles changes the Euler-midpoint
prediction by at most **0.0000000882 lb/ft**; that reconstruction is a diagnostic,
not an independent solver prediction.

For the current Euler-midpoint diagnostic, the family maxima are:

| Original family | Rows retained | Maximum absolute error, lb/ft | Maximum relative error |
|---|---:|---:|---:|
| Rigid, cosine loading | 320 | 0.000002600 | 0.00330% |
| Literal type-2 roller | 320 | 0.000002420 | 0.00349% |
| Forward-only, cosine/elliptical | 232 | 0.000005483 | 0.00120% |
| Rigid, elliptical loading | 320 | 0.000004750 | 0.01966% |

Several conventions pass at 5%, including the endpoint-average scalar weight.
None reproduces all strict printed intervals. The tables therefore do not
uniquely identify the original export interpolation. Printed node and angle
uncertainty remains; this audit does not claim an exhaustive uncertainty bound
or select coordinates to improve agreement.

## Check against actual saved physical loads

A subsequent [independent review](../../artifacts/isae/st5-reaction-display-20261110/independent-review.json)
checks all **992 actual intervals**, using the saved nodal load arrays and each
interval's material length. Their force per length agrees with
`[0, 0, −(weight_left + weight_right)/2]` to **1.78e-15 lb/ft**.
The arithmetic transform averages agree exactly with the saved source operator.
Recomputing 1,164 nonterminal unit-normal projections directly from frame
columns agrees with the first audit to **1.78e-15 lb/ft**.

That review then uses the existing `physical_midpoint_frame` already exported
by OpenSwing, instead of either newly constructed normal. The resulting
gravity projection matches every physical-interval reference at 5%, with
**595** also within strict printed precision. The maximum error is
**0.000005478 lb/ft**, or **0.01966%**. All **200 nonphysical display rows** remain
unavailable for this particular physical-interval projection, in the full
1,192-row scope. Their reference values have not been removed.

The root duplicate illustrates the distinction. In rigid `30lb_80_20`, rear
beam line 102 has native `f_reac = 3.728783 lb/ft`. Its two traces have opposite
dihedral. Normalizing their mean normal gives the vertical direction;
averaging the transformation matrices retains a z component of about 0.96746.
That difference produces the roughly **0.12134 lb/ft** discrepancy in the
arithmetic-mean-normal diagnostic. There is no finite physical interval
between those duplicate rows.

Steady Eqs. 48–50 explicitly use the arithmetic transformation average in the
structural equations. The display evidence does **not** authorize replacing
that matrix with a normalized frame or averaged Euler angles. The existing
code already keeps its constitutive transform and geometric display frame
separate; both are preserved.

## Consequence and remaining work

The static meaning of `f_reac` and the existing physical interval loads are
now checked against the full paired archive. Exact duplicate-row/terminal
display behavior and historical interpolation remain open. The prior strict
ledgers, unavailable modal evidence and remaining `Fn` failure are unchanged.
No unsteady or acceleration-dependent `f_reac` validation follows from this
static check.

The next implementation step is to expose the documented static normal load
from the existing gravity forces, material lengths and physical section frames,
with its sampling location explicit. Native export placeholders should remain
separate from physical intervals. This does not call for another structural
solve tolerance change or a modification of the conservative load equations.

## Evidence and reproduction

- [Predeclared expressions and source pins](../../artifacts/isae/st5-reaction-display-20261110/plan.json)
- [Saved-load review plan](../../artifacts/isae/st5-reaction-display-20261110/review-plan.json)
- [Final verification](../../artifacts/isae/st5-reaction-display-20261110/verification.json)
- [Audit driver](../../scripts/audit_st5_reaction_display.py) and [independent checker](../../scripts/verify_st5_reaction_display.py)

Prepare a new directory with the audit driver's `prepare` action, then run
`run --family rigid`, `roller`, `forward` and `elliptical` in separate serial
invocations, followed by `summarize`. The checker has separate `prepare` and
`run` actions. Use `--output DIRECTORY` throughout and set
`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and
`NUMEXPR_NUM_THREADS` to 1. Each numerical-data read has 512 MiB address-space,
15 CPU-second and 25 wall-second caps. All invocations completed normally;
no solver, Node, browser or build was launched. Production modules and primary
scope hashes remain unchanged.
