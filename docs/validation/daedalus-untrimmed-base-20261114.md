# Daedalus: conditional accelerating operating point

Observed 2026-11-14 UTC. A new operating-state diagnostic substantially deepens
the low-frequency yaw dip, but **does not match the complete native response**.
It is evidence that the operating point matters, not a recovered ASWING setup
or a reason to change the default flight condition.

At the reference dip frequency, 1.1573777374 Hz, the yaw magnitude changes from
**0.0738485 to 0.0406700 deg/s/F3**. The native drawing gives 0.0339862, so the
same-frequency discrepancy changes from +117.29% to +19.67%. However, yaw at
0.1 Hz becomes +54.80% high, and roll at 6.79896 Hz becomes +787.81% high.
No physical parameter was fitted and no production equation was changed.

[Comparison plot (PNG)](../../artifacts/daedalus-untrimmed-base-20261114/report-v2/comparison.png),
[SVG](../../artifacts/daedalus-untrimmed-base-20261114/report-v2/comparison.svg),
[all four outputs at eight frequencies (CSV)](../../artifacts/daedalus-untrimmed-base-20261114/report-v2/comparison.csv).
Orange markers are individual conditional samples, not a continuous curve or
located extrema. The earlier plot remains in `report/`; `report-v2/` moves
its legend so it does not cover the low yaw dip. Numerical values are unchanged.

## Reference basis and qualification

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog were consulted. Drela's
[original manual](../../reference/aswing_doc.txt), **Forced-Response Frequency
Analysis — BODE**, defines perturbations about the current converged operating
point and distinguishes its static constraints from the dynamic constraints.
It does not identify the operating point used for the public Daedalus drawing.

The [unsteady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed p. 26, §13.1, Eqs. 130–134, explicitly permits linearizing a converged
quasi-steady or time-marched state. It also limits the physical interpretation:
time-invariant response requires a trimmed state with constant system matrices.
An instantaneous nontrimmed response is meaningful only on time scales much
shorter than the changes in those matrices. Section 13.2, Eq. 135, gives the
harmonic descriptor solve used here.

Consequently, this calculation is a **locally frozen descriptor at an
accelerating state**. It is not a periodic trajectory or proof that the native
plot used such a state. Its substantial pitch acceleration makes the
time-scale qualification particularly relevant near 1 Hz and below.

## Disclosed setup

Use the literal public `dae.asw`, the current 98-interval / 103-node mesh,
SEGSPL, source airflow equations, Mach 0.1, aerodynamic lag and live influence
geometry. Speed remains 6.7 m/s; mass, stiffness, damping, stall constants,
core settings, reference locations and all aircraft input tables are unchanged.

Prescribe alpha=beta=0, all three Euler attitude angles zero, mean rotation
rates zero, F2=F3=0 and engine-1 power zero. Solve all six translational/angular
accelerations from zero net force and moment, including inertial reaction.
Solve the elastic shape, internal forces and circulation afresh. The original
level-flight shape is only an initial Newton guess. Zero local elastic rates
and circulation rates define the instantaneous state.

This changes several operating inputs together; it does **not** isolate
incidence, elevator trim, thrust, preload or frame acceleration individually.
These are deliberately explicit diagnostic settings, not asserted ASWING
defaults. No result was used to choose or adjust their values.

The accepted state has maximum scaled residual **3.212e-10**, below the same
1e-9 threshold used for level flight. Frame acceleration is
(-0.385419, 0.00308991, -6.47983) ft/s², and angular acceleration is
(-0.000661305, -0.436183, -0.0000139068) rad/s². The pitch component is about
-24.99 deg/s². The dynamic-base residual is identical and its
`kinematically_steady` flag is false.

The maximum wing z displacement from the jig falls from 8.09679 to 6.87162 ft
(about 15.1%). This confirms a change in loaded shape; it does not compare
that shape quantitatively with the native GIF.

## Same-frequency results

All rate values are deg/s per unit native F3. The native values come from the
previously checked PDF paths used by the
[current comparison](daedalus-current-bode-20261114.md). The CSV retains their
graphic-reading bands. Rounded CLI frequencies differ from those retained
paths by less than 1e-9 Hz; no distant-sample or response interpolation is used.

| Output | Frequency, Hz | Native drawing | Level flight | Conditional accelerating state | Conditional error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Yaw | 0.1 | 0.118238 | 0.119910 | 0.183037 | +54.80% |
| Yaw | 1 | 0.0587461 | 0.0748817 | 0.0411793 | -29.90% |
| Yaw | 1.15738 | 0.0339862 | 0.0738485 | 0.0406700 | +19.67% |
| Roll | 1.54881 | 0.0221981 | 0.0102140 | 0.0179852 | -18.98% |
| Yaw | 6.94779 | 0.0855693 | 0.0934289 | 0.144520 | +68.89% |
| Roll | 6.79896 | 0.00206532 | 0.00320698 | 0.0183361 | +787.81% |
| Yaw | 8.77304 | 0.517660 | 0.603630 | 0.510021 | -1.48% |

These are values at the drawing's feature frequencies, not comparisons of
each model's own extrema. The conditional case's full curve and extrema have
not been computed. A shifted narrow feature can have a large same-frequency
error; the eight samples do not prove that its high-frequency dip disappeared.

## Verification and outcome

All 1,953 states are retained. Every dynamic derivative was rebuilt at the new
base; no level-flight dynamic matrix was reused. Exact beam elimination yields
a 717-coordinate frequency factorization and recovers the full response.
Three complete-residual directions check both assembled matrices, with maximum
relative errors **2.889e-12** for A and **4.693e-11** for M. The largest scaled
matrix residual across eight samples is **6.076e-17**.

All **27 numerical stages** succeeded and were reaped, with matching source
hashes. The largest job used 5.759 CPU seconds and peak numerical RSS was
127,940 KiB, within the existing one-thread / 512 MiB / 15 CPU-second /
25 wall-second limits. The plot was visually inspected. No browser, build,
Node, WASM or background solver job ran. No ISAE fraction or scope changed.

This result keeps operating-state differences as a credible contributor to
the low yaw discrepancy, but rejects this particular zero-incidence,
zero-control snapshot as a full match. Further diagnosis must separate the
changed operating inputs and continue checking all four outputs. Neither the
native setup nor general dynamic validation is established.

[Numerical evidence](../../artifacts/daedalus-untrimmed-base-20261114/report-v2/result.json),
[source pins](../../artifacts/daedalus-untrimmed-base-20261114/report-v2/source-pins.json),
[bounded driver](../../scripts/check_daedalus_untrimmed_base.py),
[report generator](../../scripts/report_daedalus_untrimmed_base.py).
