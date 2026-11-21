# Daedalus: independent check of the wing position equations

The inboard-wing lead from the [mesh residual study](daedalus-mesh-residual-20261114.md)
has now been checked directly against Drela's steady **Eqs. 48–50, PDF page 12**.
No error was found in these position equations. The analytic derivative agrees
with every position row in both saved aircraft matrices within **3.347e−11**
per scaled entry. Subdivision supplies the largest term in the remaining wing
position account; changed mean rotations and position transport partly offset it.

This narrows the investigation, but does not improve the native Bode match.
At **1.5 Hz**, the complete wing-position equation account has magnitude only
**0.0422% of the original yaw output**, versus **2.350% of the original roll
output**. These are mapped-residual contributions, not independently solved
changes to the aircraft. They cannot explain the large native yaw discrepancy.
No production code, physical input, or ISAE completion fraction changed.

![Position compatibility partition and response context](../../artifacts/daedalus-position-compatibility-20261114/report/position-compatibility.png)

## Source equation and independent matrix check

The [authoritative index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) identify the steady
description. In this literal aircraft, section-axis offsets and axial
compliance are zero. The position equation therefore becomes

```text
g = (r_b - r_a - ds*(u_a + u_b)/2) / L = 0,
```

where `u` is the loaded unit section span vector and `ds` is unloaded arc
length. For a spatial rotation increment `theta`, `du = theta cross u`.
With scaled translations `d = dr/L`, its derivative is

```text
dg = d_b - d_a
     - ds/(2*L)*(theta_a cross u_a + theta_b cross u_b).
```

The saved descriptor uses `K = i*omega*M - A`, with `A` the residual state
Jacobian. Its position rows are consequently **minus** this derivative and
have no mass term. The comparison checks all endpoint columns, verifies zero
dependence on other nodes and internal loads, and checks every position mass
row for zero. Shared-node section span continuity is verified independently.

| Check | Original mesh | Refined mesh |
| --- | ---: | ---: |
| Elements checked | 103 | 206 |
| Position rows checked | 309 | 618 |
| Maximum matrix-entry discrepancy | 2.636e−12 | 3.346e−11 |
| Saved response derivative discrepancy | 5.789e−16 | 3.588e−15 |
| Maximum independent rotation-difference discrepancy | 6.939e−17 | 3.469e−17 |

The rotation check uses fourth-order centered differences at two widths,
`1e−3` and `5e−4`, of actual rotated endpoint frames. No existing matrix
entry is used to construct that derivative. This verifies the literal
zero-strain case; it does not generalize this audit to finite axial/shear
compliance or section-axis offsets.

## What subdivision changes

Consider one original interval, split into lengths `s1` and `s2`, retaining
both original endpoint motions. At the inserted node, the six position rows
have five attainable directions. Their left-null vector is

```text
n = [u_mid, u_mid] / sqrt(2).
```

It eliminates inserted-node translation and rotation from the summed position
defect. After the previous least-squares completion of those five directions,
the remaining residual is parallel to `n`. This reconstruction agrees with
the saved six-row residual within **1.521e−15**. The left-null identity itself
closes within **4.908e−19**.

Keeping the **actual fine** `u_mid` and full-aircraft adjoint fixed, the
remaining scalar separates algebraically into:

- The original coarse position residual, numerically negligible.
- The changed endpoint weights caused by subdivision, using original mean
  endpoint spans and the same endpoint rotation increments.
- The change in those mean endpoint spans after refining and retrimming.
- The transport of the same endpoint motion between the two mean positions.

No midpoint rotation is adjusted to improve the comparison. The previous
completed mapping and all 108 retained-node motions are unchanged.

For roll at 1.5 Hz, the signed projections onto the **net complex whole-mesh
roll change** are:

| Position-equation term | Projection |
| --- | ---: |
| Original coarse residual | +0.000000083% |
| Subdivision | +16.6562% |
| Changed mean endpoint rotations | +2.3166% |
| Position transport | −4.8081% |
| Combined wing position account | +14.1646% |

The two previously identified intervals, **t = −21.4303…−14 and
14…21.4303**, receive subdivision projections of **3.9263% and 3.8936%**.
Their rotation and transport terms nearly cancel. The surviving peaks thus
come primarily from the changed discrete compatibility weights, rather than
from changing the mean section rotations at those endpoints.

An additional steady identity checks the same intervals with the original
mean rotations interpolated to the new node. The subdivision defects have
vector magnitudes about **0.00054 ft** there. Changed mean positions and
rotations cancel those defects in the refined equilibrium. This is expected
for endpoint-average integration of a curved beam; it is not evidence of an
unconverged steady solve or permission to replace Drela's averaging rule.

## Interpretation and limits

The analytic decomposition reproduces the previous full wing position account
within **1.123e−11** in output units. The report retains the small remaining
numerical difference explicitly; its largest signed projection is
**1.254e−7%**. It is not silently assigned to a physical term.

| Output | Whole-mesh complex change / original amplitude | Wing-position account magnitude / original amplitude |
| --- | ---: | ---: |
| Yaw rate | 0.6195% | 0.0422% |
| Roll rate | 16.3476% | 2.3501% |
| Sideslip | 1.6811% | 0.1953% |
| Bank | 17.5339% | 2.5238% |

These magnitudes are not signed amplitude changes. The signed component
projections can cancel, and both the fine null direction and fine adjoint
already incorporate the refined equilibrium. This is an exact equation
accounting with a stated mapping, not a unique separation of physical causes
or a hybrid aircraft solve.

The source position formula and its derivative now have direct evidence.
Further position-row interpolation experiments are unlikely to resolve the
native yaw discrepancy. The next structural audit should examine the
rotation/constitutive rows and their coupling to wing loads, retaining the
current literal material properties and distinguishing local consistency
from a measured effect on the complete Bode response.

## Evidence and execution

The [bounded driver](../../scripts/check_daedalus_position_compatibility.py)
retains the [geometry capture](../../artifacts/daedalus-position-compatibility-20261114/capture/result.json),
[accepted audit](../../artifacts/daedalus-position-compatibility-20261114/audit-v2/result.json),
[report](../../artifacts/daedalus-position-compatibility-20261114/report/result.json),
[CSV partition](../../artifacts/daedalus-position-compatibility-20261114/report/equation-partition.csv),
and [verification receipt](../../artifacts/daedalus-position-compatibility-20261114/verification.json).

Four serial jobs are terminal and reaped: **three successful and one failed**.
The first audit omitted the minus sign between the residual derivative and
the harmonic position rows. Its failed assertion was retained, and only the
new diagnostic was corrected. No production equation or acceptance gate changed.
The final report figure was visually checked.

Every numerical child uses one BLAS thread, **512 MiB address space, 15 CPU
seconds and 25 wall seconds**. Maximum recorded use is **2.050 CPU seconds,
3.878 wall seconds and 112.352 MiB resident memory**. Browser/build jobs remain
held. ISAE fractions and progress scopes are unchanged; no progress event is
added.
