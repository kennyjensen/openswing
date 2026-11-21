# Exact reuse in mounted tangents

This optimization retains the equations, mesh, precision, finite-difference
steps, rank check, four load increments and convergence tolerances. Flexible
structures still assemble fresh tangents at every load step. The previously
validated guarded intermediate-tangent reuse for rigid structures remains.
The full ASWING goal is still incomplete.

The initial rank check and first loaded tangent evaluate identical physical
states. A bounded load cache reuses their transferred forces, moments and
circulation residuals. Every load-factor residual and finite difference retains
the original arithmetic. This reuse is limited to ordinary equilibrium without
operating constraints or residual overrides, and is discarded after the first
accepted load. A separate transient cache retains fixed material interpolation
and jig frames only during one tangent.

For larger aerodynamic influence matrices, a node perturbation changes only
nearby vortex segments and receivers. The cache reuses identical pairs and
recalculates every changed pair with the original Biot–Savart kernel, including
wake cores, physical-bound exclusions, PG and ground images. Complete-array
PG/image transformations retain their original arithmetic order. Changed global
parameters fall back to complete evaluation. Matrices with fewer than 4096 pairs
use the original complete vectorized kernel, avoiding small-array bookkeeping.
This retains deformation sensitivities and does not enable K/F frozen influences.
The stored influence/material arrays have a 64 MiB budget; the initial-load
cache has a 32 MiB entry budget. Cache exhaustion only changes computational cost.

Actual UI worker-request-to-reply observations at the unchanged 48-panel setting:

| Case | Browser before | Browser after | Reduction |
|---|---:|---:|---:|
| Default rectangular wing | 32.512 s | 24.473 s | 24.7% |
| Flexible wing | 48.775 s | 46.951 s | 3.7% |

These are single sequential observations on a shared host with its normal
available CPU affinity, not timing guarantees. Cold runtime initialization is
excluded. Both versions run through the real UI and Pyodide worker; Playwright
routes supply each pinned numerical source tree to the same frontend. The final
built and served sources are separately checked against the tested candidate.
The flexible-wing gain in this browser comparison is small.

All 214 selected native tests and 51 exact WASM comparisons pass.
Coverage includes complete Jacobians versus original finite differences at
nonzero deformation, circulation and frame/elastic motion; propulsion;
wing/body interactions; joints; ground; Fourier circulation; frozen influences;
loaded apparent-rate terms; material load transfer; cache invalidation,
exhaustion and exception cleanup. Existing independent mechanics, balance,
mesh-refinement, trim and saved-equilibrium tests are included. This is not a
full-suite run. Both complete native results are byte-identical to their baselines.

The final browser comparisons retain all 8,027 default-case and 7,736 flexible-case
numeric fields exactly, including complete physical outputs and residuals.
The comparison excludes software provenance and the top-level evaluation counter;
the counters are checked separately and remain 1,150 and 1,860. Only numerical
software provenance changes. No accuracy or convergence threshold was relaxed.

An earlier candidate passed native checks but did not show consistent browser
improvement; its flexible browser run reached the harness timeout. It remains
recorded as FAIL. That run also used restricted CPU affinity; no single cause
of its timing is asserted. The accepted revision keeps full vectorized kernels
for small matrices and uses a fresh paired browser comparison. Exploratory
unpinned native runs, a failed extra byte-equality assertion on a repeat of the
unchanged baseline, and a status-file polling race are retained in the evidence.
The repeated native baseline still met the original numeric comparison bounds.

[Results](mounted-tangent-reuse.json) and [hashed evidence](mounted-tangent-reuse-evidence.zip)
include source snapshots, complete requests/results, profiles, tests, browser
progress, screenshots and rejected attempts. Every evidence member has a
SHA-256 entry in MANIFEST.json. To reproduce native measurements, extract it and
run `measure-mounted.py baseline NEW_LABEL` and
`measure-mounted.py candidate-06 NEW_LABEL` with the repository virtualenv and
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`; add `--flexible` for that case.
`scripts/test-tangent-reuse-wasm.mjs` runs the 51 exact WASM comparisons against
the current source and self-hosted runtime.
