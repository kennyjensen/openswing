# Daedalus: wing-root motion and mounting loads

The short forward-boom section between the wing and fairing supplies most of
the wing-root rotation identified in the
[wing-lift sensitivity study](daedalus-wing-lift-terms-20261113.md). Its actual
rotation is consistent with the literal stiffnesses and supplied moments.
The wing-to-boom reaction drives nearly all of this deformation. No joint or
stiffness correction is established, and yaw remains **0.074218 versus 0.033986
deg/s/F3** at the reference dip.

![Wing mount motion and cancelling loads](../../artifacts/daedalus-wing-mount-20261113/report/wing-mount.png)

The moment panels show **1.157378 Hz**. Every load term belongs to the same
accepted full-aircraft response; these are not separate aircraft solutions.

## Literal mounting path and compliance

The flight frame is fixed to beam 5 at `t=-15.6`. The fairing extends to
`t=-10`, where a rigid joint connects it to boom station `t=2.5`. The boom's
`t=0` station is rigidly joined to the wing root, with the file's offset.
Rigid-joint rotation compatibility and the nodal rate/rotation identity are
checked at both 0.2 and 1.157378 Hz. Summing the fairing and forward-boom
relative rotations recovers the wing-root rotation.

| Literal segment | EIcc | GJ | EInn |
| --- | ---: | ---: | ---: |
| Fairing, t −15.6 to −10 | 200,000 | 200,000 | 400,000 |
| Boom, t 0 to 2.5 | 80,952.38 → 92,857.14 | 25,000 | 80,952.38 → 92,857.14 |

Stiffness units are lb ft². These are decoded file values, not fitted values.
**14 November correction:** this table previously stated constant boom bending
stiffness of 100,000. The parser and saved solver fixtures already used the
varying literal values; only that summary was wrong. The
[direct input check](../../artifacts/daedalus-transmission-zeros-20261114/literal-mount/result.json)
compares independent interpolation, parsed values and saved endpoint properties.
The fairing is a vertical surface beam, so body-x rotation primarily bends
it; the forward boom is axial along body x, so body-x rotation primarily
twists it. Body-z rotation primarily bends the forward boom.

At 1.157378 Hz, complex rotation amplitudes relative to the flight frame are:

| Path | Body-x rotation, deg/F3 | Body-z rotation, deg/F3 |
| --- | ---: | ---: |
| Fairing | −0.000780 + 0.001258i | +0.000704 − 0.001068i |
| Forward boom, fairing attachment to wing | −0.001957 + 0.005104i | −0.011671 + 0.012269i |

A straight-axis moment/compliance integral differs from the complete complex
rotation vector by **0.106–0.109% for the fairing** and **0.426–0.438% for the
forward boom**, across the two frequencies. It intentionally omits geometric
preload coupling. Independently forming the material compliance and the matrix
curvature identity of steady Eq. 52 gives a **0.160–0.162%** aggregate curvature
difference from the actual moments. Eq. 52 differs at second order from the
production Euler Eq. 53; the theory explicitly distinguishes them. These are
approximate consistency checks, not new native ASWING passes or grounds to
replace the source operator. The two rigid joints remain at their specified
zero relative rotation.

References: the authoritative
[steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
Eqs. 17–20 and 52–56; the
[unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
Eqs. 1–2 and 37–40; and the original manual's
[Ground, Joint and Strut definitions](../../reference/aswing_doc.txt).
The [catalog](aswing-authoritative-sources.json) retains the source identities.

## Which mounting loads drive the motion?

Separate mechanical tangents retain loaded beam geometry and constitutive
coupling. The fairing has 216 retained pose/internal-load coordinates and a
fixed lower cut. The forward substructure covers the entire boom ahead of
`t=2.5`, including the propeller-side portion, with 96 retained coordinates;
its motion at that cut is prescribed from the complete solution. Real inertia
and gravity are supplied as the actual D'Alembert load phasors, alongside
aerodynamic loads and attachment reactions. No vacuum eigenfrequency or
independent dynamic response is inferred from this reconstruction.

The sums reconstruct the entire saved fairing/forward-boom mechanical states
within **6.135e−14 / 6.590e−15**, and their relative rotations within
**2.744e−15 / 1.178e−15 radians/F3**. The extracted joint moment includes both
`arm × delta(force)` and `delta(arm) × force_base`.

The wing reaction alone produces forward-boom rotation
`−0.001962 + 0.005108i` about body x and `−0.011592 + 0.012291i` about body z,
in deg/F3. Compare these with the totals above. Forward-boom airloads,
propeller/point loads, its own inertia/gravity and motion of the cut make much
smaller contributions under these supplied load phases. Fairing motion is
driven by its boom reaction and its own mass/gravity loads, including the
attached point masses.

## The wing reaction contains substantial cancellation

Summing all wing aerodynamic and real inertial/gravity nodal loads, plus the
two braces, independently reconstructs the actual wing-to-boom wrench about
the moving boom attachment. The axial brace derivative is evaluated directly
from its unloaded length, EAw, loaded direction and pretension. It includes
the changing direction and pylon moment arm; both braces remain in tension.

Moments below are **body-axis components at that attachment**, in lb ft/F3:

| Wing load source | Body-x moment | Body-z moment |
| --- | ---: | ---: |
| Ordinary circulation lift | +6.27961 − 15.97522i | +2.56532 + 4.96669i |
| Circulation-rate lift | +2.21146 + 8.47465i | +0.09441 + 0.35983i |
| Profile force and intrinsic pitch couple | +0.00179 + 0.07070i | +0.10167 + 0.35244i |
| Apparent loads | −3.17451 + 3.65884i | +0.40354 − 0.48289i |
| Real inertia and gravity | −3.66379 + 2.06483i | −10.70134 + 2.90724i |
| Both braces | −1.97804 + 2.57709i | −0.00603 + 0.00742i |
| Total wing reaction on boom | **−0.32350 + 0.87088i** | **−7.54243 + 8.11074i** |

The body-x terms strongly cancel. Real inertia/gravity is a major contribution
to the body-z moment. The wrench sum agrees with the direct joint reaction
within **3.450e−9** in the respective native units; transferring each source
through the forward-boom tangent reproduces the joint-driven rotation within
**3.446e−13 radians/F3**.

This points next to the wing's inertial reaction and its frame/elastic-motion
coupling, alongside the aerodynamic phase already identified. It does not
justify changing forward-boom stiffness or the rigid mount. The
[paper's roll-pin diagnostic](daedalus-wing-paper-20261113.md) remains a
different, already tested setup that worsened the Bode dip. Historical native
operating settings and full Bode agreement remain unresolved.

The subsequent [independent current-wing inertia check](daedalus-wing-inertia-20261113.md)
reproduces the real-mass/gravity reaction within 6.603e−10 native units across
0.2 Hz and the dip frequency. Wing-root rotational motion accounts for most
of its elastic yaw-moment contribution. A separate continuous mass integral
changes the complex yaw reaction by 0.298% at the dip for the same motion;
no missing/doubled acceleration or finite-segment inertia term was found.
This checks the applied inertia, not the predicted motion or native Bode match.

## Evidence and limits

The [bounded driver](../../scripts/check_daedalus_wing_mount.py) retains all
plans, source snapshots, field arrays, terminal receipts and input hashes.
All **eight jobs** succeeded and were reaped, with one BLAS thread and limits
of 512 MiB address space, 15 CPU seconds and 25 wall seconds. Maximum CPU time
was **3.559 seconds**, wall time **11.877 seconds**, and RSS **132.856 MiB**.
The mechanical derivative-width and full-matrix compatibility differences
are below 3.331e−11. Subtracting external/joint loads from three perturbed full
residuals reproduces the mechanical function within 4.859e−18. The two reduced
mechanical solves have reciprocal condition estimates above 0.003.

The reconstruction reuses production section/chart functions and supplied
aircraft load phases; it is not an independent solution of the complete
coupled aircraft. No physical equation, default, ISAE fraction or browser/build
verification changed. See the
[combined report](../../artifacts/daedalus-wing-mount-20261113/report/result.json),
[wing-wrench CSV](../../artifacts/daedalus-wing-mount-20261113/report/wing-wrench.csv)
and [verification record](../../artifacts/daedalus-wing-mount-20261113/verification.json).
