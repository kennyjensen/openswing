# AE-3: rigid response, influence settings and control-input differences

Observed 2026-11-11T04:55:34.065556+00:00. Ten small serial diagnostic solves complete and
all **94 numerical/physical checks pass**. No production equation or original
input was changed. These are sensitivity studies, adding **zero** native
comparison votes; the [current primary tally](isae-ae3-current-20261111.md)
remains **50/725 at 5%**. The full ASWING goal and AE-3 remain open.

The two tested speeds are the first and last native exports. Flexible variants
use the same nominal-80 mesh (82 actual intervals) as the current baseline.
Only the rigid diagnostic also uses nominal160 (162 actual intervals).

| Diagnostic | Cl at 27.0934 m/s | Native difference | Cl at 59.4556 m/s | Native difference |
|---|---:|---:|---:|---:|
| Archived flexible ASWING | -0.002056000 | — | 0.000450000 | — |
| Literal coupled model | -0.001562894 | 23.98% | 0.001272751 | 182.83% |
| Rigid, literal model | -0.001783614 | 13.25% | -0.001783541 | 496.34% |
| Frozen influences | -0.001562901 | 23.98% | 0.001272760 | 182.84% |
| Report moment slope | -0.001535936 | 25.29% | 0.001630031 | 262.23% |
| Sibling lift slope | -0.001944760 | 5.41% | 0.000185329 | 58.82% |

Rigid-wing differences are diagnostic, not failures to reproduce a flexible
case. That calculation holds the original geometry fixed and solves the same
circulation equations, without changing stiffness or claiming structural
equilibrium. The refined rigid result at the lowest speed is
**-0.001794644**, still **12.71%**
weaker in magnitude than the archived flexible result. Both rigid mesh changes
are approximately **0.615%**.
Simply eliminating the current elastic deformation does not close the low-speed
gap. This does not prove that every possible stiffness or coupling correction
is irrelevant.

![Two-speed diagnostic comparison](../../artifacts/isae/ae3-control-setup-20261111/diagnostics.png)

## What the tests resolve

* **Frozen versus updated influences:** maximum change in Cl is
  **0.000650%** relative to the corresponding current
  baseline. This setting cannot explain the observed discrepancy at these two
  states. The literal model and production frozen default remain unchanged.
* **Report pitching-moment slope:** changing only −0.0102 to **−0.0107**, as
  stated in Jan Part IV §3.3 p.13, makes both endpoint errors worse.
* **Sibling lift-control slope:** changing only 0.0581 to **0.0686**, present
  in the original 60O/80O/95O files, reduces the endpoint errors to **5.41% and
  58.82%**. It explains a substantial part of the difference but does not
  resolve either endpoint at the current 5% tolerance. It is not an established
  generating input for the 20O export and has not been adopted.

The lift-only and moment-only changes were separate prospective probes.
Their combination was not solved; nonlinear coupled results must not be
constructed by adding the two observed changes. No parameters were fitted to
the archived curve. Neither a reversal speed nor a full speed curve is inferred
from these endpoints.

## Theory and source audit

Drela's steady description, **Eqs.158–159**, rotates the control-point normal
using the flap increment `F1 * dCLdF1 / dCLda`. OpenSwing's `aero.py` implements
that expression with the file-defined flap units; it does not add a second
degree/radian conversion. **Eqs.72–73** put the lift arm at quarter-chord and
use the local perpendicular Mach correction on the supplied section pitching
moment. The corresponding source expressions agree. An independent saved-data
check of Eq.73 covers **980 section samples**,
with maximum absolute coefficient difference **0**.
This is a targeted formula check, not validation of every load, influence or
structural equation. The [authoritative reference index](aswing-authoritative-references.md)
and checksummed Part IV / Drela sources were consulted and pinned.

The original `Straight_60O.asw` is identical to `Straight_20O.asw` except for its
title, lift-control coefficient and control-span breakpoints. Its title is
`Mowe_temp`, matching the native exports, whereas the 20O input has another
title. This supports auditing input provenance, but is not proof of which
model was used to generate the exports.

The published Git history was followed through the
[February 2025 folder rename](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/a58ec61bbafb22f9915ed4188b34bc35727e05bc)
back to the [initial upload](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/f745fb40b308d85a2a99e039665457177686a9bd).
Both the supplied 20O model and first native export have unchanged Git blobs
across the rename; their earlier paths show only the initial upload. This
does not recover an earlier generating input. Raw API replies, retrieval times,
URLs, SHA-256 receipts and the parent tree are retained in
[reference/ae3-history-20261111](../../reference/ae3-history-20261111/).

The four XFOIL tables and their scripts were also inspected. They do not embed
flap deflection in each output row; the commented postprocessor assigns a
29-value −14…14 sequence, while the driver starts at −15. No inferred row
alignment or newly fitted polar coefficients have been promoted to inputs.
The report's fixed high-Re statement, numerical constants and mixed literal
model coefficients still require reconciliation.

## Verification and next step

Every child retains one BLAS thread and **512 MiB address space /15 CPU seconds
/25 wall seconds**, exits zero and is reaped. The diagnostic checks verify
unchanged mesh/geometry/material properties, parsed control scales, fresh
circulation or full coupled residuals, restored forces/moments and independent
rolling-moment integration. Flexible states also check support balance and the
root clamp. Rigid states do not claim a structural balance. Original sources,
all 725 comparison slots and the original failures remain unchanged.

Next: make an independent **native AVL comparison of the actual rigid AE-3
geometry and control-normal perturbation**, matching normal versus streamwise
chord, sweep, reference dimensions, discretization and force conventions.
This will distinguish an aerodynamic implementation discrepancy from a
generating-input mismatch more strongly than further coefficient substitutions.
Keep original ASWING, modified ASWING-m and experiment separate. Browser/build
checks remain held.

[Prospective plan](../../artifacts/isae/ae3-control-setup-20261111/plan.json) ·
[Audited results and receipts](../../artifacts/isae/ae3-control-setup-20261111/assessment.json) ·
[CSV](../../artifacts/isae/ae3-control-setup-20261111/comparison.csv)
