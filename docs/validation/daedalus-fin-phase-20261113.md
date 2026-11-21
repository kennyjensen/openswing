# Daedalus: fin apparent-load phase reconstruction

An independent evaluation of the published apparent-load equations reproduces
the current fin's nodal loads and global wrench at **1.157378 Hz**. No missing
or doubled frame-acceleration term was found. This closes the pending check
from the [boom-load study](daedalus-boom-drivers-20261113.md); it does not close
the Bode discrepancy. Yaw remains **0.074218 versus 0.033986 deg/s/F3**.

![Fin apparent loads by motion and equation term](../../artifacts/daedalus-fin-phase-20261113/report/fin-phase.png)

## Equations and scope

The [reference module](../../scripts/fin_apparent_reference.py) imports no
OpenSwing code. It independently evaluates section angular-rate interpolation,
stationary-base frame kinematics and Drela's unsteady Eqs. 23, 27 and 43–44
(printed pp. 7 and 9). The authoritative
[unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf)
and [source catalog](aswing-authoritative-sources.json) define the reference.
The absolute origin acceleration is reconstructed as
`i*omega*U_hat + Omega_hat × U_base`, and angular acceleration as
`i*omega*Omega_hat`; the production operating-acceleration slots are not inputs.

The loaded geometry/material data, base relative fluid velocity, harmonic
response coordinates and declared symmetric strip-wrench transfer are supplied.
This is not an independent circulation or full-aircraft solution. It checks
the accepted endpoint/SEGSPL case at 6.7 m/s, Mach 0.1, with lag and plume on.
The stationary-base restrictions are asserted. All nine previously separated
motion/control sources and their complete sum are replayed.

## Findings

Fin body-y force components in lb per native F3, with `exp(i*omega*t)`:

| Load contribution | Real | Imaginary |
| --- | ---: | ---: |
| Ordinary circulation lift | +0.106905 | −0.206313 |
| Circulation-rate lift | +0.181223 | +0.092304 |
| Apparent force | +0.037087 | −0.192547 |

The apparent force separates into:

| Apparent-load term | Real | Imaginary |
| --- | ---: | ---: |
| Local/frame angular-rate term | −0.074006 | −0.038743 |
| Frame velocity derivative | −0.008227 | +0.005210 |
| Frame convective acceleration | +0.003279 | −0.000393 |
| Frame angular acceleration | −0.002985 | −0.022264 |
| Elastic translation acceleration | +0.110580 | −0.121540 |
| Elastic rotation acceleration | +0.008446 | −0.014817 |

The intrinsic angular-inertia couple contributes moment but no force. Elastic
translation acceleration and the angular-rate term dominate the apparent
side-force decomposition. The direct rudder contribution to ordinary/rate
lift is respectively `0.437569 − 0.397043i` and `0.348288 + 0.374635i` lb/F3;
their imaginary parts substantially cancel. Fin motion then changes that
balance. None of these isolated load terms is an independently realizable
aircraft response.

| Check | Maximum absolute error |
| --- | ---: |
| Nodal apparent force | 1.431e−17 lb/F3 |
| Nodal apparent moment | 4.857e−17 lb ft/F3 |
| Global apparent wrench | 1.832e−15 in its respective units |
| Sum of motion groups versus complete load | 4.441e−16 |
| Independent frame acceleration reconstruction | 1.388e−17 |

The original gates remain 2e−6 for load comparisons, 2e−10 for superposition
and 2e−8 for frame-acceleration reconstruction. The
[replay result](../../artifacts/daedalus-fin-phase-20261113/replay/result.json),
[complete CSV](../../artifacts/daedalus-fin-phase-20261113/report/loads.csv) and
[bounded driver](../../scripts/check_daedalus_fin_phase.py) retain the evidence.
Both jobs succeeded and were reaped under one-thread/512 MiB/15 CPU-second/
25 wall-second limits. No production physics, settings or ISAE counts changed.

The original Bode drawing was visually checked again: the selected yaw minimum
near 1.157 Hz is consistent with the retained approximately 0.034 digitization.
Its legend identifies operating point 1, unit F3 and frame Omega-z; it does not
identify full versus reduced-order solution or give the operating settings.

The subsequent [wing-lift decomposition](daedalus-wing-lift-terms-20261113.md)
provides a more specific next lead: wing-root rotation contributes strongly
through the velocity-dependent part of ordinary wing lift near the yaw dip.
