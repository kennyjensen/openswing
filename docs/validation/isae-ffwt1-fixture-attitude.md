# FFWT-1 fixture attitude and archived model checks

Updated 2026-10-15. Four paired calculations show that fixture attitude changes
fold equilibrium and computed loads. The tilted-fixture model reduces the
high-incidence lift deficit, but increases disagreement in sensor bank, local
flow angle and root bending moment. It does **not** reconcile the archived
ASWING results. ISAE coverage remains **17 partial / 24 pending / 0 fully
validated**, with FFWT-1 pending.

## Physical setup being tested

[Healy's primary thesis](https://research-information.bris.ac.uk/ws/portalfiles/portal/388426634/Final_Copy_2024_01_23_Healy_F_PhD_Redacted.pdf),
printed pages 191–192 (PDF pages 225–226), describes changing model incidence
with an overhead balance and a rear strut. Under a declared horizontal,
uniform tunnel-flow assumption, changing incidence also changes the direction
of gravity in wing/body coordinates.

The previous archived comparison kept the body level and varied body-relative
airflow incidence. This study compares that condition with body elevation equal
to incidence. Both retain the reconstructed rigid Flare30 model, 22 m/s,
zero sideslip, the source atmosphere, 100/40/40 requested intervals, unchanged
section properties and frozen aerodynamic influences. The tilted case uses

`gravity_body = g [sin(alpha), 0, -cos(alpha)]`.

An explicit rotation check makes the freestream horizontal in Earth coordinates.
At each original pose and supplied circulation, the two attitudes give exactly
the same aerodynamic force and moment. Their gravity torques differ. Four new
two-hinge roots then balance aerodynamics, gravity and the literal spring laws.
Each starts from the corresponding earlier computed root; archived angles and
loads do not initialize or calibrate the calculation.

This is a controlled comparison of two rigid setups. The physical inner wing
is flexible, its spatial flow field remains unmatched, and the archived
executable's actual attitude is unrecorded. Setting elevation equal to requested
incidence is conditional on the uniform horizontal-flow assumption.

## Paired equilibria

| Requested incidence | Level-body Lift | Tilted-fixture Lift | Change in port physical fold |
| --- | ---: | ---: | ---: |
| −18.094708° | −16.91064724 N | −16.80863553 N | −0.407919° |
| −0.169321° | 1.92644843 N | 1.92704237 N | −0.002948° |
| +8.779176° | 14.41512035 N | 14.42313264 N | −0.038733° |
| +30.263890° | 19.90208138 N | 20.06166530 N | −0.643988° |

All four new equilibria meet the unchanged normalized circulation requirement
of 1e−12 and hinge-torque requirement of 1e−12 N m. The run retains 47 evaluations
and eight additional supplied-circulation sensor evaluations. The timed native
study body takes 11.59 seconds; this is a reduced rigid-fixture calculation,
not a full-network or browser benchmark.

An independent saved-data review passes 180 mechanical and sensor checks across
the eight level/inclined states. It reconstructs gravity, spring and aerodynamic
moments and distinguishes body-relative and Earth-relative sensor orientations.

The high-incidence comparison shows why a lift improvement is insufficient:

| Observable at 30.263890° | Archived ASWING | Level body | Tilted fixture |
| --- | ---: | ---: | ---: |
| Lift | 20.753400 N | 19.902081 N | 20.061665 N |
| Port sensor Earth bank | 46.294700° | 46.106584° | 40.656742° |
| Port local full-flow incidence | 0.578309° | 0.613904° | 1.056517° |
| Root `Mc′`, left trace | 1.087180 N m | 1.037261 N m | 1.183393 N m |
| Root `Mc′`, right trace | same archived column | 1.037227 N m | 1.183343 N m |

The archived sensor's root-cut side is unknown, so both moment traces remain
visible. Neither is selected according to agreement. For the tilted endpoint,
port physical fold is 49.555048° and body-relative sensor bank is 45.453392°;
both differ from its Earth bank. These quantities must not be interchanged.
The remaining lift deficit is 0.691735 N, about 3.33% of archived lift, while
Earth-bank disagreement grows to 5.637958° and root-moment disagreement changes
sign and increases in magnitude.

## Additional archive constraints

The source audit verifies 110 archived files and examines five FFWT-1 model
tables and 30 launch scripts. It identifies several useful distinctions:

- All five examined main-wing section limits are ±1.15. The two twist variants
  also change the starboard tip limit from ±1.1 to ±1.4, so they are not pure
  twist changes. No alternative main-wing limit was recovered.
- A second `FFWT_Flare30.asw` under the archived FFWT-4-U case has the same
  aerodynamic properties but finite main-wing stiffness and distributed mass.
  The scripts use relative filenames, and their producing working directory is
  unrecorded. This is a distinct available model, not proof of a file mix-up.
- The final high-incidence point explicitly receives anchored defaults. Earlier
  points retain additional constraint-propagation uncertainty. Unrecorded
  parameter values and convergence remain limitations for every point.
- Plot export dates do not establish the model bytes or settings that generated
  the numerical tables.

Saved-load diagnostics locate most computed high-incidence lift on the main
wing. A conditional lift/moment difference estimate suggests an inboard load
difference; it cannot identify a unique cause without matched attitude, gravity
and force direction. The numerical representation of circulation and the
separately archived flexible-main model remain useful discriminating checks.
Changing section limits merely to reduce the discrepancy is not justified.

## Evidence and remaining work

The [recorded comparison](isae-ffwt1-fixture-attitude.json),
[selected evidence](isae-ffwt1-fixture-attitude-evidence.zip) and
[extraction verification](isae-ffwt1-fixture-attitude-evidence.json) retain the
declared contract, source observations, paired states and independent reviews.
A pre-execution review caught a level-gravity restriction in the earlier
validation postprocessor. A new scoped helper handles arbitrary uniform body
gravity for main and tip weights; the original helper and rejected draft remain
preserved. Production solver source and defaults are unchanged.

The archived lift discrepancy, exact producing setup, flexible-fixture and
spatial-flow matching, updated-influence limitations and dynamic validation
remain open. No original ASWING executable is available.
