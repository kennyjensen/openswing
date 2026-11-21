# SA-13: pressure observable conflict

**Subsequent finding:** the [geometry-identity audit](isae-sa13-pressure-geometry-20261109.md)
reproduces every finite red ordinate as `100*(backward radius slope)^2 - 5`.
This identifies a source-output mapping issue. The Cp bound below remains
conditional on the full-Bernoulli interpretation; it does not establish invalid
flow for a differently defined velocity-squared ordinate. No reference row or
native denominator is discarded.

Observed 2026-11-09 UTC. This source-only follow-up leaves SA-12 open and
does not start an SA-13 solver sweep. **SA-13 remains 0/612**, including all
136 unavailable reference entries. Recovering geometry alone would not resolve
every comparison: one archived pressure value conflicts with the declared
steady incompressible Bernoulli interpretation.

## Necessary bound on the pressure observable

Jan Part I **§6.2, printed p.40**, describes obtaining pressure from numerical
surface velocities using steady Bernoulli. Figure 24(d), **p.42**, labels the
quantity as a dynamic-pressure ratio, while the cited primary source,
NACA-TM-574 **printed p.11 / PDF p.13**, derives static gauge pressure from
the squared total velocity. The existing [source audit](isae-sa13-sources.md)
therefore interprets the ordinate as

`100 Cp = 100 (p − p∞) / q∞ = 100 (1 − |V|² / U∞²)`.

For steady incompressible flow with the reference stagnation pressure,
`|V|² / U∞² ≥ 0`, so `100 Cp ≤ 100`. This necessary condition is independent
of hull geometry, mesh, radius derivatives and sensor placement.

| Archived pressure series | Finite / retained ordinates | Maximum 100 Cp | Entries above 100 |
|---|---:|---:|---:|
| Continuous ASWING 5.96, modified implementation | 103/103 | 99.8511 | 0 |
| Discrete ASWING 5.96, original-discretization label | 56/103 | **173.2016** | **1** |

The conflicting discrete entry is **row 2**, at stored abscissa **1.7927331**.
It implies `|V|²/U∞² = −0.732016`, which cannot be produced by the full
Bernoulli formula for real velocities. The closest admissible ordinate, 100,
still differs by **42.2638%**. Even an illustrative 5% relative band starts at
164.5415. This illustration does not assign a new tolerance: the registered
figure comparisons retain their unset precision/tolerance contract.

The other pressure values satisfying the bound does not validate those values
or establish their generating inputs. The pressure figure's filename says
R101, whereas the cited primary pressure study describes ZR III; that existing
identity conflict also remains unresolved.

## Consequence for development

A different pressure normalization, a linearized postprocessing formula or an
export error could explain the value. These are hypotheses, not recovered
historical behavior. The evidence does not identify which is responsible, and
does not justify clamping the reference or changing OpenSwing's pressure law.
The apparent conflict is specifically conditional on the stated incompressible
Bernoulli observable; it is not a bound for every compressible pressure
coefficient or every normalization.

Keep all eight ASWING-labelled series, their **476 finite and 136 unavailable
entries**, and the original/modified distinction. Original radius/derivative
tables, operating and mesh settings, interpolation, and sensor coordinates are
still absent. No graph reconstruction becomes an original native test here.
The useful next source evidence is the original SA-13 model/driver and the
pressure postprocessing that generated this red curve, rather than another
mesh sweep of a reconstructed hull.

The old graph-based study also describes an endpoint display defect as an
unapplied candidate. That is historical: the later
[source transition](endpoint-source-transition.json) applied the exact-knot
repair, and current `Distribution.evaluate` contains it. It should not be
treated as an outstanding SA-13 fix or a new parity pass. Current browser/build
checks remain under the existing UserLAnd hold.

## Reproducible evidence

The [audit script](../../scripts/audit_sa13_pressure_reference.py) imports only
the standard library and the existing source adapter. It authenticates the
pinned figures, decoded series, report and primary source; retains every
declared row; and evaluates the conflicting value with Decimal arithmetic.
The [analysis](../../artifacts/isae/sa13-pressure-reference-20261109/analysis.json)
contains the exact binary64 source values and source hashes.

An independent read of the original MATLAB figure confirms the red-series
row, abscissa and ordinate bit for bit; all **15 source pins** verify. The
[verification receipt](../../artifacts/isae/sa13-pressure-reference-20261109/verification.json)
records **10.91 s**, peak RSS **54,920 KiB**, one BLAS thread, 512 MiB address
space, and 15 CPU/25 wall-second caps. No production imports or solver calls
were made. The initial standard-library audit invocation exposed a relative
`__file__` path issue under `runpy`; this was corrected before creating the
analysis artifact.

Primary local sources:
[Jan Part I](../../reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf)
and [NACA-TM-574](../../reference/isae-sa13/naca-tm-574.pdf).
No solver equations, defaults, native-reference values, completion fractions
or tracked scopes changed.
