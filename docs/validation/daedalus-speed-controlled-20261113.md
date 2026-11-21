# Daedalus: current-solver speed and frozen-influence comparisons

**The Bode curves still do not agree.** A fresh, fully retrimmed five-speed
comparison gives the best overall match at **6.7 m/s**. Increasing speed deepens
the yaw notch, but shifts it toward **1 Hz**, below the drawing's approximately
**1.157 Hz**, and worsens the low-frequency responses. A separate check with
frozen influence coefficients also leaves the notch much too shallow.

This narrows the investigation: the difference is not explained by any of the
tested speeds, or by the fast/slow influence setting at 6.7 m/s. It does **not**
identify Drela's original operating point or establish native ASWING validation.
No production equations, aircraft properties, defaults, input gains, acceptance
tolerances or ISAE pass counts changed.

## Four-output speed sweep

![Five speeds compared with the four published curves](../../artifacts/daedalus-speed-20261113/report/four-output-speed.png)

[Vector plot](../../artifacts/daedalus-speed-20261113/report/four-output-speed.svg),
[all complex outputs and magnitude errors](../../artifacts/daedalus-speed-20261113/report/comparison.csv),
[machine-readable report](../../artifacts/daedalus-speed-20261113/report/result.json).

All values below are yaw magnitude in degrees/second per native F3 unit.
The comparison at **1.157377737 Hz** uses the drawing's dip frequency, so a
computed minimum at a different frequency cannot masquerade as agreement.

| Speed, m/s | Yaw at 0.1 Hz | Error at 0.1 Hz | Yaw at drawing's dip frequency | Error there | Sampled local-minimum frequency, Hz |
| --- | ---: | ---: | ---: | ---: | ---: |
| Drela drawing | 0.118238 | — | 0.0339862 | — | 1.15738 |
| 6.0 | 0.0386932 | −67.3% | 0.121428 | +257.3% | 1.995* |
| **6.7** | **0.121445** | **+2.71%** | **0.0737892** | **+117.1%** | **1.100** |
| 7.5 | 0.187428 | +58.5% | 0.0610198 | +79.5% | 1.07978 |
| 8.25 | 0.264972 | +124.1% | 0.0544429 | +60.2% | 1.000 |
| 9.144 (30 ft/s) | 0.377091 | +218.9% | 0.0523611 | +54.1% | 1.000 |

The minima are sampled within 0.6–2 Hz, not optimized continuous-frequency
extrema. `*` The 6 m/s minimum is at the upper sampled boundary and does not
represent a resolved notch in that window. At 9.144 m/s the sampled minimum
itself is 0.0275481, but its location is wrong and its low-frequency yaw is
more than three times the reference. Matching one minimum's depth would not
match the published transfer function.

The combined score weights yaw, roll, sideslip and bank equally over the
61 uniformly log-spaced frequencies. It is the RMS of
`20 log10(computed magnitude / drawing magnitude)`; smaller is better.
The four extra feature samples are included in the ±5% counts but excluded
from this uniformly weighted score.

| Speed, m/s | Four-output RMS error, dB | Magnitudes within ±5% |
| --- | ---: | ---: |
| 6.0 | 4.272 | 36/260 |
| **6.7** | **2.400** | **85/260** |
| 7.5 | 3.049 | 9/260 |
| 8.25 | 4.428 | 7/260 |
| 9.144 | 6.379 | 3/260 |

These counts describe this digitized magnitude comparison. They are not new
ISAE tests or proof that a complete aircraft response has passed. The current
6.7 m/s median absolute relative errors are **11.34% yaw, 13.03% roll,
4.93% sideslip and 20.35% bank**. Relative errors are especially sensitive
near response cancellations; the plots and CSV retain absolute magnitudes.

## Separate frozen-influence check

![Frozen and unfrozen 6.7 m/s cases](../../artifacts/daedalus-frozen-20261113/report/four-output-speed.png)

[Vector plot](../../artifacts/daedalus-frozen-20261113/report/four-output-speed.svg),
[CSV](../../artifacts/daedalus-frozen-20261113/report/comparison.csv),
[machine-readable report](../../artifacts/daedalus-frozen-20261113/report/result.json).

The speed sweep deliberately retained the earlier comparison's **unfrozen**
influences. This separate case changes only that setting to **frozen**, then
solves a fresh trim and rebuilds all matrices. Frozen influences are already
the OpenSwing default adopted at the user's request. Drela describes the
fast/slow distinction in the [original manual](../../reference/aswing_doc.txt),
under “Fast,Slow Vortex-Lattice Model”: fast holds influence coefficients at
undeformed geometry and zero alpha/beta; slow updates them with the geometry
and wind direction.

| 6.7 m/s setting | Yaw at 0.1 Hz | Error | Yaw at 1.15738 Hz | Error | Four-output RMS error | Within ±5% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unfrozen | 0.121445 | +2.71% | 0.0737892 | +117.1% | 2.400 dB | 85/260 |
| Frozen | 0.119283 | +0.88% | 0.0753718 | +121.8% | 2.495 dB | 63/260 |

Freezing improves the lowest-frequency yaw magnitude slightly, but makes the
notch a little shallower. The roll and bank curves retain an excessively deep
cancellation around 1–1.6 Hz. The switch does not resolve the coupled shape
discrepancy. This check does not justify changing the default back to unfrozen.

## Fixed setup and reference provenance

The [authoritative reference index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) were consulted.
The target is Drela's [rudder Bode PDF](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf),
also retained as [a local PDF](../../reference/drela-rudder-bode-20261113.pdf).
Only the `reference_drawing_magnitude` column of the existing
[four-output digitization](daedalus-rudder-four-outputs.csv) supplies reference
ordinates; neither historical OpenSwing curve is used as truth. Interpolation
between digitized reference points is linear in log-frequency/log-magnitude.

The official [ASWING page](https://web.mit.edu/drela/Public/web/aswing/) and
its animations identify operating point 1 and qualitatively demonstrate the
boom-compliance effect. They do not supply the operating-point speed or the
original saved settings. The previously cited 6.7 m/s design cruise speed
remains a plausible candidate, not an authenticated Bode operating point.
Reference phase is unavailable.

All six new cases use:

- The literal [dae.asw](../../examples/dae.asw). The public project's source
  was checked to be byte-identical to that file.
- One identical, pinned set of current `openswing/*.py` sources. Historical
  physical fields serve only as a starting guess; no historical A/M matrix
  supplies a prediction in this study.
- The corrected **physical-breaks-v1** C16 mesh: **108 nodes, 103 elements,
  82 circulation unknowns and 2,044 dynamic coordinates**. This explicitly
  preserves the earlier comparison mesh; it is not relabeled as the newer
  default mesh recipe.
- The existing **midpoint** structural operator, reference density 0.002378
  in model units, fixed PG **Mach 0.1**, aerodynamic lag enabled, unchanged
  stall settings, literal mass/stiffness distributions and no material damping.
  Mach is an explicit fixed comparison setting, not the automatic Mach for
  flight at 6.7 m/s. The optional published-equation structural operator is
  not silently substituted.
- Seven steady-level trim constraints solving alpha, beta, bank, elevation,
  elevator F2, rudder F3 and engine setting P1 for six zero net loads and
  zero flight-path angle. Free-flight dynamics then release six frame
  acceleration variables; trim controls remain fixed apart from the F3 forcing.
- **65 frequencies per case**: 61 log-spaced points from 0.1 to 10 Hz, plus
  0.2, 1.1, 1.15737773741517 and 1.3 Hz. Angular frequency is `2*pi*f`.
  Outputs convert radians to degrees once; the native F3 input has no extra
  degrees/radians gain conversion.

High-frequency mesh convergence remains open. This C16 study isolates speed
and the influence setting; it cannot establish mesh independence or exact
agreement with an unknown original aircraft discretization/version.

## Numerical and resource checks

[The serial runner](../../scripts/check_daedalus_speed.py) checkpoints trim,
geometry columns, remaining state derivatives, mass/input/output matrices and
frequency batches. Each stage has an immutable plan, runner snapshot, output
and terminal receipt. Study plans pin the current physics sources, literal
aircraft, project and reference digitization before computation:
[speed plan](../../artifacts/daedalus-speed-20261113/study-plan.json),
[frozen plan](../../artifacts/daedalus-frozen-20261113/study-plan.json).

The trim driver reuses the production canonical force/moment geometry blocks,
reorders those rows for the seven trim equations and independently differences
all seven trim controls. Full-residual directional checks verify that assembly.
Every final trim also receives a fresh tangent-rank certificate; final maximum
residuals range from **4.16e-14 to 3.20e-10**, below the **1e-9** gate.

Complete A/M matrices were checked against independent full-residual probes
in three mixed-coordinate directions per case. Maximum relative discrepancies
were **5.78e-10** for state derivatives and **2.23e-11** for rate derivatives.
These verify the staged assembly in the checked directions, not native
ASWING physics or every matrix column individually.

All **390/390 harmonic solves** pass the unchanged full-equation checks.
Maximum scaled residual is **3.35e-17**; minimum estimated reciprocal
condition is **7.10e-9**, above the **1e-12** rejection gate. The production
exact beam elimination retains every entry and restores the complete response;
no modal truncation or small-entry cutoff was introduced.

Four failed attempts are retained, not overwritten or counted as successes:

- The combined 6.7 m/s linearization reached the **15 CPU-second** cap;
  subsequent jobs split the same derivative construction into stages.
- Two full-LU response attempts hit the **512 MiB address-space** allocation
  limit. The existing exact beam elimination made the solves fit.
- At 8.25 m/s the fast geometry derivative declined a perturbation crossing a
  powered-jet boundary. All **648** geometry columns were recomputed using the
  production fourth-order full-residual fallback in batches of at most 64.
  The resulting full matrix passed the independent directional checks.

Every child and parent numerical invocation completed or was terminated and
reaped. Successful jobs used at most **14.313 CPU seconds, 16.467 wall seconds
and 168.4 MiB peak RSS**. One BLAS thread and the original **512 MiB /15 CPU
/25 wall-second** limits remained in force. No background solver, browser,
Node/build job or extra watcher was started.

## What remains

The completed sweep rules out a simple speed choice among these five cases;
the additional frozen-influence run rules out that switch at 6.7 m/s. Neither
establishes that all dynamics or aerodynamic equations agree with ASWING.

The remaining useful comparison is the coupled response near **0.7–1.6 Hz**:
why the predicted yaw cancellation is too weak while the roll/bank cancellation
is too strong. The next physics audit should quantify the relative phase and
gain of fin aerodynamic loading, boom bending and frame motion against Drela's
unsteady formulation, and keep the midpoint versus published-equation structural
discretization distinction explicit. These are investigation targets, not a
diagnosed root cause. The independent [boom-mechanics audit](daedalus-tailboom-20261113.md)
supports the implemented beam mechanics but does not settle those coupled terms.
