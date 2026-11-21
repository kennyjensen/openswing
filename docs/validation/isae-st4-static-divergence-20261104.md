# ST-4 static divergence verification

The declared straight Weight7a pilot reaches its first static pressure
singularity at **139.44477948 m/s** in OpenSwing. The independently assembled
beam/horseshoe reference gives **139.44323010 m/s**, a **0.001111%** difference.
Both mesh refinements pass the predeclared 0.1% speed criterion. This verifies
the static divergence calculation for this setup; it does not establish a
native ASWING match or the lowest flutter speed.

The original model, fixed frame, zero incidence, fixed Mach zero, prescribed
gravity and density are retained. No parameter is fitted to the archive.
The independent formulation is described in the
[flowing-air reference](isae-st4-flow-reference-20261104.md).

| Calculation | Structural / circulation intervals | Critical speed (m/s) |
|---|---:|---:|
| OpenSwing requested N128, saved at 139.5 m/s | 129 / 129 | 139.44570943 |
| OpenSwing requested N160, saved at 139.5 m/s | 161 / 161 | 139.44477948 |
| Same N160, saved at 120.5 m/s | 161 / 161 | 139.44477948 |
| Independent reference, first grid | 384 / 513 | 139.44325540 |
| Independent reference, refined aerodynamics | 384 / 769 | 139.44327204 |
| Independent reference, refined structure | 513 / 769 | 139.44323010 |

The OpenSwing mesh change is 0.000667%; separate reference aerodynamic and
structural changes are 0.0000119% and 0.0000301%. The two N160 operating points
agree within 2.7e-12 m/s. All five declared speed comparisons pass.

With circulation normalized by speed, the static Jacobian has block form
`J(q) = [[A, q B], [C, D]]`, where `q = (U/U0)^2`. Exact elimination of all
mechanical coordinates gives `D gamma = q C A^-1 B gamma`. Every circulation
coordinate remains in the generalized eigenproblem. The full mechanical right
vector is `-q A^-1 B gamma`; the mechanical left vector is
`-A^-H C^H w_flow`. The helper checks both full null-vector equations and a
nonzero speed sensitivity. Five retained formula tests cover the full pencil,
complex coordinate transformations and invalid/singular cases.

The pressure scaling is checked against fresh physical residuals, rather than
assumed from the saved matrices alone. For each OpenSwing case, the runner
restores the physical equilibrium at the candidate speed, verifies coordinate
scales, and evaluates six centered probe widths from 1e-3 to 3e-6. It also
checks the candidate, a smooth geometry perturbation and a circulation
perturbation at three speeds around the candidate. All dynamic kinematic rows
are included, with zero state rates for this zero-frequency calculation.

Across 102 fresh residual evaluations, the largest base residual is 4.59e-16.
The largest scaled directional-action error is 1.98e-9, below the 1e-7 gate.
At the two smallest probe widths, left-projected speed corrections are at most
8.39e-10 m/s; these are local sensitivity estimates, not rigorous error bounds.
The projected static residual changes sign across the prescribed ±0.01% speed
bracket. Both full null-vector checks pass in all six calculations.

The six serial numerical jobs total 65.23 seconds, excluding initial source
hashing, with peak recorded RSS of 152,332 KiB. The runner uses one BLAS thread,
a 90-second limit and a 512 MiB address-space cap. No equilibrium solve or
dynamic modal sweep is repeated.

The existing **24/26 production modal mesh checks**, **24/26 modal reference
comparisons**, native scores and near-critical modal discrepancies remain
unchanged. Good agreement in critical speed does not prove convergence of each
modal component arbitrarily close to a crossing. The archived slow root still
has the opposite sign at 139.5 m/s; its native static crossing is unavailable.

The reusable helper is `scripts/static_divergence.py`; the physical runner is
`scripts/verify-isae-st4-divergence.py`. The predeclared plan, full vectors, probe
actions, source hashes and individual receipts are in
`artifacts/isae/st4-static-divergence-20261104/`.
[Portable results](isae-st4-static-divergence-20261104.json) include all gates and
comparisons. Production kernels and the browser build are unchanged.
