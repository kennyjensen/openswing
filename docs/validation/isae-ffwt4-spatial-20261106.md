# FFWT-4 initial-equilibrium spatial refinement

The latest nominal128/256 pair (159/287 actual nodes) passes all three 0.1%
initial-equilibrium mesh checks: root moment, nodal displacement and small
rotation vectors. This is a spatial check at t=0. Full gust-history spatial
accuracy and all-state convergence remain open.

All five initial root moments pass the 5% native-reference allowance. The
finest error is 0.777709%; refining the mesh does not monotonically improve
agreement with the archive. No physical parameter or operating condition was
adjusted to improve that agreement.

## Results

| Nominal intervals | Actual nodes | Root Mc′ (N m) | Native error | Fresh residual |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 47 | 0.740953051929 | 1.198486% | 1.563e-13 |
| 32 | 63 | 0.736245025601 | 0.555470% | 1.157e-13 |
| 64 | 95 | 0.737825922928 | 0.771387% | 6.006e-14 |
| 128 | 159 | 0.737793772714 | 0.766996% | 3.076e-14 |
| 256 | 287 | 0.737872216990 | 0.777709% | 1.529e-14 |

The archived t=0 value is 0.732178 N m. Each refined mesh keeps the literal
model, prescribed speed 22 m/s and incidence 6°, and the same equilibrium
algorithm and numerical settings. The native reference allowance is separate
from the stricter numerical mesh gates.

| Adjacent nominal counts | Shared nodes | Root-moment change | Displacement change | Rotation-vector change | Gates passed |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16 → 32 | 47 | 0.639465% | 1.304549% | 1.864859% | 0/3 |
| 32 → 64 | 63 | 0.214264% | 0.146746% | 0.074772% | 1/3 |
| 64 → 128 | 95 | 0.004358% | 0.061304% | 0.130712% | 2/3 |
| 128 → 256 | 159 | 0.010631% | 0.007617% | 0.021535% | 3/3 |

The nominal64/128 pair passed root moment and displacement, but rotation still
changed 0.130712%, above the unchanged 0.1% gate. The next independently
computed mesh reduces that rotation change to 0.021535% and passes all three
checks. The maximum displacement change is 2.5168e-7 m; the maximum change in
the rotation vector is 1.8238e-6 rad.

The original nominal32 initial root moment differs from nominal256 by
**0.220525%**. The completed time-refinement study used nominal32. Its
passing time gate therefore does not establish spatial accuracy. A full
response on finer meshes, with time accuracy checked there, remains required.

![Initial load, native error and spatial changes](../../artifacts/isae/ffwt4-spatial-20261106/plots/comparison.png)

[Vector plot](../../artifacts/isae/ffwt4-spatial-20261106/plots/comparison.svg).

## What was checked

The three new cold equilibria at nominal64/128/256 each have a fresh residual
computed on a separately rebuilt network, below 1e-8. The original nominal16
and nominal32 results are authenticated and reused. The solver is the same
138-file archive used for the completed time-refinement studies; imported
module paths and all source bytes are verified. Production equations are
unchanged.

The independent assessor reconstructs the straight-beam cosine stations
without importing solver code, then includes the 30 distinct stations of all
60 literal point masses, the root, and both endpoints. Actual node counts are
nominal+31. It checks the saved jig geometry, connectivity and every station.
Only nominal mesh count may differ between requests; source text, conditions,
model properties, numerical settings and kernel hashes must match.

The nodal comparisons use every shared station without interpolation. Jig
positions are subtracted before comparing displacement, so the undeformed
span cannot hide a bending error. Differences use vector norms, normalized
by the full fine-grid maximum. Rotation vectors stay below 0.1 rad throughout
this study; the comparison is specific to this small-rotation regime. These
checks do not certify circulation or element-centered force/moment fields,
which do not share the same sample locations across grids. The root moment
uses sensor 1's unchanged left trace.

Ten focused audit tests pass. They cover mandatory stations and nesting,
interior deformation/rotation errors, errors hidden by the jig span,
nonfinite fine-only states, incomplete grids, changed jig geometry, skipped
refinement ratios and the wrong sensor trace.

All three new jobs exit successfully. They run serially, one BLAS thread and
512 MiB virtual address space each. Nominal64/128 jobs have 90-second caps;
nominal256 has a 150-second cap for its larger single equilibrium. Actual
complete-process times are 54.09, 66.02 and 72.30 seconds. These include
imports, evidence checks, output and fresh-residual verification; they are
not browser performance benchmarks. There are no failed attempts in this
spatial study.

Evidence under `artifacts/isae/ffwt4-spatial-20261106/` includes:

- `n64/`, `n128/`, `n256/`: full requests, results, progress and reports.
- `terminals.json`: actual subprocess exit codes and commands.
- `assessment-n128.json`: retained intermediate 2/3 result.
- `assessment-n256.json`: independently authenticated five-mesh comparison.
- `audit-tests.xml`: ten passing tests.
- `plots/`: PNG/SVG and plot input hashes.

## Remaining work

Full gust-history spatial accuracy and other physical state fields remain
unvalidated. Exact historical node positions and complete original defaults
are still unrecovered. The other seven fixed histories, hinged variants and
shared suite registration remain required. This does not resolve the cause
of the remaining native discrepancy or validate the whole family.

The tracked fraction remains **200/1,600** from the completed Fixed-1 history.
Repeating its t=0 value on additional meshes adds no distinct native target.
