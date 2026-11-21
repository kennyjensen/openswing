# SA-13: remaining continuous curves and published force laws

**The NACA finite-body corrections do not resolve the blue curves on the
currently reconstructed outlines.** They reduce several errors, but this
does not establish an omitted ASWING term. The geometry and normalization
questions remain material. No production equation, default or acceptance
fraction changed; **SA-13 remains 0/612 and SA-12 remains open**.

## Equations compared

Drela's steady description, printed p.16, Eqs.68–69, gives the following
body-transverse force for an isolated straight body in uniform flow:

`f_z/q = sin(2 theta) d(pi R²)/dx`.

The cited primary [NACA-TR-405](https://ntrs.nasa.gov/api/citations/19930091479/downloads/19930091479.pdf)
contains two distinct theoretical curves in Figs.6–8, printed pp.131–132:

- The local ellipsoid approximation, Eq.10 on p.130:
  `f_z/q = pi R sin(2 theta) sin(2 alpha)`.
  Here **theta is flight incidence, alpha is the local hull tangent angle**,
  and `tan(alpha) = dR/dx`. Thus it is the Drela uniform-flow expression
  divided by `1 + (dR/dx)²`.
- Munk's finite-body approximation multiplies the Drela expression by
  `k2 − k1`. The figure captions give **0.924 for R33, 0.817 for R101,
  and 0.78 for RS1**. These are published constants, not fitted multipliers.

The NACA text also discusses translating the local-ellipsoid curve to balance
positive and negative areas; Fig.6 explicitly mentions that correction.
Its numerical shift is not supplied. This audit evaluates Eq.10 **without
that shift** and does not claim to reproduce the complete plotted NACA curve.
Neither NACA approximation is silently substituted for ASWING's force law.

Jan Part I §6.2, p.40, instead describes a modification that accepts a supplied
radius derivative. It does not document adding either of these NACA force
corrections. The legend “Continuous ASWING 5.96” alone cannot establish the
inputs or computation that generated the stored curve.

## Conditional comparison

All three laws use the same existing closed outline, natural cubic radius
interpolation and primary incidence: **10°, 10°, 9°** for R33, R101 and RS1.
Nothing is fitted to the load ordinates. Diameter is twice the largest
tabulated radius, retaining the previous reconstruction's convention.

The table reports **RMSE divided by the archived curve's maximum absolute
ordinate**, in percent. These are conditional discrepancy measures, **not
the native 5% pointwise relative-error acceptance test**.

| Hull and ordinate assumption | Compared / retained blue values | Drela Eqs.68–69 | NACA local ellipsoid, no balance shift | NACA Munk |
|---|---:|---:|---:|---:|
| R33, `f/(qD)` | 35/64 | 15.83% | 11.70% | 12.70% |
| R101, `f/(qD)` | 74/74 | 115.83% | 71.09% | 86.80% |
| R101, primary `f/q` in feet | 74/74 | 38.56% | 15.64% | 28.17% |
| RS1, `f/(qD)` | 24/65 | 88.37% | 42.80% | 60.65% |

R101's dimensional alternative uses the primary figure's 33.01-inch model
length; it is not pooled with the dimensionless alternative. The maximum
absolute discrepancies for the local-ellipsoid expression, normalized by
curve peak, are still **26.92%, 60.88% and 82.94%** for R33, dimensional R101
and RS1. A better RMSE therefore does not identify that law as the generating
equation or validate the reconstructed inputs.

R33 retains 28 unavailable entries and one finite point outside the closed
outline. RS1 retains 41 unavailable entries. No extrapolation or missing-value
fill is used. There are **133 distinct compared lift stations**; R101's
alternative normalization repeats its same 74 stations. The continuous
pressure curve is not a force-law comparison and remains untouched.

## Geometry remains a separate unknown

| Hull | Reconstructed `L/D` | ISAE reported `L/(2R)` | Largest radius-knot gap / body length |
|---|---:|---:|---:|
| R33 | 8.123 | 16 | 37.197% |
| R101 | 5.577 | 11 | 1.866% |
| RS1 | 3.227 | 6 | 1.562% |

The roughly factor-two aspect-ratio conflict was already identified in the
[source audit](isae-sa13-sources.md). The plotted outline's axial and radial
display scales are not independently authenticated physical dimensions.
R33's particularly large gap runs from **24.856% to 62.053%** of the existing
closed-body length. A smooth interpolant across it is a reconstruction, not
a measured radius/derivative distribution.

There is now independent historical support for **R101's fineness ratio near
5.5**, rather than 11. The public abstract of the contemporary
[1929 technical description](https://doi.org/10.1108/eb029202),
*Aircraft Engineering* 1(9), pp.305–312, explicitly gives 5.5, describes a hull
without a parallel portion, and relates it to NPL shape U 721. This is a
full-airship description, not the exact R&M1169 test-model table. It supports
investigating a radius/diameter convention error in the ISAE caption; it does
**not** justify halving the reconstructed radius to enforce 11 or authenticate
every existing radius sample. The public-abstract
[observation](../../reference/isae-sa13/primary-model-search-20261109/r101-1929-abstract-observation.json)
records provenance and the access limitation: the full article was not read,
and direct HTML download returned 403. Original R&M801 and R&M1169 reports
were not recovered in this search.

These findings rule out treating a missing NACA correction as a sufficient
explanation **on this reconstruction**. They do not rule out different
original geometry, supplied derivatives, or postprocessing. The next useful
source evidence is the actual analytic radius/derivative definition or a
physically dimensioned hull table. Additional mesh refinement of this same
uncertain outline cannot recover those inputs.

## Reproduction and checks

[Audit script](../../scripts/audit_sa13_continuous_laws.py) ·
[complete station results](../../artifacts/isae/sa13-continuous-laws-20261109/analysis.json).

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/audit_sa13_continuous_laws.py --output /tmp/sa13-laws.json
```

The output path must not already exist. The script verifies the checksummed
primary PDFs and all **1,530 coordinate pairs** against the four original
MAT figures. Eq.10's tangent-angle and slope forms agree within `5.56e-17`.
This checks arithmetic and source extraction; it is not an independent
physical validation. The run completed in **2.88 s**, with **239,132 KiB** peak
RSS, one BLAS thread and limits of 512 MiB, 15 CPU seconds and 25 wall seconds.
It imports no OpenSwing module and makes no solver calls.

All 612 native targets, including 136 unavailable values, are retained.
The earlier full JSON replay of 180 valid **discrete** lift stations remains
separate. Browser/WASM/build checks remain held.
