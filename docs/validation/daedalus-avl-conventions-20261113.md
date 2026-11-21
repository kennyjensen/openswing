# Daedalus: separating the loaded-surface AVL conventions

The preceding loaded-wing/fin discrepancies are largely differences in where
the two formulations sample velocity. Explicit replays now reproduce both
saved endpoints, including circulation, induced velocity and integrated
circulatory loads. Adding only the measured isolated rigid-body-rate load
differences to the full dynamic matrix changes yaw at the reference dip by
**−0.187%**. This limited correction does not resolve the **+118%** Bode
discrepancy. No production physics, defaults or aircraft properties changed.

This follows the [native loaded-surface comparison](daedalus-loaded-avl-20261113.md).
The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Drela's steady description, **pp. 31–33, Eqs. 150–159**,
explicitly uses the whole beam's Glauert-angle midpoint and weighted physical
interpolation. In particular, Eq. 154 defines the beam-axis receiver and
Eqs. 155–156 define its force/control offsets. OpenSwing follows that choice.
The native conversion has one AVL SECTION interval per original structural
interval, and uses AVL's section-local interpolation. The prior
[receiver source audit](isae-sa11-root-moment-envelope-20261108.md#which-receivers-actually-moved)
documents that distinction in `amake.f` and `sgutil.f`.

## Exact endpoints, explicit intermediate operators

Two bounded jobs use the saved baseline, ±roll-rate and ±yaw-rate cases for
the actual loaded wing and fin. The original vortex endpoints, body-x wake,
Mach zero, unit speed/density and isolated-surface scope remain fixed.
Each case is replayed in this order:

1. Native AVL coordinates, normals, quartic core and force conventions.
2. ASWING's zero same-beam core and exact `1/(4*pi)` kernel multiplier.
3. ASWING control-point positions, including the imposed rate velocity there.
4. ASWING control-point normals at the original material sampling locations.
5. ASWING force-velocity receivers, including the imposed rate velocity there.
6. ASWING material span times interval length in the force cross product.
7. ASWING physical quarter-chord moment arm.

While changing the velocity receiver, the force application point is held
at the native location until the final step. Thus receiver and moment-arm
effects are distinct. The increments below depend on this disclosed order;
they are not a unique attribution of interacting choices.

All **70 small circulation solves** pass the 1e−11 residual gate. At each
native endpoint, reconstructed circulation and velocity satisfy 2e−12
absolute/relative gates against native output. At each final endpoint they
satisfy the same gates against saved production output. Both integrated
force/moment endpoints satisfy 2e−10 absolute and 2e−12 relative gates.
No physics was adjusted to close these comparisons.

| Change toward ASWING convention | Wing yaw moment / yaw rate: percentage points of native | Fin yaw moment / yaw rate: percentage points of native |
| --- | ---: | ---: |
| Core and kernel multiplier | −0.000015 | +0.000010 |
| Control-point location | −0.613318 | −4.772962 |
| Control-point normal | −0.009591 | +0.000001 |
| Force-velocity receiver | −7.821917 | −0.000301 |
| Force vector | −0.026659 | −0.000001 |
| Moment arm | +0.048358 | −0.000045 |
| **Total** | **−8.423142** | **−4.773297** |

The wing's roll-moment/roll-rate difference similarly includes −1.255
percentage points from control-point placement, partly offset by +0.270
from the moment arm. Every force and moment component, both rate inputs,
all intermediate circulations and geometry arrays are retained in the
[wing result](../../artifacts/daedalus-avl-conventions-20261113/wing/result.json)
and [fin result](../../artifacts/daedalus-avl-conventions-20261113/fin/result.json).
This explains the reported differences without recommending AVL's receiver
rule as an ASWING replacement.

## Limited projection into the coupled response

A second diagnostic asks how much the **measured isolated steady rate-load
differences alone** affect the existing full-aircraft response. For each
surface, native minus OpenSwing force/moment derivatives are reconstructed
strip by strip from the saved ±rate solutions. Their global wrench matches
the preceding replay within **4.27e−9** in the unit-speed/density convention.

For a physical speed `U`, density `rho`, and normalized body rate
`omega = W*zOmega`, the unit-state derivative scales by `rho*U*W`.
Each distributed increment is transferred conservatively to the existing
structural nodes; its resultant force/moment closes within **2.85e−14**.
Only the free-frame roll/yaw-rate columns of `A` receive those force and
moment increments. The correction is affine about the accepted equilibrium,
so the base state is preserved. `M`, the input/output maps, circulation rows
and all other columns remain unchanged.

This is deliberately **not a complete alternative physical model**: the
isolated Mach-zero differences do not include their corresponding changes
to circulation equations, elastic motion, mutual influences, PG Mach,
aerodynamic lag or apparent inertia. Consequently it tests the size of a
specific steady load correction, not equivalence of two unsteady solvers.

All **12 direct, 2,044-coordinate harmonic solves** pass the existing
conditioning and full-equation residual gates. Yaw magnitudes are in deg/s
per native F3 unit:

| Frequency, Hz | Baseline | Wing correction | Fin correction | Both | Both versus baseline |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 0.121763 | 0.120611 | 0.121140 | 0.120001 | −1.447% |
| 1.0 | 0.075499 | 0.075521 | 0.075251 | 0.075272 | −0.301% |
| 1.157378 | 0.074218 | 0.074331 | 0.073967 | 0.074079 | −0.187% |

At the last frequency, the reference drawing is **0.033986**. The limited
correction barely changes that mismatch. Both corrections change roll/bank
magnitudes by roughly 1% there. These results lower the priority of the
isolated rigid-rate load differences as an explanation, but do not rule out
differences in the full unsteady circulation/elastic-motion coupling.

Complete complex yaw, roll, sideslip and bank outputs, matrix increments and
numerical diagnostics are retained for
[0.1 Hz](../../artifacts/daedalus-avl-conventions-20261113/low-rate-projection/result.json),
[1 Hz](../../artifacts/daedalus-avl-conventions-20261113/one-hertz-rate-projection/result.json)
and [the dip frequency](../../artifacts/daedalus-avl-conventions-20261113/dip-rate-projection/result.json).

## Reproduction and status

Use [the driver](../../scripts/check_daedalus_avl_conventions.py) with a fresh
tag for each job:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/check_daedalus_avl_conventions.py \
  --beam 1 --tag fresh-wing
```

The `project` stage accepts `--frequency` and reads the retained `wing`/`fin`
replays and source-equation matrices. Its plan pins those inputs explicitly.
All five jobs were serial, with one BLAS thread and the existing 512 MiB
address-space, 15 CPU-second and 25 wall-second limits. Maximum observed use
was **2.922 CPU seconds, 5.377 wall seconds and 163.325 MiB resident memory**.
Every diagnostic child and parent was reaped. Source snapshots and original
comparison evidence were preserved. No native solver was rerun.

The documented ASWING receiver and force laws remain the implementation
target. The remaining Bode investigation concerns the full moving aerodynamic
response and its coupled phase, together with the still-unavailable original
operating settings. These diagnostics add no native Bode passes or ISAE
completion increments.
