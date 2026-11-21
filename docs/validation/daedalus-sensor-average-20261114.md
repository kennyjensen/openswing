# Daedalus: averaging yaw-rate sensors

**Some spatial averages produce deeper dips, but none of the tested fixed
layouts reproduces Drela's dip near 1.16 Hz.** Averaging the cabin and wing-root
sensors moves the sampled dip to 1.5 Hz. Including the two wingtips moves a much
deeper dip to approximately 2 Hz. Averages including the flexible tail are much
larger near 1 Hz, because its local yaw motion dominates.

The app now links to **Daedalus sensor-average Bode** under **Validation &
implementation scope**, at `/validation/daedalus-sensor-average/index.html`.
It includes [magnitude and phase](../../public/validation/daedalus-sensor-average/bode.png),
all eleven layouts in a downloadable CSV and exact sensor positions/weights.
These responses are calculated from attached gyros; no GIF measurements enter
this experiment. The original magnitude-only plot remains below.

![Sensor-average comparison](../../artifacts/daedalus-sensor-average-20261114/report/comparison.png)

[SVG plot](../../artifacts/daedalus-sensor-average-20261114/report/comparison.svg),
[all complex transfers and cancellation ratios](../../artifacts/daedalus-sensor-average-20261114/audit-v4/comparison.csv),
[exact sensor locations, weights and values](../../artifacts/daedalus-sensor-average-20261114/audit-v4/result.json).

## Definition and unchanged calculation

The [authoritative reference index](aswing-authoritative-references.md) and its
source catalog were consulted. Drela's unsteady description, printed p. 22,
Eq. 108, defines an attached rate gyro as the frame angular velocity plus the
local elastic angular velocity, transformed into the sensor axes. This is
implemented by `measure_sensor` in `openswing/sensors.py`.

Each diagnostic sensor is attached to an existing structural node. In the
primary comparison its axes are aligned with the body axes in the loaded base.
The aircraft has zero mean angular rate, so the linear response is the complex
sum `Omega_frame + omega_elastic` projected onto that common z direction. The
experiment averages **complex responses before taking magnitude**; it retains
phase cancellation. All weights are nonnegative and sum to one. No sensor mass,
stiffness, damping or solver parameter was added or changed.

The full 162-frequency, 1,953-state response from the existing 6.7 m/s level-flight
case is reused. These are full dynamic states, not a truncated modal model.
No new aerodynamic/structural solve was performed. This is not the user's
currently loaded result, and Drela's historical operating point remains unknown.

## Results

Magnitudes are deg/s per unit native F3. The comparison frequency is the
digitized native low-frequency minimum, **1.1573777 Hz**, with magnitude
**0.0339862 deg/s/F3**. Minima below are the lowest saved sample between
0.7 and 3 Hz, not newly refined extrema.

| Sensor layout | At 1.15738 Hz | Sampled minimum frequency | Sampled minimum magnitude |
| --- | ---: | ---: | ---: |
| Drela drawing | **0.03399** | **1.157 Hz** | **0.03399** |
| Aircraft frame, normal Bode output | 0.07385 | 1.099 Hz | 0.07331 |
| Three cabin stations | 0.07789 | 1.073 Hz | 0.07654 |
| Pilot attachment + wing root, equal weights | 0.05934 | 1.500 Hz | 0.04193 |
| Pilot attachment + wing root + both wingtips, equal weights | 0.07306 | 1.995 Hz | 0.00994 |
| Wing root + both wingtips, equal weights | 0.10195 | 2.818 Hz | 0.01471 |
| Seven locations across the aircraft | 0.43154 | — | No native-like dip near 1 Hz |
| Fifteen distributed locations | 0.73514 | — | No native-like dip near 1 Hz |
| All 103 nodes, equal weights | 0.39913 | — | No native-like dip near 1 Hz |
| Equal weight per component, length average within each | 0.69733 | — | No native-like dip near 1 Hz |

The full diagnostic also retains six centerline sensors and five component
midpoints, giving 0.69170 and 0.64190 respectively at the reference dip.
All-node equal weights depend on mesh density; the equal-component/length
average is included to make that distinction explicit.

The seven-location layout contains the pilot attachment, wing root, both
wingtips, a mid-boom node, stabilizer center and a mid-fin node. The fifteen
locations are the two ends and nearest midpoint of each of the five beams.
Locations are chosen geometrically; no phase-dependent weights or optimized
sensor positions are used. After the initial aircraft-wide averages failed,
the two-, three- and four-sensor wing/cabin layouts were added to investigate
the observed opposing wing and tail phases. They were not fitted to the target.

## Why the broad averages rise

At 1.15738 Hz, these individual common-axis gyro signals are:

| Attachment | Magnitude, deg/s/F3 | Phase, degrees |
| --- | ---: | ---: |
| Pilot / fairing | 0.07900 | -3.39 |
| Wing root | 0.08963 | -94.17 |
| Left wingtip | 0.11075 | -117.26 |
| Right wingtip | 0.11063 | -117.34 |
| Mid-boom | 0.25088 | +30.38 |
| Stabilizer center | 1.26964 | +40.37 |
| Mid-fin | 1.69167 | +30.05 |

The wing contributions partially oppose the tail, but their magnitudes are
too small to cancel it in the broad averages. Removing the tail changes both
the depth and location of the apparent antiresonance. Thus measurement choice
can strongly change the plotted dip; these results do not establish which
measurement or operating point produced Drela's drawing.

The alternative convention uses default sensor directions in the undeformed
aircraft, carried by each elastic attachment. It also fails to recover the
native dip: the two-sensor cabin/wing-root average is 0.059336 and the four-sensor
wing/cabin average is 0.089319 at 1.15738 Hz. All values for both conventions
are retained in the diagnostic JSON.

## Verification and limits

- Both gyro-axis conventions were checked against the actual production
  `measure_sensor` function at all 103 nodes, at 1 Hz and 1.15738 Hz. The maximum
  complex-vector difference is **1.341e-13 rad/s/F3**.
- The frame component agrees with the pre-existing Bode output at every one of
  the 162 frequencies. Saved-state source checksums are retained.
- No weights were fitted, and no production Bode output was replaced by an
  average. This experiment does not establish native ASWING agreement.
- Each numerical diagnostic was a small serial job with one BLAS thread,
  512 MiB address-space / 15 CPU-second / 25 wall-second limits. The final
  audit took **2.55 CPU seconds**, with **90,748 KiB peak RSS**, and was reaped.
  The plot job took 2.30 CPU seconds / 82,292 KiB. No solver is left running.
- An initial filename lookup failed before a worker was spawned because
  refined states use explicit 17-digit filenames. The driver now uses each
  record's declared filename; the failed attempt and successive diagnostic
  snapshots are retained.
- No ISAE completion fraction or scope changed; no Node, browser, build or
  WASM job was started.

[Audit driver](../../scripts/check_daedalus_sensor_average.py),
[plot driver](../../scripts/report_daedalus_sensor_average.py),
[final audit receipt](../../artifacts/daedalus-sensor-average-20261114/audit-v4/terminal.json),
[plot receipt](../../artifacts/daedalus-sensor-average-20261114/report/terminal.json).

The subsequent [magnitude/phase report](../../scripts/report_daedalus_sensor_bode.py)
checks that every exported magnitude/phase reconstructs its saved complex
response. Its bounded job took 2.13 CPU seconds / 89,116 KiB RSS and was reaped.
The [publisher](../../scripts/publish-daedalus-sensor-bode.py) copies this saved
report to the app; neither step reruns dynamics. Both plots were visually
inspected. The new static app link requires a manual refresh because automatic
reloads remain disabled. This is not a full browser-rendering test.
