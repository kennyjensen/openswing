# Exact mechanical derivatives in source modal assembly

Modal assembly now uses the source formulation's exact internal-force,
internal-moment and reaction derivatives. The same mechanical block already
serves steady and time-domain assembly. Geometry, circulation, inertia and
motion derivatives retain their existing full equations.

At fixed endpoint frames, the section compliance is linear in the internal
loads. With the endpoint-average transform `Ta`, its translation derivative is
`-Ta.T @ dstrain * ds/L`, and its rotation derivative is `-dcurvature * ds`.
The block includes coupled section compliance, offset force couples and the
smooth sprung-joint chain rule. Material-rate terms do not depend on these
load coordinates. Unknown constitutive or rate laws, custom measurements,
controllers and unsupported derivative states keep the full-residual route.
The general source `analytic_mechanics` flag remains false; midpoint
compatibility derivatives are not substituted for the source equations.

| Matrix assembly | Previous residual evaluations | Exact-column evaluations | Previous CPU / elapsed | Exact-column CPU / elapsed |
|---|---:|---:|---:|---:|
| ST-4 N160, 3,077 unknowns | 162 | 114 | 40.47 / 46.88 s | 44.33 / 48.48 s |
| Hinged two-beam airflow model, 340 unknowns | 1,926 | 1,062 | 35.79 / 44.11 s | 24.47 / 49.71 s |

These are individual observations, not controlled speedup estimates. The
hinged model uses 108 exact columns and saves 864 residual evaluations;
ST-4 uses 972 exact columns and saves 48. Neither observation shows an elapsed
time improvement. The ST-4 path still performs 3,890 induced-field evaluations
for geometry derivatives. Its principal-value guard requires complete physical
differences for the retained vortex stencil; this change does not bypass it.

Both complete mass matrices remain exactly unchanged. The hinged physical
equilibrium is identical, excluding the intentionally reduced evaluation count.
All complete A-matrix, original left/right eigenvector residual, pole and
phase-normalized vector/output comparisons pass their existing gates. These
checks include the saved ST-4 modes and all four newly computed hinged modes.
Projected ST-4 pole changes are diagnostics only; no correction is applied to
scored results.

All **38 distinct regression tests** pass across bounded serial batches. Nine
new cases cover vacuum, still air, prescribed and free moving frames, airflow,
fuselage sections, nonzero material damping, offset masses and joints. Every
load/reaction column is compared with complete physical residual differences
at two step sizes. Existing independent source tangents, damped spectra and
mixed state/rate directions remain covered. Initial fixture errors and obsolete
routing assertions are retained in the execution record; numerical gates were
not relaxed. The first matrix assessor also incorrectly required evaluation
counts to remain identical; it now retains those counts separately while
requiring every physical base field to match exactly.

The built offline worker passes all **21 comparison groups**, including both
complete matrices, the physical base, all four poles, both eigenvector sides,
complete phase-normalized outputs and original-pencil residuals. Its cold solve
takes 40.99 seconds in this observation. There are no page errors, failed network
requests, external requests or requests after disconnection. All 137 kernel
hashes match the native sources before and after assessment. This is a worker
calculation check, not a new desktop/mobile UI or saved-project check.

The original browser invocation completed and saved the result before a new
verifier incorrectly expected the worker reply to echo its request. The input
is established by the retained, hash-verified harness and request file. Corrected
assessment reuses that same saved output and takes 3.62 seconds; it does not
repeat or alter the solve. Future live runs record the exact posted request.
The original failed audit remains available alongside the passing reassessment.

Browser verification is recorded in the accompanying
[portable evidence](source-modal-mechanics-20261104.json). This study adds no
native ASWING comparison passes and changes no ISAE tolerances. Original ISAE
setup ambiguities, ST-4 mesh/reference failures and full-family validation
remain open. Full execution artifacts are in
`artifacts/isae/source-modal-mechanics-20261104/`.
