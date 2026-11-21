# Daedalus wing motion: independent roll-load derivative check

**The wing translation-velocity load derivatives agree with the published
force equations at both checked operating states.** All 153 wing velocity
coordinates were checked against all six global force/moment rows: 918 matrix
entries per state. The largest absolute difference in normalized matrix entries
is 1.203e-17. This supports these specific derivatives; it does not validate the
complete coupled response or resolve the published Bode mismatch.

The earlier response-difference diagnostic identified a large contribution
from changes in the global roll equation's wing-local-velocity columns. The
new check identifies its physical origin: **ordinary circulation lift reacting
to fore-and-aft wing motion**. The difference between the two saved states is
almost entirely their different bound circulation, rather than their geometry
or a newly discovered derivative error. No production equations were changed.

## Source equations and scope

The [authoritative index](aswing-authoritative-references.md) and
[checksummed source catalog](aswing-authoritative-sources.json) identify:

- Drela's [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
  printed p. 8, Eqs. 30–36: bound-vortex relative velocity and ordinary/unsteady
  circulation lift and moment.
- Drela's [steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
  printed pp. 16–17, Eqs. 67, 69–74: lift, profile drag, and section pitching
  moment, including its normal-Mach correction.
- Unsteady printed pp. 9–10, Eqs. 38–44: real and apparent inertia. With zero
  mean frame/local angular velocities, the partial derivatives of these terms
  with respect to local translation velocity are zero. Their acceleration
  derivatives remain in the mass matrix and are outside this check.

Hold geometry, circulation, control inputs, local angular velocity and all
accelerations fixed. For a section translation-velocity increment `du`,
the relative-airflow increment is `dV = -du`. The ordinary lift derivative is

`dF = -rho * Gamma * ds * (du × s_hat)`.

Its moment about the reference point is `r_quarter × dF`. For an approximately
straight spanwise wing, forward motion reduces lift, so antisymmetric forward
motion of the two halves produces a rolling moment. This contribution scales
directly with the existing circulation; it is present even while the
circulation perturbation itself is held fixed.

The checker separately differentiates skin-friction drag, pressure drag,
stall-leakage drag and section pitching moment analytically. It reconstructs
section geometry from endpoint poses using the existing independent geometry
evaluator, and uses independently integrated vortex/volume/jet fields for the
base relative velocity. Parsed material values and the declared Glauert
sampling/source wrench-transfer policy are accepted inputs. No production
force derivative is used as an expected value.

The compared cases use the same literal `dae.asw`, redistributed mesh and
6.7 m/s speed:

1. The existing trimmed level-flight state.
2. The existing [pitch-balanced zero-incidence diagnostic](daedalus-pitch-balanced-base-20261114.md).
   This state has nonzero acceleration and is **not** an alternative steady
   flight condition or a recovered native operating point. No new trim or
   operating-point search was run.

For independent airflow evaluation only, the second state's mean accelerations
are set to zero in a copy: they do not enter relative velocity. Its zero-power
type-0 engine is omitted from that copy because the separate jet reference
supports positive thrust only. Zero power gives exactly zero thrust, torque
and plume. Actual masses, the original state, and the compared matrix are
preserved. The copied field evaluator is not used to claim agreement of the
accelerating state's complete loads.

## Results

| Check | Level flight | Pitch-balanced diagnostic |
| --- | ---: | ---: |
| Matrix entries compared | 918 | 918 |
| Maximum normalized entry difference | 1.202e-17 | 5.638e-18 |
| Relative matrix Frobenius-norm difference | 6.549e-16 | 5.447e-16 |
| Maximum base relative-airflow difference, ft/s | 6.462e-14 | 9.243e-15 |

At 1.1573777 Hz, the contribution of the **local wing translation-velocity
terms alone** to global roll moment has these magnitudes, in lb ft per F3:

| Term | Level flight | Pitch-balanced diagnostic |
| --- | ---: | ---: |
| Ordinary lift | 19.4887 | 13.6242 |
| Skin drag | 0.01200 | 0.01627 |
| Pressure drag | 0.00874 | 0.01191 |
| Stall drag | 0.00000221 | 0.000000000702 |
| Section pitching moment | 0.00733 | 0.00654 |
| Complex sum of these terms | 19.4674 | 13.5936 |

These are partial load contributions, not the net aircraft roll moment or
angular-rate amplitudes. Magnitudes do not add. In level flight, the same
partial separated by local velocity axis gives 19.4950 from x, 0.01393 from y
and 0.01927 from z. Thus the dominant motion here is fore-and-aft, not vertical.

To distinguish loading from geometry, write the ordinary-lift derivative as
`Gamma * G`, where `G` contains length, span direction and moment arm. The
exact symmetric identity

`delta(Gamma * G) = delta(Gamma) * mean(G) + mean(Gamma) * delta(G)`

separates the two changes without choosing a fitted multiplier. Applied to
either saved complex velocity response, circulation accounts for about
**100.60%** of the change along that change's complex direction; geometry
accounts for **−0.76%** and other terms total about **+0.17%**. These signed
projections sum to 100%; they are not error percentages or fractions of the
complete response. Integrated wing circulation falls by **27.14%** between
the two states. This explains why that matrix block changes; it does not
establish which circulation or trim produced Drela's drawing.

## Evidence and limitations

[Analytic checker](../../scripts/check_daedalus_wing_velocity.py),
[product-decomposition checker](../../scripts/report_daedalus_wing_velocity.py),
[complete results](../../artifacts/daedalus-wing-velocity-20261114/report/result.json).
Individual runs retain input hashes, immutable driver snapshots, numerical
arrays and terminal receipts.

The initial second-case check stopped at the independent reference's
positive-thrust guard. Its failed record is retained. The explicit inactive
engine adapter described above allowed the check to complete. Three successful
jobs and that failed job were serial, used one BLAS thread, and were all reaped.
Each stayed below 2.91 CPU seconds and 94,604 KiB peak RSS, under the existing
512 MiB / 15 CPU-second / 25 wall-second limits.

No new Bode solves, GIF measurements, browser/Node/build/WASM jobs, production
physics changes, or ISAE completion/scope changes were made. The requested
[sensor-average Bode experiment](daedalus-sensor-average-20261114.md) remains
available in the app as a separate measurement diagnostic.
