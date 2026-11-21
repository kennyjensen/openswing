# SA-8 isolated-wing profile-drag and projection audit

2026-10-31. Neither a different constant section profile-drag coefficient nor
a rotation of the reported lift/drag axes, considered separately, resolves
the isolated-wing discrepancy in the retained strength-20 reconstruction.
The original registered SA-8 result remains **373/504**. The separate
strength-20 result remains **432/504**, including **212/252** isolated-wing
checks. Its failed fine-mesh CD errors still have median **11.29%**, maximum
**15.66%**. No production equation, native input, target or tolerance changes.

## Input and publication evidence

The fore-only deck contains one straight lifting beam, with no body, engine
or point-drag records. Direct reading of its 41 section-property rows confirms
constant `Cdf=0.006`, `Cdp=0.014`, `CLmin=-0.3` and `CLmax=1.2`.
The parser and captured solver parameters agree. The driver specifies 30 m/s
and the 18 archived incidences; `OPER K I 100` sets the iteration limit, not
the mesh. It does not recover the historical node array or stall strength.

The authors' [ICAS 2022 paper, Table 2, page 8](https://www.icas.org/icas_archive/ICAS2022/data/papers/ICAS2022_0318_paper.pdf)
independently lists the same NACA4309 section constants, including lift slope
6.11 and zero-lift incidence −3.9°. Equation 7 gives the friction, pressure
and stall contributions using local velocity. Its pages 11–12 discuss
querying polars by local incidence/Reynolds number as a future improvement;
this does not support adding an undocumented runtime polar to this case.
The paper includes a fuselage, whereas the later ISAE report says its influence
was neglected. That difference does not identify the setup that produced the
archived outputs. The paper is retained locally with a SHA-256 pin.

The deck's radius property does not establish an omitted wing-volume force:
the ASWING guide specifies this input for fuselage beams. The separate
[body-flow investigation](isae-sa8-body-volume-20261031.md) addresses the
full aircraft, which actually contains a body. It cannot explain the isolated
wing's drag difference.

## Constant profile coefficient: infeasible even before upper stall

For this rigid, unswept wing, the spanwise velocity is zero. The friction
and pressure terms of steady equation 70 therefore have identical velocity
factors. Changing either constant coefficient affects only their sum
`C = Cdf + Cdp`; circulation does not depend on these coefficients.
With all other settings held fixed, each state's total drag obeys

`CD(C) = CD(0.020) + k (C − 0.020)`

where independent scalar integration gives

`k = sum(|V| (V·e_drag) chord ds) / (U² Sref)`.

We compute the entire admissible interval of `C` for each native CD target
using its existing `max(original absolute tolerance, 3% of target)` gate.
There is no optimization or selection of a best-fitting coefficient.

| Scope | Necessary lower bound on C | Necessary upper bound on C | Result |
|---|---:|---:|---|
| All 36 saved states | 0.02311223 at −6°, N128 | 0.02132948 at 10°, N64 | Disjoint |
| Only −3° through +4° | 0.02240762 at −3°, N128 | 0.02202729 at +4°, N64 | Disjoint |

The two meshes also fail separately on the restricted range: each has a
gap greater than **0.00037** between its necessary lower and upper bounds.
Thus this conclusion is not caused by mixing meshes or by the high-incidence
stall region. It rules out a single changed constant, or changing the split
between the two constants, within this fixed reconstruction. It does not
rule out different geometry, circulation, inflow or an undocumented varying
drag law in the producing setup.

## Projection alone: force magnitude is too small at −4°

An orthogonal rotation of lift and drag preserves `sqrt(CL²+CD²)`.
At −4° on the fine mesh, the computed magnitude is **0.01087956**.
The smallest magnitude anywhere inside the native CL/CD acceptance rectangle
is **0.01216588**. The coarse mesh gives the same exclusion.

No choice of reporting angle can therefore bring both outputs within their
current tolerances at this state. This tests a change of output projection
alone; changing the physical incidence and solving a different flow is a
different hypothesis. It also does not exclude combined changes to forces
and projection, which would require independent justification.

## Verification and limits

Six new cold solves cover −4°, 0° and +4° at N128, each with the original
coefficients and with `Cdp` doubled in an in-memory model. This predetermined
perturbation verifies the equation; it is not a proposed native setting.
All source files remain byte-identical.

- All six solves converge and their worker processes terminate successfully.
- Three fresh baseline forces reproduce the retained forces exactly.
- Maximum circulation difference from retained values: **2.22e−16**.
- Maximum local-velocity difference: **7.11e−15 m/s**.
- Maximum force-change error against independent equation-70 integration:
  **8.61e−17**, normalized by `q Sref`.
- An independent verifier reads all 18 original native rows and all 41
  original section-property rows, recomputes the 36 interval/projection checks,
  and checks the three cold perturbation pairs without importing solver code
  or the audit implementation.

The investigation narrows the isolated-wing discrepancy but does not resolve
it. Native stall strength and historical setup remain unverified; the
published approximate strength 40 stays the production default. No fitted
correction is introduced. The broader SA-6–SA-10 work remains unfinished.

Artifacts: [audit and cold-run plan](../../artifacts/isae/sa8-profile-projection-20261031/plan.json),
[analysis](../../artifacts/isae/sa8-profile-projection-20261031/analysis.json),
[independent verification receipt](../../artifacts/isae/sa8-profile-projection-20261031/receipt.json),
[cold-run log](../../artifacts/isae/sa8-profile-projection-20261031/run.log).
