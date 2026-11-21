# Daedalus: coupled response with Euler interpolation

The tested interior-orientation alternative does not explain the published
yaw-rate dip. With consistent angular rates and accelerations and a fresh
physical trim, yaw at 1.157378 Hz changes by **+0.001099%**, to **0.0742186
deg/s/F3**, against the drawing's **0.0339862**. No production algorithm or
aircraft property was changed.

The diagnostic interpolates absolute Euler angles between nodes instead of
the production rotation interpolant. It is a conditional implementation of
the documented nodal charts, not evidence that native ASWING uses this
interior rule. The authoritative reference index and source catalog were
consulted. The previous [rate-only study](daedalus-rate-interpolation-20261114.md)
left this full coupled effect open.

The literal aircraft retains its 6.7 m/s, Mach 0.1 conditions, source-equation
and SEGSPL policies, live aerodynamic influence, and 108-node/82-circulation
mesh. All 2,044 dynamic states remain active. The new trim residual is
3.22644e-11; it uses no constant residual offset. Its checkpoint has a distinct
diagnostic identity and cannot silently become a production equilibrium.

| Frequency [Hz] | Yaw magnitude change | Roll magnitude change | Sideslip magnitude change | Bank magnitude change |
| ---: | ---: | ---: | ---: | ---: |
| 0.1 | −0.003006% | −0.000727% | −0.000894% | +0.001303% |
| 1.157378 | +0.001099% | −0.002814% | +0.000877% | −0.008364% |
| 1.5 | −0.002355% | +0.041971% | +0.001949% | +0.045965% |

Explicit rotation trajectories independently check interior angular velocity
and acceleration at two time-difference widths. Each accepted harmonic state
then passes complete nonlinear-residual directional checks at widths 0.002
and 0.004. The second check evaluates the identical saved candidate, not its
next correction. Maximum accepted harmonic residual is **1.95089e-11**, below
the declared 2e-11 gate; the next relative output change is below 2e-7.
The old descriptor is only a correction preconditioner, not a rank certificate
for the changed operator. Intermediate unconverged iterations are retained.

All ten capped serial jobs completed and were reaped, with unchanged inputs
during each job. The [verification receipt](../../artifacts/daedalus-euler-interpolation-20261114/verification.json)
retains both-width checks, every terminal receipt, current hashes and the two
historical input differences: earlier jobs preceded browser-copy repairs in
`bridge.py` and `frequency_sweep.py`. The numerical source files and driver
are unchanged. This receipt checks saved evidence; it does not claim those
earlier jobs were rerun against today's complete application.

[Bounded driver](../../scripts/check_daedalus_euler_interpolation.py).
Browser/build jobs remain held. ISAE counts and progress history are unchanged.
The full Bode discrepancy remains open.
