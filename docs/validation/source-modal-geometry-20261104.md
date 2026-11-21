# Local source modal geometry assembly

Fixed-frame vacuum and still-air source modal assembly now probes geometry
columns with disjoint equation supports together. The known moving-source
operator also uses this path when its frame is fixed. Each probe evaluates
the full physical residual with the same fourth-order stencil and step.
No induced field, physical coupling, matrix entry or mode is discarded.

Supports include adjacent beam compatibility/balance equations, offset objects,
ideal and sprung joints, struts and local kinematics. Global frame/control
equations, airflow, unknown source classes and unsupported method overrides
retain their established derivative paths. Existing hinge and wire transition
checks run on every grouped probe.

| Measured case | Before | After |
|---|---:|---:|
| ST-2 N320 still-air equilibrium, assembly and checkpoint | 145.61 s | 11.29 s |
| Same stage, CPU time | 115.51 s | 9.78 s |
| Same stage, physical residual evaluations | 7,914 | 258 |
| ST-2 N160 vacuum, complete 20-mode calculation | 84.26 s | 42.79 s |
| Complete calculation, CPU time | 58.47 s | 28.31 s |

These single-run observations give **12.89×** faster
equilibrium/assembly/checkpoint execution and **1.97×** faster
complete modal execution. The latter includes full physical outputs, sparse
matrix checkpoints and physical verification under the identical original
request. Jobs run serially with one BLAS thread and a 512 MiB address-space cap.
Host scheduling varies; the CPU measurements also show reduced computation.

Both complete **5,796 × 5,796 A/M matrices are exactly unchanged**. All 40 saved
left/right eigenvectors pass their original-pencil checks. The N160 matrices,
all 20 complete mode/vector/output objects and physical base outputs are also
exactly unchanged; only the base evaluation counter differs.

All **50 regression tests pass**, including 15 new cases. Independent full
residual probes verify every row outside the proposed supports at curved,
loaded, damped and offset states, including a distant sprung joint, fuselage
geometry, still air and moving inertia. Separate loaded-base tests compare
complete grouped and individual-column pencils. Existing source-operator and
brace/wire regressions retain their original physical gates.

An original Pazy N12/four-mode still-air request passes the actual built offline
worker: **21 comparison groups**, complete A/M matrices,
base state, all four poles, both vector sides and physical modal outputs.
Its geometry derivative groups all 84 geometry columns into
18 groups. The browser solve takes
**6.52 s** in this observation. All 137 kernel hashes are
verified before and after the solve; no page/network errors or external/offline
requests occur. This is worker verification, not a new UI or project-save test.

The first saved-matrix comparison failed because its verifier did not handle
an empty sparse difference. Correcting that verifier established exact matrix
equality without rerunning assembly. The failed receipt and original verifier
remain recorded.

ISAE scores and tolerances are unchanged. The earlier ST-2 independent 14/14
mode study retains its scope; this optimization adds no native ASWING agreement.
Source hashes, complete outputs, matrices and execution receipts are retained in
`artifacts/isae/source-modal-geometry-20261104/`. The
[portable evidence](source-modal-geometry-20261104.json) includes the measurements
and browser comparisons.
