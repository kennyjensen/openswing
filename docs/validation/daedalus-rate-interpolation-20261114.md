# Daedalus: interior orientation and angular-rate interpolation

Componentwise interpolation of the nodal angular rates does **not** explain
the missing rudder Bode dip. At 1.157378 Hz it changes yaw from **0.0742178** to
**0.0742164 deg/s per F3**, or **-0.00185%**. The published magnitude is
**0.0339862**, leaving **+118.37%** error. Across three sampled frequencies,
all twelve output magnitudes change by less than **0.011%**.

![Four-output comparison](../../artifacts/daedalus-rate-interpolation-20261114/report/comparison.png)

The separate Euler-angle comparison below is a local geometry/rate probe,
not a solved alternative Bode response. Production interpolation is unchanged.

## Source review and position checks

The [authoritative index](aswing-authoritative-references.md) and checksummed
source catalog were consulted. Relevant definitions are:

- **Steady Technical Description, p. 32, Eq. 154:** aerodynamic section positions
  use the Glauert-angle midpoint, then weighted interpolation in material arc
  length between the two node positions. This Glauert angle is distinct from
  the structural Euler twist angle.
- **Unsteady Extension, p. 4, Eqs. 1–4:** nodal relative angular velocities
  have body xyz components. The published mapping from angular velocity to
  Euler-angle rates includes the beam-to-body transformation. They are not
  csn-component arrays requiring another rotation before use.
- **Unsteady Extension, pp. 7–8, Eqs. 22–36:** local velocity and angular rate
  enter the kinematic velocity at aerodynamic offsets and the unsteady lift.
- **Unsteady Extension, pp. 13–14, Eqs. 60–62:** the structural damping
  discretization uses endpoint-average quantities. This does not by itself
  specify the interior aerodynamic rotation interpolant. The literal aircraft
  has zero material damping.

The references specify the location and nodal variables but do not explicitly
identify geodesic versus componentwise Euler interpolation for the interior
orientation. The alternative below is therefore conditional, not an identified
native ASWING algorithm.

An independent calculation from the saved Glauert node angles reproduces the
current interpolation fractions to **1.69e-14** and the deformed mesh sample
positions to **2.14e-14 ft**. All five beam meshes are checked; this validates
the aerodynamic location rule for the four lifting beams. It does not replace
or validate the distinct Gauss quadrature used for body-fluid loads.

## Interior angular rates

The current local motion follows the exact time derivative of
`Q(f) = Qa exp(f log(Qa^T Qb))`, with fixed material fractions. The diagnostic
instead uses `(1-f) omega_a + f omega_b` for the interior body-axis angular
rate, and the same interpolation for its body-frame time derivative. This
alternative is **not** the exact derivative of the unchanged geodesic
orientation; it treats nodal rates as separately interpolated discrete fields.

The conditional replacement is limited to non-material interior motion
sampling used by the airflow calculation. It preserves nodal kinematics,
translations, section orientations, completed endpoint real-inertia loads,
point-object motion, structural damping sampling and the source force-transfer
rule. No virtual-power transfer from the other structural policy is substituted.

At the original physical trim, both full residual arrays are **bitwise equal**,
with maximum scaled residual **1.90165e-10**. No retrim or constant residual
offset is needed. At 1.157378 Hz, using the retained original harmonic direction
and mean geometry, the angular-rate differences are:

| Beam | Relative field-norm difference | Maximum absolute angular-rate difference, rad/s per F3 |
| --- | ---: | ---: |
| Wing | 0.03733% | 3.306e-6 |
| Elevator | 0.001038% | 4.745e-7 |
| Rudder | 0.000197% | 2.304e-7 |
| Body / boom | 0.01167% | 5.424e-6 |
| Fairing | 0.000578% | 2.543e-9 |

These local differences alone are not output-error bounds. The subsequent
coupled calculation retains all **2,044 states**, evaluates the complete
alternative nonlinear residual, and iterates its harmonic response using the
original descriptor only as a preconditioner. Its condition estimate does not
certify the alternative operator's rank. Each final response satisfies the
unchanged gates of residual <2e-11 and next relative output correction <2e-7,
at both derivative widths **0.002 and 0.004 on the same final state**.
The maximum paired residual is **8.235e-12** and the maximum difference between
the two output corrections is **9.110e-9 relative**.

| Frequency, Hz | Original yaw | Linear-rate yaw | Published yaw | Change from original |
| --- | ---: | ---: | ---: | ---: |
| 0.1 | 0.121762645 | 0.121762637 | 0.118238214 | -0.00000680% |
| 1.157378 | 0.074217773 | 0.074216402 | 0.033986190 | -0.00185% |
| 1.5 | 0.094316249 | 0.094316397 | 0.081818136 | +0.000156% |

Yaw units are deg/s per F3 unit. At the dip, roll, sideslip and bank change by
-0.00934%, +0.000667% and -0.01009%, respectively. The graph's three markers
per output are the new results; continuous curves are retained earlier data.
No new minimum, frequency sweep or native-reference pass count is claimed.

## Separate Euler-angle comparison

Linearly interpolating the absolute surface/body Euler triplets at the same
material fractions gives the following **mean** section-orientation differences
from the current rotation interpolation:

| Beam | Maximum orientation difference, degrees |
| --- | ---: |
| Wing | 0.0022204 |
| Elevator | 0.00006129 |
| Rudder | 0.000000153 |
| Body / boom | 0.00001540 |
| Fairing | 0.00000000772 |

The exact first time derivative of this alternative Euler interpolant is also
evaluated on the retained original harmonic direction. Nodal Euler rates use
the published mapping `theta_dot = (R K)^-1 omega`; the interpolated rate is
then transformed back with the midpoint `R K`. Its relative field-norm
differences are **0.03510%** for the wing, **0.001204%** for the elevator,
**0.000205%** for the rudder, **0.01160%** for the body and **0.000576%** for the
fairing. These are local comparisons at the original mean/direction. They do
not include the equilibrium change or feedback of a different orientation
operator. No coupled Euler-interpolation result is inferred from the
componentwise-rate response above.

## Reproducibility and remaining question

Driver: [check_daedalus_rate_interpolation.py](../../scripts/check_daedalus_rate_interpolation.py).
Evidence: [study directory](../../artifacts/daedalus-rate-interpolation-20261114/),
[verification receipt](../../artifacts/daedalus-rate-interpolation-20261114/verification.json).
All **nine** bounded serial jobs succeeded and were reaped. Eighty complete
residual probes are explicitly recorded, in addition to system initialization.
Limits remain one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall
seconds. Production code, public aircraft, source catalog and ISAE fractions
remain unchanged. No browser, Node, build or background solver job ran.

The position rule passes, and the tested angular-rate alternative is negligible
for this mismatch. A coupled Euler-orientation comparison would need consistent
interior angular rates/accelerations and a fresh physical trim; the small local
differences do not replace that calculation or establish native ASWING's choice.
