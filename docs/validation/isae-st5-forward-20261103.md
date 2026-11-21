# ST-5 original forward-wing comparisons — 2026-11-03

All four distinct forward-wing-only snapshots complete three serial grid solves
and fresh residual checks: **12/12 physical solves pass**. ST-5 remains incomplete.
The initial printed-coordinate grids reproduce the archived response much more
closely than the refined grids, even with no joints present.

| Original load case | Z median error, initial / fine | Twist median error, initial / fine | Bending moment median error, initial / fine | Fine mesh checks |
|---|---:|---:|---:|---:|
| cosine_20lb | 0.001603% / 0.2815% | 0.000106% / 0.5889% | 0.000083% / 0.5700% | 6/14 |
| cosine_30lb | 0.001142% / 0.2724% | 0.000122% / 0.5841% | 0.000047% / 0.5601% | 6/14 |
| elliptical_20lb | 0.001080% / 0.1774% | 0.000117% / 0.0781% | 0.000045% / 0.2750% | 13/14 |
| elliptical_30lb | 0.000974% / 0.1784% | 0.000192% / 0.0746% | 0.000050% / 0.2705% | 13/14 |

The error medians above cover finite nonzero references at every original row.
The [machine-readable report](isae-st5-forward-20261103.json) additionally records medians
and maxima restricted to failed scalar checks. Mesh checks compare 76 and 152
intervals using the unchanged 0.1% limit: **38/56 pass**. The largest per-case
mesh changes are 0.205–0.480%; no coarse failure is discarded.

Across all three grids, **10,670/18,792 required scalar slots match** after
excluding the unresolved reaction-display matches from the numerator:

- Structural predictions: **2,342/9,744** match printed half-last-place intervals.
- Conditional zero outputs: **6,960/6,960**.
- Input-display echoes: **1,368/1,392**.
- Unresolved `f_reac`: 12 raw matches among **696 required entries**, with none
  credited as validated. Zeros and input echoes do not establish physical fidelity.

Inputs are the untouched `JW_1_FW_20lb` and `JW_1_FW_30lb` model/driver/output
triples under `Rigid_Joint` and `Elliptical_Loading` in pinned ISAE revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`. The former files also occur byte-for-byte
under `Link_Joint` and `Elliptical_Loading/cosine_load`; those copies are catalogued
without extra solves. All 58 output rows, duplicate traces, and 27 output columns
are retained. All 72 source-decoder checks pass, including independent root load
balance and shell recovery at literal property knots.

Each original model has one rigid root clamp, no joints, and 16 exactly null
point-weight records. The records remain in the parsed model. Original distributed
loads and self-weight are unchanged; filenames are not used to normalize loads.
The driver specifies zero-flow structural equilibrium. The numerical policies are
`drela-segspl-v1` interpolation and `drela-steady-section-v1` structural equations.
Grids have 38/76/152 intervals, formed from printed coordinates and exact known
model knots. They are not claimed to be the recovered historical node arrays.

Maximum fresh residual is **8.35e-13**; maximum force/moment balance errors are
**4.27e-14 lb / 4.22e-9 lb-ft**, within the existing gates. Peak child RSS is about
100 MiB. The 12 dispatch solves total **23.75 s**; complete numerical processes
and their checks total **172.12 s**. Jobs used one BLAS thread, 180 s time limits,
and 512 MiB address-space limits. A retained initial attempt used system Python,
which lacked NumPy and failed before solving; successful runs use `.venv/bin/python`.

This independently shows that joints alone cannot explain the initial-versus-fine
archive discrepancy. The initial 20 lb cosine-load tip errors are 3.35e-7 ft in
Z and 4.43e-7 degrees in twist. Historical discretization and coordinate/output
precision remain plausible explanations; no material or load fitting was used.
Exact printed agreement, mesh convergence, and original exporter identity remain
separate requirements. No solver or application code changed in this study;
no new browser validation or distribution build is claimed.

Reproduce with `python3 scripts/verify-isae-st5-forward.py prepare --stage NEW_DIR`,
then run each case/level using `.venv/bin/python scripts/verify-isae-st5-forward.py
run --stage NEW_DIR --case CASE --level LEVEL` with `OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`, serially. Finish with
`python3 scripts/verify-isae-st5-forward.py assess --stage NEW_DIR`.
The [retained study](../../artifacts/isae/st5-forward-20261103-run/assessment.json)
contains source pins, generated recovery code, all solved states and comparisons.
