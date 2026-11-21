# SA-11: applicability of connected lifting-line corrections

2026-11-07. The successful [ideal-winglet generalized solves](winglet-generalized-solve-20261107.md)
do not transfer directly to the actual SA-11 winglet geometries. Their
quarter-chord endpoints are separated, and the upper/lower arrangement also
has a three-branch attachment. Twelve source-grouping audits and two geometric
controls establish this distinction without changing the production solver.

An exact decomposition of eight saved root fields also finds that the signed
three-branch circulation imbalance is not the dominant term in the rejected
states. At N96, the upper/lower imbalance is only **−0.09756%** of main-wing
circulation, while the field attributable to separated root origins has
magnitude **9,052.77 m/s** at the selected receiver. These are velocities of
the rejected discrete model, not a prediction of physically attainable flow.

SA-11 remains **163/4,592 at 5%**. No new equilibrium calls, reference passes,
production equations, model inputs, Mach gates or core defaults change.

## A structural attachment is not a continuous aerodynamic line

The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
"Joint" block, defines a joint as a rigid pylon between beam stations. It
allows spatially separated stations. Its "Physical index" section separately
specifies zero mutual vortex core for logical beams sharing a physical index,
and warns about trailing legs passing near another beam's control points.
Neither rule says that a structural joint makes quarter-chord endpoints
coincident or supplies a single ordered aerodynamic curve through a fork.

The saved frozen-influence SA-11 geometries have the previously independently
verified root offsets:

| Winglet root relative to main-wing bound endpoint | Streamwise offset | Vertical offset |
|---|---:|---:|
| Upper | +53.210964 mm | 0 |
| Lower | −25.901302 mm | −0.070 mm |

Both sides and both N48/N96 meshes preserve these offsets. Endpoint graph
analysis identifies three disconnected quarter-chord curves for the upper
model and five for the upper/lower model, even though the structural joints
connect them. This graph describes aerodynamic line geometry only.

## What the reference grouping routines actually do

The audit executes intact `_sort_segments_into_wings`,
`_sort_segments_left_to_right` and `is_continuation` method bodies from MachUpX
revision `9935476395b205e74612b6dc53d931eb1cad8d5e`. The continuation predicate
requires attachment to a parent's tip with origin offset below 1e−12.
All physical nodes remain fixed in the following three metadata fixtures:

| Fixture encoding | Upper: groups | Upper/lower: groups | Result relevant to a port |
|---|---:|---:|---|
| Explicit left/right winglets, retaining exact offsets | 3 | 5 | Each winglet is a separate lifting-line group; no gap inside any ordered group. This does not apply the same connected construction that succeeded on the ideal control. |
| Mirrored winglet pairs, retaining exact offsets | 2 | 3 | The retained sorter places left/right winglets together; consecutive roots in those groups are 2.4852 m apart. |
| Structural-joint-only alias, declaring offsets zero while retaining nodes | 1 | 1 | Ordered entries still have geometric gaps: 53.211 mm for upper and 89.027 mm for upper/lower. The zero-offset metadata contradicts the actual endpoints. |

These are explicit metadata tests, **not full MachUpX input/solver runs** or
claims that every possible MachUpX representation behaves this way. In
particular, the joint-only alias is a deliberately tested invalid mapping,
not a proposed conversion. The differing outcomes show why a port cannot
silently equate a shared ASWING physical index, a structural joint, and a
MachUpX continuation.

A gap between ordered entries does not mean the reference code adds a physical
bound vortex across that gap. It means that group ordering is not a connected
path through the supplied endpoints. This matters before using that ordering
for effective-geometry blending and tangent calculations. No corrected fields
or loads are evaluated by this grouping audit.

Two explicitly nonphysical controls translate each entire winglet so that its
root meets the main-wing endpoint. The upper-only control then has one
connected path, maximum endpoint degree two and zero ordered gap. The
upper/lower control has degree-three junctions and cannot be represented as a
single nonbranching path. The unchanged reference sorter still makes one group,
with a **93.768 mm** jump between consecutive segments. Thus removing root
offsets alone does not make the branching arrangement equivalent to the ideal
two-branch control. Original files and saved results are not moved or replaced.

## Signed circulation at the three-branch root

For the right root, let `Km`, `Ku`, `Kl` be the semi-infinite-ray influence
vectors from the main, upper and lower origins at the selected receiver. With
the saved interval orientations, the root-ray field is exactly

```text
R = Gamma_m*Km - Gamma_u*Ku - Gamma_l*Kl
  = Gamma_m*(Km-Ku) - Gamma_l*(Kl-Ku)
    + (Gamma_m-Gamma_u-Gamma_l)*Ku.
```

The left-root orientation reverses the overall sign. The first two terms are
the field remaining at fixed main/lower circulation if the signed imbalance
is removed by adjusting the upper strength. They do not disappear merely
because `Gamma_m = Gamma_u + Gamma_l`. When the origins are collinear, their
ray differences equal finite streamwise connectors. The lower origin's height
offset adds a separate ray-difference term, retained exactly in the audit.
This is an algebraic decomposition of the existing field, not extra vorticity.

| Saved model | Intervals/beam | Signed imbalance / main Gamma | Geometry remainder speed | Imbalance-term speed |
|---|---:|---:|---:|---:|
| Upper | 48 | +0.264891% | 1,213.73 m/s | 10.93 m/s |
| Upper | 96 | +0.098401% | 4,834.48 m/s | 16.17 m/s |
| Upper/lower | 48 | −2.275092% | 3,973.05 m/s | 0.0000293 m/s |
| Upper/lower | 96 | −0.097561% | 9,052.77 m/s | 21.54 m/s |

The receiver is each saved state's worst point, on its corresponding side;
its location changes between meshes. Magnitudes do not add because the terms
are vectors. Other bound and trailing contributions remain in the complete
velocity. The N48 upper/lower receiver is upstream of the upper-root origin,
which explains its very small imbalance-ray contribution despite a larger
circulation imbalance.

![Root-field contributions](../../artifacts/isae/sa11-generalized-topology-20261107/root-field-decomposition.png)

This supports investigating how force-point velocity is represented around
separated origins, rather than treating a circulation-balance constraint as a
sufficient repair. It does not prove that adding such a constraint would leave
all other circulations fixed. Nor does the large height-difference component
justify closing the 70-micrometre gap: the earlier
[changed-geometry solves](isae-sa11-winglet-root-height-20261107.md) already show
that doing so worsens these rejected states.

## Checks and consequence for implementation

The driver verifies the saved result and source hashes, current example hashes,
all 141 production module hashes and the status/scope hashes. All four full
wake reconstructions agree with the saved production decomposition within
**5.01e−11 m/s**. Independent finite-segment formulas agree with the collinear
ray differences within **4.55e−12 m/s**. A separate scalar audit verifies
circulation sums, vector-component sums, magnitudes, endpoint distances and
complete segment coverage. No new equilibrium or generalized field solve runs.

The simple connected correction remains a useful alternative on its tested
geometry. A production change would require an explicit treatment of offset
and branching junctions, consistent force and wake equations, and checks
against original ASWING results. This audit rules out a direct grouping-only
port as an established solution. The next useful comparison is a resolved
finite-chord representation of the actual SA-11 root geometry, preserving the
offsets and distinguishing its loads from the documented ASWING force law.

That [finite-chord follow-up](isae-sa11-finite-chord-20261107.md) now retains
ten linear solutions and an exact subdivision of overlapping root filaments.
The one-row prescribed field agrees with the direct horseshoe calculation,
but resolved loads remain sensitive to span refinement and several upper/lower
controls predict negative drag. This alternative is not an established repair.

Reproduce in a fresh directory, as a single foreground job:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-sa11-generalized-topology.py --output artifacts/isae/sa11-generalized-topology-new
```

- [Plan and unchanged-source pins](../../artifacts/isae/sa11-generalized-topology-20261107/plan.json)
- [Twelve grouping results, controls and eight root identities](../../artifacts/isae/sa11-generalized-topology-20261107/results.json)
- [Artifact verification](../../artifacts/isae/sa11-generalized-topology-20261107/verification.json)
- [Independent scalar audit](../../artifacts/isae/sa11-generalized-topology-20261107/independent-audit.json)
- [Plot as SVG](../../artifacts/isae/sa11-generalized-topology-20261107/root-field-decomposition.svg)
