# AE-3: full speed sweep of the qualified roll-constraint setup

Observed 2026-11-11 UTC. The independently sourced control coefficient and
conditional script-constraint interpretation from the
[endpoint study](isae-ae3-control-response-20261111.md) now reproduce the first
five archived rolling moments within **1.20% on both meshes**. The highest-speed
error falls from **28.50% to 13.01%** with refinement, but the two meshes still
differ by **13.71%** there. Near-reversal convergence remains unestablished.

The qualified alternative agrees with **68/72 coefficient comparisons** under
the unchanged 5% policy: **20/24 nonzero comparisons**, plus 48 zero-reference
comparisons using their original absolute gates. These are separate diagnostic
comparisons, not new primary votes. The [primary replay](isae-ae3-current-20261111.md)
remains **50/725**, with 72 computed values, 22 mismatches and 653 uncomputed
targets. No production code, original model, reference target or tracked scope
is changed.

![Qualified AE-3 speed sweep](../../artifacts/isae/ae3-roll-sweep-20261111/comparison.png)

## Inputs and authoritative evidence

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog remain the basis for this investigation. The
alternative uses the original 20%-span aileron geometry and changes only its
lift-control slope from 0.0581 to the **0.0686 supplied by original sibling
model files**. The moment-control slope remains −0.0102. This value was chosen
before these runs from independent source files, not fitted to the response.

The original `Roll_rate.sh` contains `% / 4 23 / P / d`. The manual's active
control-table layout suggests freeing roll acceleration while enforcing zero
net rolling moment. The diagnostic explicitly implements that constraint and
keeps angular rates at zero. The exact archived table mask and generating file
remain unknown. Jan Part IV p. 13's constants, highest-Reynolds-number statement,
mounted experiment and free-roll experiment remain distinct evidence; they do
not establish this exact historical operating setup.

The additional manual review found that the original user manual describes
`M` output axes, while the extended manual p. 23 identifies force-derivative
matrix reporting. Neither establishes the archived `MM` response convention.
Drela's steady description §8.3, Eqs. 212–213 and §8.6, Eqs. 220–223 includes
acceleration response and the corresponding force chain rule. The ratio clue
from the endpoint study does not authenticate a fixed-acceleration native
derivative convention. This question remains open.

Both grids retain cosine spacing, mandatory root/flap breakpoints, the original
geometry/material laws, literal references, density, Mach zero, F1 = 1 file
unit, updated influences and the original root attachment in body coordinates.
Nominal 80/160 produce **82/162 actual intervals**. No historical `NODE` array
is inferred. All twelve solutions are unstalled.

## Complete speed comparison

Errors below are absolute relative errors against the printed original ASWING
values. The original coefficient normalization and force conventions are kept.

| Speed (m/s) | Native Cl | Nominal-80 Cl | Nominal-160 Cl | Cl error: 80 /160 | CX error: 80 /160 |
|---:|---:|---:|---:|---:|---:|
| 27.0934 | −0.002056 | −0.002050818 | −0.002066628 | 0.252% /0.517% | 2.094% /2.339% |
| 38.5020 | −0.001957 | −0.001949714 | −0.001969931 | 0.372% /0.661% | 3.940% /4.016% |
| 43.0429 | −0.001878 | −0.001868665 | −0.001892111 | 0.497% /0.751% | 2.589% /2.539% |
| 47.2340 | −0.001759 | −0.001745901 | −0.001773899 | 0.745% /0.847% | 2.850% /2.616% |
| 50.9245 | −0.001578 | −0.001559106 | −0.001593440 | 1.197% /0.978% | **5.616% /5.146%** |
| 59.4556 | +0.000450 | +0.000578259 | +0.000508538 | **28.502% /13.009%** | 2.230% /0.075% |

Thus only two channels at two operating points miss the reference gates on
both grids: CX at 50.9245 m/s, and Cl at 59.4556 m/s. The first five rolling
errors have median **0.703%**, range **0.252–1.197%** across both meshes.
Their maximum rolling mesh change is **2.155%**. Mesh change is measured
relative to the finer value; the prospective 5% check passes for all CX pairs
and the first five Cl pairs, and fails for the last Cl pair. Two grids do not
prove continuum convergence or identify the historical discretization.

The twelve states pass **132 physical checks**, including fresh full residuals,
independent aerodynamic and full-fluid wrench reconstruction, support balances,
root position/frame, zero angular rates and the net-roll constraint. Maximum
fresh full residual is **9.266e−13**. Ten new cold solves supplement the two
previously checked endpoint solves; no endpoint was counted twice.

## Bounded refinement and memory investigation

A separate nominal-320 run at the final speed was chosen because the 80/160
mesh change exceeded the prospective gate. It failed during full-Jacobian
assembly while attempting the first 25%-load stage, before returning a solution.
The failed allocation was **2.01 MiB** for a `(16434, 16)` local-geometry block
in `LocalGeometryMatrix.columns()`. The process used **9.72 CPU /20.35 wall
seconds** and **303,420 KiB peak RSS**, within a **512 MiB address-space cap**.
RSS and address-space use are different quantities. This is a resource failure,
not an aerodynamic mismatch or a completed refined result.

An isolated candidate copied the production package and changed only two
statements: release the obsolete Newton matrix/factor before constructing its
replacement. A nominal-160 high-speed control passes its 11 physical checks and
**nine parity checks with exactly zero difference** in coordinates, internal
resultants, reactions, circulation, aerodynamic wrench and operating values.
However, the nominal-320 candidate still fails at the same allocation. It uses
**8.62 CPU /11.77 wall seconds** and **303,812 KiB peak RSS**. Releasing obsolete
storage alone is therefore insufficient. The candidate is **not adopted**.

Both failed refinements, their tracebacks, source pins and terminal receipts
are retained. No larger resource limit, reduced physical model or changed
reference tolerance was used. All **13 newly launched children** are terminal
and reaped: ten sweep solves, one original refinement and two isolated
candidate runs. The saved start/end records confirm nonoverlapping numerical
worker windows. Every child used one BLAS thread and the unchanged
512 MiB /15 CPU-second /25 wall-second limits. Browser/build checks remain held.

Next, reduce temporary geometry-derivative assembly storage without dropping
matrix terms, verify that change on controls, and repeat the bounded refinement
only after that implementation changes. Continue auditing the native `MM`
convention and exact generating inputs. The current evidence supports the
setup/mesh investigation; it does not validate all AE-3 physics or recover the
remaining derivative, inertia and ASWING-m targets.

Evidence: [prospective sweep plan](../../artifacts/isae/ae3-roll-sweep-20261111/plan.json),
[assessment](../../artifacts/isae/ae3-roll-sweep-20261111/assessment.json),
[CSV](../../artifacts/isae/ae3-roll-sweep-20261111/comparison.csv),
[refinement plan](../../artifacts/isae/ae3-roll-refine-20261111/plan.json),
[isolated candidate plan](../../artifacts/isae/ae3-rebuild-memory-20261111/plan.json),
[saved-data assessor and plotting script](../../scripts/summarize_isae_ae3_roll_sweep.py).
