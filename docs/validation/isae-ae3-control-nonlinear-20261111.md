# AE-3: independently reconverged control response

Observed 2026-11-11 UTC. **Eight full nonlinear solves pass 100 physical checks
and 30 response checks.** They independently reproduce the saved control
derivative at the high-speed AE-3 diagnostic state, with both the roll constraint
active and acceleration held at its solved value. Halving the perturbation also
passes the prescribed refinement checks.

The archived discrepancy remains. For this conditional setup, the
held-acceleration CldF1 is **0.000185346522**, versus archived **0.000146**:
**26.95% error**. Allowing roll acceleration to respond gives **0.000578437891**,
or **296.19% error** against that same archived derivative. Neither convention
reproduces the native value. These are diagnostic comparisons, not additional
primary votes; the last complete native score remains **434/725**.

## What was solved

The accepted base is the previously disclosed sibling-control/free-roll
diagnostic at **59.4556 m/s**, F1 = 1, nominal 80 / actual **82 intervals** and
frozen jig influences. The lift-control slope is 0.0686 from the sibling input;
the moment-control slope remains −0.0102. Geometry, stiffness, source conventions,
reference dimensions, zero real mass/inertia and other conditions are unchanged.
This setup remains separate from the literal-model primary comparison.

Each job restores that same physical state, with no derivative predictor, and
changes only F1 by **±0.01 or ±0.005 file units**. It reconverges the complete
equations with the original warm Newton algorithm and a 1e−10 solver tolerance.
The two response conventions are explicit:

- **Held acceleration:** retain the actual base roll acceleration,
  **−126.72531217946845 rad/s²**, and allow the support to balance the changed
  net rolling moment. The base physical equations and outputs are checked when
  transferring from the constrained to the prescribed-acceleration network.
- **Active roll constraint:** solve roll acceleration together with the beam
  and circulation unknowns, keeping net body rolling moment zero. Other rates
  and accelerations remain zero.

Both modes retain all source aerodynamic, apparent-inertia and structural terms.
Every returned state passes the fresh complete residual, root-position/frame,
applied/support balance, zero-real-mass and apparent-inertia checks. The seed
stays unchanged. All eight solves take two Newton corrections with one iteration
matrix build, then a fresh final tangent and the unchanged rank gate.

## Response comparison

The centered nonlinear difference is `(output(F1+h) − output(F1−h))/(2h)`.
The independently saved tangent predates these solves. Its active-constraint
prediction combines the fixed-acceleration control and acceleration columns:

\[
\frac{da}{dF}=-\frac{M_F}{M_a},\qquad
\left.\frac{dC_l}{dF}\right|_{M=0}
=\left.\frac{dC_l}{dF}\right|_a
+\frac{\partial C_l}{\partial a}\frac{da}{dF}.
\]

Here `M` is the total body rolling moment including inertial reaction; `Cl`
uses the aerodynamic wrench without apparent loads, in stability axes.

| Response | Saved full tangent | Nonlinear, h = 0.01 | Nonlinear, h = 0.005 |
|---|---:|---:|---:|
| CldF1, held acceleration | 0.000185346517 | 0.000185346488 | 0.000185346522 |
| CldF1, active roll constraint | 0.000578437701 | 0.000578437809 | 0.000578437891 |
| Roll acceleration per F1, active constraint | −126.781448041 | −126.781471290 | −126.781488876 |

At the smaller step, Cl-derivative agreement is approximately **0.00000271%**
for held acceleration and **0.0000327%** with the roll constraint active.
The assessment also checks apparent Ixx and net moment, with absolute gates
for near-zero quantities. A percentage of residual-level net moment is not
interpreted as a meaningful physical error.

The comparisons cover the **entire normalized solution response**: all 1,078
beam/circulation/reaction variables in the fixed case, and those variables plus
roll acceleration in the constrained case. Four tangent comparisons and two
step-refinement comparisons pass the prospective per-component gate
`1e−9 + 1e−5 × |reference|`. The largest normalized error-to-gate ratio is below 0.191.
This is not a comparison of six integrated coefficients alone.

The scalar response gates were fixed in the plan before execution. They use
1e−5 relative tolerance plus quantity-specific absolute allowances; the native
5% comparison policy is unchanged. Maximum fresh equilibrium residual across
the eight solves is **1.12e−13**. None of these checks establishes continuum
mesh accuracy or recovers the archived generating input.

## Relation to the authoritative references

The [reference index](aswing-authoritative-references.md) and its
[checksummed catalog](aswing-authoritative-sources.json) were consulted and the
selected local texts authenticated. Drela's
[steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
§§8.3–8.4, Eqs. 212–217, pp. 50–52, explicitly includes acceleration response
when force/moment constraints are active. Sections 8.5–8.6, Eqs. 218–225,
define the stability-axis transformation and aerodynamic wrench derivatives.
The constrained experiment here retains the one selected rolling equation;
it is not a six-degree-of-freedom free-flight derivative calculation.

Holding acceleration is a distinct mounted response. Its closer agreement with
the archived `MM` value does not prove that the original executable used that
convention. Jan's [Part IV](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf),
§3.3, pp. 13–14, distinguishes the mounted and freely rolling experiments and
original ASWING from ASWING-m. Those distinctions remain intact.

The retained `Roll_rate.sh` contains no explicit node-spacing or circulation-mode
selection. The current native grids remain prospective choices. The archived
export explicitly reports Mach 0 and PG factor 1; substituting speed-derived PG
Mach would contradict that retained context. Historical node/mode defaults,
exact model identity and the MM response convention remain useful setup audits.

## Resource handling and evidence

Two initial numerical children reached the 25-second wall limit without an
accepted result. Both are retained and reaped. The instrumented second attempt
spent **10.86 wall seconds / 2.30 CPU seconds** loading modules before constructing
the base, then exhausted the remaining wall budget during correction.

The successful replay uses the established
[AE-2 serial preload pattern](../../scripts/probe_isae_ae2_incidence_stages.py):
load numerical libraries in a single-thread parent, then fork exactly one
supervised numerical child. No model, residual, matrix or solve is constructed
in the import phase. The parent import phase and numerical child each retain
**512 MiB address space / 15 CPU seconds / 25 wall seconds**. Their times are
reported separately; this is not an end-to-end speed benchmark.

Library preload takes **3.93–7.51 wall seconds** and **1.44–2.33 CPU seconds**.
The accepted workers take **6.03–8.98 wall seconds** and **5.92–6.68 CPU seconds**,
with at most **90,348 KiB RSS**. All eight successful children and both earlier
timed-out children are reaped. No background worker, raised numerical limit,
changed equation or relaxed acceptance gate was introduced. Production source
and the browser/build hold are unchanged.

- [Assessment and all response checks](../../artifacts/isae/ae3-control-nonlinear-r3-20261111/assessment.json).
- [Pinned plan](../../artifacts/isae/ae3-control-nonlinear-r3-20261111/plan.json) and [one-job runner](../../artifacts/isae/ae3-control-nonlinear-r3-20261111/run.py).
- [Original capped attempt](../../artifacts/isae/ae3-control-nonlinear-20261111/cases/free-minus-h010/terminal.json) and [instrumented capped attempt](../../artifacts/isae/ae3-control-nonlinear-r2-20261111/cases/free-minus-h010/terminal.json).

The full control-response calculation is now independently checked for this
state. The next investigation is the retained node and circulation representation
settings against the original driver and documented defaults, with all native
targets and current model distinctions preserved.
