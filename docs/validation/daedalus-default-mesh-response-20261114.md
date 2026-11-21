# Daedalus response on the new app mesh

The requested GIF-like mesh has a fresh, converged level-flight solution, but
does **not** resolve the published yaw-rate dip. At 1.157377737 Hz its magnitude
is **0.0737970 deg/s/F3**, versus **0.0742178** on the previous comparison mesh
and **0.0339862** in Drela's drawing. The mesh change is −0.5669%; the remaining
drawing error is +117.14%.

![Three sampled frequencies on the new mesh, previous comparison curve and Drela drawing](../../artifacts/daedalus-default-mesh-response-20261114/report/comparison.png)

[SVG plot](../../artifacts/daedalus-default-mesh-response-20261114/report/comparison.svg),
[all four outputs in CSV](../../artifacts/daedalus-default-mesh-response-20261114/report/comparison.csv).
Orange markers are the three newly solved points, not a full new sweep.

## Conditions and mesh

This comparison uses literal `dae.asw`, source structural equations, SEGSPL,
6.7 m/s, Mach 0.1, live influence geometry, unsteady circulation and propeller
plume. Seven trim conditions establish zero net force/moment and zero flight
path; six flight-frame load equations are released for the response. The input
is the file's native F3 rudder control. No aircraft parameter or response
amplitude is fitted to the reference.

The new uniform per-component app mesh has **112 nodes, 107 intervals,
86 circulation coordinates and 2,120 dynamic states**. The previous comparison
mesh has 108 nodes, 103 intervals and 2,044 states. It is not the old app's
48-intervals-per-beam default, which had 261 actual intervals. Both distinctions
matter when interpreting the changes below. The new mesh's exact counts and
fresh-import behavior are documented [separately](daedalus-default-mesh-20261114.md).

An interpolation of the previous solution is used only as an initial guess.
Its scaled equation defect is 0.06318, so it is explicitly rejected as a solved
state. All new trim derivative columns are rebuilt and directionally checked.
A sparse inverse-norm rank certificate gives a reciprocal-condition lower
bound of 3.747e-8. Full nonlinear correction then converges to a maximum scaled
residual of **2.291e-11**, without offsets or weakened tolerances.

The fresh solution has zero flight path to roundoff, airspeed 21.98163 ft/s,
and wing tips **8.10770 / 8.11215 ft** above the loaded root. The mesh's mass
quadrature gives **232.5360 lb**, versus 233.3019 lb on the prior comparison
mesh, with unchanged mass input tables. Angle of attack is 3.08638°, elevator
F2 is −8.82559, rudder F3 is 0.0183881 and engine control is 6.00106. This is
the declared comparison condition, not an identification of native Op.Point 1.

## What changed in the response

| Frequency [Hz] | Previous comparison yaw | New mesh yaw | Drela drawing | New error |
| --- | ---: | ---: | ---: | ---: |
| 0.1 | 0.121763 | 0.119052 | 0.118238 | +0.69% |
| 1.157377737 | 0.074218 | 0.073797 | 0.033986 | +117.14% |
| 1.5 | 0.094316 | 0.093804 | 0.081818 | +14.65% |

Yaw units are degrees/second per native F3 unit. Across the twelve sampled
output magnitudes, the largest change from the prior coarse comparison is
**−20.82% in roll rate at 1.5 Hz**; bank there changes −17.38%. Thus small yaw
changes do not establish mesh independence of every channel. Relative to the
previous independently refined 211-node mesh, those same changes are −5.84%
and −4.34%, respectively, and yaw at the dip differs by −0.35%. That older
refinement is a separate mesh family, not a convergence certificate for this
new preset. Its saved numerical values and checksum are retained in the
[verification record](../../artifacts/daedalus-default-mesh-response-20261114/verification.json).

## Numerical checks

All dynamic derivative columns and the mass/input/output maps are rebuilt at
the accepted base. Three independent complete-equation directional checks
give maximum relative error **1.840e-11** across state and rate derivatives.
The three complete harmonic solves use exact beam/kinematic elimination:
2,120 total states and a 776-dimensional frequency factor, with no modal
truncation. Reciprocal condition estimates exceed 1.8e-8.

Six additional checks apply fourth-order differences of the *full nonlinear
residual* to the actual complex responses at widths 0.002 and 0.004. The
largest complete harmonic defect is **5.324e-12**. These checks support the
solutions of the declared discrete equations; they do not establish matching
native conditions, continuum convergence, or all-frequency agreement.

All **26 successful bounded jobs** completed and were reaped. Maximum resident
memory was 134,484 KiB; maximum CPU time was 13.939 seconds, within the 15-second
limit. An initial reporting audit stopped because it read the steady flag at
the wrong nesting level; its corrected successor passed. Both receipts remain.
No browser/build or background solver job ran. No production physics, default
mesh setting, ISAE fraction or progress history changed in this follow-up.

[Trim state](../../artifacts/daedalus-default-mesh-response-20261114/trim-1/state.json),
[full response](../../artifacts/daedalus-default-mesh-response-20261114/response/result.json),
[independent residual audit](../../artifacts/daedalus-default-mesh-response-20261114/audit-v2/result.json),
[assembly driver](../../scripts/check_daedalus_default_mesh_response.py),
[audit/report driver](../../scripts/report_daedalus_default_mesh_response.py).
