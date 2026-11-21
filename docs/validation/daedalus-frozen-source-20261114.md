# Daedalus: source-equation frozen-influence default and plume direction

The documented K/F fast setting still does not reproduce Drela's rudder Bode
curves. At 1.157378 Hz, the freshly trimmed frozen case gives **0.0756733
deg/s per F3**, versus **0.0339862** in the published drawing. This investigation
also found and fixed a separate production error: the propulsive plume did not
follow the aircraft x-axis when influence freezing was enabled.

![Published, live and corrected frozen responses](../../artifacts/daedalus-frozen-source-20261114/report/comparison.png)

## Source and production correction

The [reference index](aswing-authoritative-references.md) and its checksummed
catalog were consulted. The official [user manual, Engine jet](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
retained at [reference/aswing_doc.txt](../../reference/aswing_doc.txt), explicitly
puts the plume along the trailing-vortex direction: freestream in slow mode,
aircraft x-axis in fast mode. The OPER K/F setting controls this choice. The
manual's displayed default freezes the vortex-lattice matrices. The steady
technical description, section 4.6, printed p. 36, describes the simplified
influence coefficients evaluated with jig geometry and zero wind angles.

OpenSwing previously used the freestream direction for the plume in both modes.
The correction routes the selected wake direction through surface, body,
shoulder, point-drag, sensor and survey evaluations and the corresponding
geometry, circulation, power and gust derivatives. The velocity increment still
follows the actual propeller thrust axis; engine inflow still uses the actual
aircraft flow. These are distinct from the plume centerline direction.

Six production modules differ from their [archived originals](../../artifacts/daedalus-frozen-source-20261114/pre-change/receipt.json):
`aero.py`, `geometry_tangent.py`, `circulation_tangent.py`, `power_tangent.py`,
`gust_tangent.py` and the explanatory comment in `propulsion.py`. No mass,
stiffness, airfoil, control gain or acceptance tolerance was fitted.

The new [plume regression](../../tests/test_frozen_plume.py) probes points down
the aircraft x-axis and down the wind direction at nonzero alpha and beta.
It independently checks plume presence, thrust-axis velocity, sensor readings
and point drag. Before the fix, fast mode fails and slow mode passes. Both pass
afterward. Eight additional selected derivative/load cases pass, making **10
passing focused tests** after the fix. The old failure is retained as evidence.

## Fresh equilibrium and complete response

The physical fields from the accepted live-influence equilibrium were used
only as an initial guess. A fresh frozen-influence trim reduces the full scaled
residual from 0.00614234 to **7.94562e-11**, with the unchanged 1e-9 acceptance
gate. Speed is 6.7 m/s, Mach 0.1, with lag and plume enabled. The literal public
aircraft, SEGSPL interpolation, source airflow equations, physical node breaks,
bilateral braces, gravity and released-frame constraints are retained.

The trim uses 108 nodes, 103 structural intervals and 82 circulation states.
Alpha is 3.146159 degrees, beta 0.01586144 degrees, elevator F2 -10.27085,
rudder F3 0.04274656 and engine setting 6.227042. The source/SEGSPL option is
explicit: this is not a claim that the ordinary browser default selects it.

The assembled descriptor retains all **2,044 states**. Exact elimination gives
a 748-dimensional factor without a modal truncation. Three random complete
state/rate residual checks give maximum relative discrepancies of **2.926e-12**
and **1.902e-11**, respectively. The circulation, local-rate and mass blocks
remain production derivatives.

Two accelerated geometry batches correctly refused stencils that crossed a
powered-jet region boundary. Those failed attempts remain recorded. Their 32
columns were recomputed with complete fourth-order residual stencils at two
step sizes, preserving the existing 2e-5 agreement gate. The largest observed
halved-step discrepancy is **1.427e-9**. All 648 pose columns are covered exactly
once in the accepted assembly; no branch guard was disabled.

All 65 frequencies from 0.1 to 10 cycles/s were solved in serial batches of at
most eight. The minimum estimated reciprocal condition is **1.386e-8**, the
maximum scaled harmonic residual **1.196e-17** and maximum backward error
**4.328e-20**. The full nonlinear residual independently checks the saved
frozen harmonic states at 0.1 Hz and 1.157378 Hz with two perturbation widths;
the largest harmonic residual is **1.283e-11**. Replaying the earlier live
state at the dip through current code gives **1.430e-11**, supporting the
unchanged live branch.

## Comparison with the same reference samples

| Setting | Samples within 5% | RMS magnitude error, dB | Yaw at published dip, deg/s per F3 |
| --- | ---: | ---: | ---: |
| Previous live influence | 85/260 | 2.45266 | 0.0742178 |
| Corrected frozen influence | 71/260 | 2.41121 | 0.0756733 |
| Published ASWING drawing | — | — | 0.0339862 |

The denominator is the same 65 frequencies times four outputs for each
setting. RMS uses the same 61 uniformly logarithmic frequency points as the
previous study. Alternative settings are kept separate. The small aggregate
RMS reduction does not imply that more points pass: fewer do, and the yaw
error at the published dip increases from **118.38% to 122.66%**. The difference
between these rows includes the full K/F setting and retrim; it does not
isolate the plume correction alone. The underlying [CSV and metrics](../../artifacts/daedalus-frozen-source-20261114/report/)
retain all four outputs and every sample.

The original plot's operating point remains unidentified, and its phase is
unavailable. This is a documented-setting comparison, not authentication of
the historical case. The prior midpoint-operator frozen/live diagnostic is
not substituted for these current source-equation results.

## Relation to the Daedalus wing paper and next work

Drela's *Method for Simultaneous Wing Aerodynamic and Structural Load
Prediction* remains a useful independent steady benchmark. The existing
[Figure 8 overlay](daedalus-wing-paper-20261113.md) uses the earlier live
equilibrium and supports the wing shape and broadly similar load distributions.
The paper's 240 lb / 22 ft/s case, historical roll-pinned mount and wing-only
formulation do not specify the later full-aircraft Bode run. The conditional
roll release already tested there worsens the yaw mismatch. No paper parameter
was transplanted into the public aircraft for this study.

The steady description distinguishes a converged residual from the lagged
geometry derivatives used to accelerate Newton iterations. The unsteady
description defines dynamic partial derivatives and discusses reusing Newton
matrices. Reconciling those statements is a useful next source audit, but it
does not yet justify removing a physical derivative or claiming native ASWING
does so. The present comparison differentiates the configured full residual.

## Evidence and remaining validation

The [bounded driver](../../scripts/check_daedalus_frozen_source.py) stores an
immutable runner, input hashes, logs, results and terminal receipt per job.
There are **38 completed jobs: 35 successful, one expected pre-fix regression
failure and two guarded derivative attempts**. All children were reaped.
Maximum CPU time is 10.600 s, wall time 15.860 s and RSS 105.34 MiB, under the
unchanged 15 CPU s / 25 wall s / 512 MiB limits and one BLAS thread.
The [verification receipt](../../artifacts/daedalus-frozen-source-20261114/verification.json)
checks input provenance, the six intended production changes and retained
outputs. No browser/build job was run; that user-requested hold remains.

ISAE fractions, comparison scopes and progress events are unchanged. Existing
powered frozen-influence ISAE results are historical evidence and have not been
revalidated under this correction. Native Bode agreement remains open.
