# SA-11: minimum horseshoe spacing

2026-11-08 UTC. **Minimum horseshoe spacing is implemented as a per-beam mesh
setting and exposed in the Nodes editor.** It applies throughout the beam,
not just at a junction. With the preset below, all 42 tested upper-winglet
operating points have complete, finite moments and pass **294/294 archived
comparisons at 5%**. The previous fixed uniform-32 study passed 217/294.

## Using the setting

In **Nodes**, select a beam and a generated distribution, then set **Minimum
horseshoe spacing**. Zero disables the minimum. The value is a length along
the undeformed beam arc, in the input model's length units, rather than a
difference in its arbitrary parameter `t`. The Nodes table/status reports the
actual applied count; it can be lower than the requested count.

For the selectable **SA-11 upper-winglet** example, use **Nodes → Import mesh**
with [isae-sa11-min-spacing.mesh.json](../../examples/isae-sa11-min-spacing.mesh.json).
A served copy is at `/examples/isae-sa11-min-spacing.mesh.json`. It preserves
the tested 32-interval main-wing nodes and requests uniform 32 on each winglet,
with `min_spacing: 0.0164659927127284`. This produces 16 actual intervals on
each winglet, 64 total. The preset stores the full value; 16.466 mm is its
rounded description, not the exact JSON setting.

The value is the full winglet material length divided by 16, inherited from
the spacing study's prescribed uniform-16 mesh. It was not fitted separately
to operating points. Increasing requests to 64, 128 or 512 produces exactly
the same applied mesh at this minimum. The root receiver stays 3.340043 mm
from the main-wing wake ray across those requests.

The minimum travels with mesh export/import and analysis requests. It does
not alter `.asw` geometry, vortex-core radius, aerodynamic equations or the
default spacing when disabled. It is an OpenSwing meshing control, not a
claim about an authenticated historical ASWING default.

## Meshing behavior

The mesher coarsens generated nodes between required stations, selecting from
both ends to preserve mirror symmetry. If only a conflicting central pair
remains, it uses their center. Every retained material interval must meet the
minimum, within floating-point tolerance. Endpoints, property breaks and
attachments remain mandatory. If required stations themselves are closer
than the requested minimum, the request fails with an explanatory message;
the mesher never removes them silently.

The option is available for uniform, cosine and modified-cosine distributions.
Explicit station lists remain explicit and cannot be combined with generated
spacing controls. The current structural and aerodynamic discretizations
share the applied mesh. A requested increase in count does not imply a finer
applied mesh once the minimum is active.

This is a minimum material interval on each logical beam, not a minimum
Cartesian distance between every pair of wake filaments on different beams.
It does not move the physical root or detach its wake. For the straight SA-11
winglets, limiting adjacent strip widths prevents the root sampling point from
creeping toward the neighboring root wake.

## Reference comparison

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Drela's User Guide, **Physical index**, warns about
trailing legs approaching another beam's control points when a shared physical
index makes the mutual core zero. Its **Considerations for Data Discontinuities**
section requires retaining declared break locations. Steady **Eqs. 64–74 and
150–161** supply the unchanged load, receiver and influence laws. Jan Part I
**p. 35, Figure 22 p. 39 and Figure 40 p. 68** supply the case and geometry
evidence. This numerical spacing rule is not attributed to those sources as
an ASWING default or new physical model.

The aerodynamic comparison uses the previously disclosed report-minus4 input:
the report's −4° upper-winglet twist and the earlier Joint multiplier correction.
The selectable example retains its original +4° twist; importing the mesh does
not change that model. Original and report-derived inputs remain distinct.

All quarter-degree rows from 0° to 5° at both archived speeds were retained.
Density is 1.2256, sound speed 340.21, PG Mach is actual speed / 340.21, and
influences are frozen. Original section data, whole-beam Glauert receivers,
shared physical index 1 and zero mutual core are unchanged. Raw coefficient
targets receive none of the paper's experimental drag plotting allowances.

| Actual speed / archive label | Complete matching points | Scalar comparisons | Maximum normal Mach |
|---|---:|---:|---:|
| 240 m/s / 0.70 | 21 of 21 | 147/147 | 0.73644 |
| 272 m/s / 0.80 | 21 of 21 | 147/147 | 0.81113 |
| **Total** | **42 of 42** | **294/294** | **No local-Mach rejection** |

| Quantity | Maximum absolute error, 240 m/s | Maximum absolute error, 272 m/s |
|---|---:|---:|
| CL | 0.447% | 0.454% |
| CD | 3.596% | 4.829% |
| CDi | 0.896% | 0.906% |
| Cm about the body origin | 0.429% | 0.410% |
| Span efficiency | 1.850% | 1.889% |

The seven comparison channels also include dimensional lift and drag, whose
errors closely follow CL/CD. All states have complete moments; this table does
not count force-only diagnostics. Circulation residuals are below 2.19e-15 and
every section stays at least 6.81 configured stall-transition widths inside its
lift limits.

![Minimum-spacing polar comparison](../../artifacts/isae/sa11-minimum-spacing-20261108/minimum-spacing-polar.svg)

The closest remaining comparison is drag at 272 m/s and 5°, **4.829% high**.
This passes the user's current 5% allowance but leaves little margin for a
tighter allowance. No 64-strip pass or continuum-refinement criterion is added.

The primary SA-11 suite remains **163/9,184**, preserving its original model
variants, sixteen polars, 0°–10° rows and existing mesh requests. This separately
labeled report-derived subset is not added to that denominator or progress
curve. Other configurations, the 0.75/0.78 normalization conflicts and the
remaining angles are still outstanding; full SA-11 is not declared validated.

## Verification and application limits

- **29 new meshing checks pass:** minimum interval length, mirror symmetry
  including odd counts, nonuniform input parameter, required-node conflicts,
  zero-minimum compatibility, tiny-minimum termination and invalid settings.
- **39 existing checks pass:** 30 selected discretization checks and nine
  historical mesh/packet checks. An accepted earlier explicit uniform-32
  aerodynamic control reproduces circulation, velocity and section CL exactly.
- An independent checker authenticates 174 source pins and raw reference rows,
  then reduces saved forces, moments and normal Mach. Maximum coefficient
  differences are 4.45e-16 for force and 2.82e-14 for Cm. Bound/wake replay
  agrees with production velocity within 2.28e-13 m/s.
- The importable preset passes the same Python inspection API used by the
  browser. The selectable +4° upper-winglet model also computes finite moments
  at 0° and 5°, 272 m/s, with maximum normal Mach 0.66593/0.78739. These are
  application smoke checks, not additional reference-comparison passes.
- The Nodes editor passes JavaScript syntax checking. Full browser execution
  remains untested under the existing UserLAnd crash-related hold; no Vite,
  Chromium, build or background solver job was started. The downloadable local
  ZIP has not been rebuilt with this change.

The 42 production calls ran in fourteen serial, three-call batches with one
BLAS thread, 512 MiB address-space, 15-second CPU and 25-second wall limits.
Batch work took 2.35–3.06 seconds, 34.86 seconds combined; peak RSS was at most
235.27 MiB. The earlier standalone uniform-16 plan was prepared but not run:
the user's steering replaced it with this production minimum-spacing check.

- [Production normalization](../../openswing/discretization.py), [mesher](../../openswing/geometry.py), [Nodes editor](../../web/node-editor.js) and [focused tests](../../tests/test_minimum_horseshoe_spacing.py).
- [Serial comparison driver](../../scripts/verify-sa11-minimum-spacing.py), [plan](../../artifacts/isae/sa11-minimum-spacing-20261108/plan.json) and [all results](../../artifacts/isae/sa11-minimum-spacing-20261108/analysis.json).
- [Independent reductions](../../artifacts/isae/sa11-minimum-spacing-20261108/verification.json), [mesh/API/default-control checks](../../artifacts/isae/sa11-minimum-spacing-20261108/mesh-verification.json) and their [driver](../../scripts/check-sa11-minimum-spacing-mesh.py).
- [PNG plot](../../artifacts/isae/sa11-minimum-spacing-20261108/minimum-spacing-polar.png), [plot generator](../../scripts/plot-sa11-minimum-spacing.py) and [plot provenance](../../artifacts/isae/sa11-minimum-spacing-20261108/plot-provenance.json).
