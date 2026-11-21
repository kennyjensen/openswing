# Daedalus: attachment gyros versus the frame response

Local motion does not explain the missing yaw attenuation at the reference
dip for any of the predefined attachment stations checked here. Every local
yaw-rate magnitude is larger than the literal frame value. The current frame
response remains **0.074218 versus 0.033986 deg/s/F3** in the drawing at
1.157378 Hz. No production equations, operating point, output definition or
aircraft properties changed.

## Definition and scope

Drela's [unsteady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed pages 19–22, distinguishes frame angular velocity from an attached
gyro. Equations 95–98 rotate the sensor axes with the beam; Eq. 108 gives
the gyro's frame-plus-local angular velocity. Eq. 114 gives the sensor bank
angle. At the literal Ground attachment, deformation and relative motion
vanish. The published frame Ωz must therefore remain distinct from a gyro on
the flexible tail.

Ten stations were specified before evaluating the response: ground, pilot,
fairing top, both sides of each wing/stabilizer/fin rigid joint, and the boom
side of the fairing joint. Sensors have zero offset and originally body-aligned
axes, which follow attachment deformation. Rigid-joint pairs give equal
responses and are combined in the table below. No station, orientation,
output combination or physical parameter was fitted.

| Station | Yaw rate at 0.2 Hz | Yaw rate at 1.157378 Hz | Roll rate at 1.157378 Hz | Bank at 1.157378 Hz |
| --- | ---: | ---: | ---: | ---: |
| Literal frame / ground | 0.172164 | 0.074218 | 0.024219 | 0.003092 |
| Pilot attachment | 0.171626 | 0.079511 | 0.027008 | 0.003424 |
| Fairing top / boom | 0.171394 | 0.081516 | 0.034385 | 0.004379 |
| Wing root / boom | 0.175267 | 0.089826 | 0.072780 | 0.010388 |
| Stabilizer root / boom | 0.226379 | 1.269100 | 0.254431 | 0.021101 |
| Fin root / boom | 0.235508 | 1.365281 | 0.294247 | 0.025423 |

Rates are deg/s/F3; bank is deg/F3. These are magnitudes of complex linear
responses, not finite step histories. Tail flexure substantially changes what
a local gyro measures. It increases the yaw magnitude at this frequency,
so using that observable would worsen the comparison. The large tail motion
is consistent with a flexible response, but its magnitude is not independently
validated by this sensor check.

## Independent checks and evidence

The [bounded driver](../../scripts/check_daedalus_local_rates.py) reconstructs
the accepted equilibrium and forms local output maps independently from the
printed rotation products. It reuses the two saved complete 2,044-coordinate
responses; there are no new harmonic solves or aerodynamic residual
evaluations. Both saved states still satisfy the unchanged descriptor, with
maximum absolute residual **1.041e−16**.

The independent maps agree with the actual nonlinear sensor API differentiated
at two stencil widths. Across 320 sensor evaluations, maximum absolute output
error is **4.270e−14** in display units; changing stencil width changes the
result by at most **4.399e−14**. Independently differentiating the Earth-oriented
sensor triad recovers the gyro rate within **4.907e−18 rad/s/F3**. Ground outputs
exactly reproduce the saved frame maps, and rigid-joint pairs agree within
**2.221e−16** in display units.

The accepted [capture-v2 result](../../artifacts/daedalus-local-rates-20261114/capture-v2/result.json)
retains all locations and checks. Its fixture and compressed arrays retain
the maps, complex responses, separate frame/elastic contributions and physical
axes. The initial `capture` completed the numerical assertions but failed
while serializing a NumPy Ground record; its incomplete output is retained
and superseded. `capture-v2` corrects only that diagnostic serialization.
Both bounded children were reaped, with no timeout. The
[verification receipt](../../artifacts/daedalus-local-rates-20261114/verification.json)
checks input pins, archived runners and unchanged production files.

This is a two-frequency check, not a complete local-sensor Bode sweep or a
search over arbitrary locations. Local sideslip/airflow, alternative aircraft
grounding and other axis choices are not substituted. The driver's optional
sweep stage has not been run. No ISAE fraction or progress scope changed.

The [wing-load paper comparison](daedalus-wing-paper-20261113.md) supplies
separate evidence for the steady loaded wing. Its agreement does not establish
the operating settings of the later full-aircraft Bode drawing. That match
remains open.
