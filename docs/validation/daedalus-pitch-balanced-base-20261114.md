# Daedalus: pitch balance does not remove the deeper conditional yaw dip

Observed 2026-11-14 UTC. Solving the elevator setting to remove the large mean
pitch acceleration changes yaw at the native dip by only **-0.885%**, from
0.0406700 to **0.0403100 deg/s/F3**. Thus the deeper dip found in the preceding
[zero-incidence diagnostic](daedalus-untrimmed-base-20261114.md) survives pitch
balance. This case still fails to match the full native response.

[Comparison plot](../../artifacts/daedalus-pitch-balanced-base-20261114/report-v2/comparison.png),
[SVG](../../artifacts/daedalus-pitch-balanced-base-20261114/report-v2/comparison.svg),
[all four outputs (CSV)](../../artifacts/daedalus-pitch-balanced-base-20261114/report-v2/comparison.csv).
Eight discrete samples are shown for each conditional state. They are not
complete conditional curves or located extrema. The two sets of markers
nearly overlap.

## One changed operating constraint

Retain the preceding diagnostic's literal `dae.asw`, current mesh, speed
6.7 m/s, zero alpha/beta/attitude/mean rotation, zero F3 and zero engine power.
All physical properties and aerodynamic options remain unchanged. Replace
the one pitch-moment constraint's unknown:

- Previous: prescribe F2 = 0 and solve angular acceleration about y.
- New: prescribe angular acceleration about y = 0 and solve F2.

The other five frame accelerations remain unknowns determined by the same
zero net-force/moment equations. The coupled elastic shape, internal loads
and circulation are solved afresh. F2 is **not fitted to any response value**.

The new equilibrium gives **F2 = -2.55191906** in native control units. Maximum
scaled residual is **5.942e-10**, below the unchanged 1e-9 criterion. Frame
acceleration is (0.879034, 0.00133538, -6.77925) ft/s². Angular acceleration is
(-0.000555058, 0, -0.000214851) rad/s². The large previous pitch component,
-0.436183 rad/s², is removed. Maximum wing z displacement from the jig changes
from 6.87162 to 6.84459 ft, only -0.393%.

For the subsequent response, **all six dynamic accelerations are free**, and
F2 remains at its solved mean setting. Pitch perturbations are not held fixed.
The released dynamic base independently satisfies the same residual tolerance.

The source basis remains the [authoritative reference collection](aswing-authoritative-references.md):
Drela's original manual, **BODE**, distinguishes operating-point and response
constraints; the unsteady description, printed p. 26, §13.1, Eqs. 130–134,
defines linearization of a converged instantaneous state and its time-scale
qualification. This state still has translational acceleration and is **not a
time-invariant flight trim**. A frozen local response does not establish a
periodic trajectory or identify the native operating point.

## Results at the same frequencies

Values are deg/s per native F3. Native values and their graphic envelopes are
retained from the checked PDF extraction used by the
[current level-flight comparison](daedalus-current-bode-20261114.md).

| Output | Frequency, Hz | Native drawing | Zero controls | Pitch-balanced | Pitch-balanced error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Yaw | 0.1 | 0.118238 | 0.183037 | 0.184600 | +56.13% |
| Yaw | 1 | 0.0587461 | 0.0411793 | 0.0405188 | -31.03% |
| Yaw | 1.15738 | 0.0339862 | 0.0406700 | 0.0403100 | +18.61% |
| Yaw | 1.5 | 0.0818181 | 0.0833696 | 0.0829258 | +1.35% |
| Yaw | 6.94779 | 0.0855693 | 0.144520 | 0.147013 | +71.81% |
| Roll | 6.79896 | 0.00206532 | 0.0183361 | 0.0186403 | +802.54% |
| Yaw | 8.77304 | 0.517660 | 0.510021 | 0.514137 | -0.68% |

Across all four outputs at the eight frequencies, changing pitch balance
changes magnitudes by at most **2.855%**. This includes the self-consistent
change in tail load, elastic shape and the other solved accelerations; it is
not an isolated derivative of the pitch-acceleration term. It nevertheless
shows that the deeper dip does not require the previous large pitch
acceleration. Incidence, wing preload and translational acceleration remain
unseparated explanations. Large errors at the native feature frequencies also
remain; eight samples do not establish the location of the conditional dips.

## Verification

All 1,953 dynamic states remain. Every dynamic matrix block was rebuilt at
the new base. Three independent complete-residual directions give maximum
relative errors **2.245e-12** for A and **1.499e-11** for M. The maximum scaled
frequency-solve residual is **8.299e-17**. Exact structural elimination gives
a 717-coordinate factorization, with the full response recovered.

All **26 numerical stages** passed and were reaped. Each job ran serially with
one BLAS thread and the existing 512 MiB / 15 CPU-second / 25 wall-second
limits. Maximum measured numerical CPU time was 5.647 seconds; maximum RSS
was 129,180 KiB. Sources for both comparison cohorts match their retained
hashes. `report-v2/` explicitly checks both cohorts without merging duplicate
path entries; it retains the numerical values of `report/`.

The plot was visually inspected. Production equations/defaults, browser
assets and ISAE completion fractions/scopes are unchanged. No background
solver, Node, browser, build or WASM job ran.

[Evidence](../../artifacts/daedalus-pitch-balanced-base-20261114/report-v2/result.json),
[source pins](../../artifacts/daedalus-pitch-balanced-base-20261114/report-v2/source-pins.json),
[bounded driver](../../scripts/check_daedalus_pitch_balanced_base.py),
[report generator](../../scripts/report_daedalus_pitch_balanced_base.py).
