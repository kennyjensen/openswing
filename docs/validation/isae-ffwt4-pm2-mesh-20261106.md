# Flare20 equilibrium mesh refinement

The literal Flare20 PM2 model now reaches full-load equilibrium on **107
nodes**, compared with 55 in the original preflight. The independent audit
verifies all seven serial jobs, 17 accepted load steps and zero rejections.
The final rebuilt physical residual is **9.6535e-13**.

The root moment changes by **0.0448%**, passing the existing **0.1%** spatial
gate for that quantity. This is not all-field mesh convergence or a completed
gust comparison. No native comparison count changes: FFWT-4 remains
**200/8,000 at 5%**.

## Controlled meshes and conditions

Every actual interval of the coarse mesh is bisected in material station.
All original attachment/property stations remain exact shared nodes. No
coarse physical state is transferred: the finer solve starts undeformed,
with unchanged load continuation, nonlinear equations, rank and residual
thresholds, 5-degree Newton rotation guard and rejection budget.

| Mesh | Main/right-tip/left-tip nodes | Total nodes | Unknowns | State |
| --- | --- | ---: | ---: | --- |
| Original preflight | 33 / 11 / 11 | 55 | 712 | Full equilibrium |
| One bisection | 65 / 21 / 21 | 107 | 1,388 | Full equilibrium |
| Two bisections | 129 / 41 / 41 | 211 | 2,740 | Initial rank fallback exceeded its 90-second cap; no accepted load step |

The original driver requests `I 100`, `I 40`, `I 40`; these nested grids do
not claim to reproduce its unknown historical node placement. The literal
model, two qualified rigid-pylon attachments, speed 22, incidence 6 degrees,
sideslip 16 degrees, density 1.2256, gravity 9.81 and declared zero Mach remain
unchanged. Original attachment semantics and other historical startup defaults
retain the qualifications in the source inventory and continuation study.

The frozen kernel is
`.reference/solver-snapshots/ffwt4-continuation-json-20261106/`. The 55-node
study used its earlier serializer; the prior verification establishes that
only JSON numeric hashing differs, with physical equations unchanged. The
new study makes no runtime-kernel changes.

## Quantitative comparison

| Quantity | 55 nodes | 107 nodes | Absolute change |
| --- | ---: | ---: | ---: |
| Sensor-1 local chordwise root moment, N m | 0.5445487051 | 0.5447928508 | 0.0002441457 |
| Joint 1 angle, degrees | 40.0309033 | 39.9178769 | 0.1130264 |
| Joint 2 angle, degrees | -5.6450755 | -5.6268498 | 0.0182257 |
| CL | 0.05865940 | 0.05878159 | 0.00012220 |
| CDi | 0.0006704581 | 0.0006691134 | 0.0000013447 |

The primary error is the absolute moment change divided by the finer-mesh
moment. Among all 55 shared material nodes, the maximum position change is
**0.2560 mm** and the maximum relative rotation is **0.0020003 rad**. CL/CDi
change by about 0.208%/0.201%; small rolling/yawing coefficients change by
1.13%/4.01%. Those values reinforce the need for further refinement even
though the root-moment gate passes. The complete coefficient and shared-node
differences are retained; near-zero profile drag is not treated as a useful
relative-error accuracy measure.

The archived first Flare20-1 moment at t=0 is **0.530039 N m**. The coarse and
finer equilibria differ from it by **2.7375%** and **2.7835%**, respectively.
This is a diagnostic comparison only: the mesh study does not establish the
full time-launch setup, compute any gust history or add a native pass. The
source file, line, printed precision and complete native-inventory hash are
retained in `native-initial-reference.json`.

## Evidence and reproduction

All evidence is under `artifacts/isae/ffwt4-pm2-mesh-20261106/`:

- `study-plan.json` pins source, driver, coarse evidence, kernel, mesh files
  and the pre-existing 0.1% gate before the refined solve.
- `level-1/job-001` through `job-007` retain exact requests, progress, outputs,
  source/kernel/predecessor hashes and actual zero process exit codes.
- `level-1/assessment.json` rebuilds every saved boundary on a fresh network
  and checks contiguous continuation, rotation guards and physical residuals.
- `comparison-55-107.json` checks identical physical requests and shared
  nodes, then reports the root-moment gate and additional field diagnostics.
- `verification-107.json` pins the completed evidence and assessment tools.

Each solve job uses one BLAS thread, a 512 MiB address-space limit and a
90-second external cap. The first job accepts one load step, the second two,
and subsequent jobs at most three. Reported job times range from 23.09 to
49.68 seconds, summing to 251.12 seconds. These are retained per-job elapsed
measurements, not a browser speed benchmark. The ill-conditioned dense solve
warning in job 3 is retained; its accepted states still pass fresh physical
residual checks, and no numerical gate was relaxed.

`scripts/advance-isae-ffwt4-equilibrium.py --mesh-file ...` changes only the
mesh from the pinned original preflight request. The continuation assessor
accepts explicit `--kernel-root`, `--mesh-file` and `--helper-copy` arguments
to audit that same frozen calculation. `scripts/assess-isae-ffwt4-pm2-mesh.py`
requires complete audited equilibria and refuses to overwrite an earlier
comparison. Further mesh refinement, other PM2 equilibria and their gust
histories remain required.

## Limit encountered on 211 nodes

The first 211-node job exited with timeout code 124 while forming the full
unloaded Jacobian, before accepting any load step. Its last progress record
is 1,730 of 2,740 tangent columns. This is a recorded incomplete attempt, not
a failed physical equilibrium or evidence of a mechanism.

A separate bounded diagnostic reused the existing 2,532-row mechanical block.
The production SVD certificate excludes blocks above 2,048 rows (32 MiB dense
input). Allowing this diagnostic's 48.91 MiB input took 15.74 seconds for SVD,
but gave a singular-value ratio of **8.1741e-11**, below the unchanged **1e-10**
gate. Simply increasing the size cap would therefore not certify this case.
The corresponding 107-node ratio was 1.8003e-10. These are conditioning
measurements in the existing scaled coordinates, not an independent proof of
a physical mechanism. The cached matrices, source pins and diagnostic code
are retained under `rank-211/` for further analysis without rebuilding physics.

A second read-only diagnostic applies the same invertible norm equilibration
to that saved matrix for up to 300 updates, with a predeclared maximum log-norm
error target of 0.001. It reaches the iteration cap with log-norm error 0.0230,
so it does **not** meet that optional equilibration stopping criterion. Its
actual singular-value ratio is nevertheless **1.5737e-10**, which passes the
unchanged rank gate. The diagnostic takes 18.42 seconds and changes no physical
matrix or production code. `rank-scaling-211/` retains its plan, scaling factors,
matrix, SVD result and zero process exit code. This identifies a concrete
conditioning improvement to integrate and test, not an accepted 211-node load
step. Any production change must preserve mechanism/redundancy rejection,
finite memory/work bounds, the rank threshold and the physical residual gates.

The subsequent [production rank refinement](isae-ffwt4-rank-refinement-20261106.md)
implements that bounded path and passes 66 native regression checks. A fresh
211-node continuation under its separately frozen kernel now saves two load
steps. This follow-up preserves the original failed attempt and all evidence
reported above; it does not yet complete the finer equilibrium.

The [2026-11-07 continuation](isae-ffwt4-pm2-211-20261107.md) subsequently
completes the 211-node equilibrium in 17 accepted steps, with rebuilt residual
2.06e-13. Its root moment changes 0.195% from 107 nodes, exceeding the 0.1%
gate; all six per-beam displacement/finite-rotation checks also fail
(0.108–0.236%). The earlier passing root-moment pair therefore did not
establish resolution. Further mesh investigation remains necessary.
