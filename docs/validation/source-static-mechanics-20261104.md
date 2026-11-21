# Exact source mechanical columns in steady Newton assembly

Cold source-structure equilibria previously finite-differenced internal forces,
moments and support reactions even though these columns are linear at fixed
geometry. The steady assembler now uses the exact endpoint-average source
derivative already used by the time solver. It retains the source section
offsets, coupled bending/torsion, shear, nodal wrenches and sprung-joint chain
rule. The original midpoint compatibility block is replaced completely.

Geometry and circulation still use their existing full assembly. An unknown
constitutive load law, unsupported capture or derivative-budget failure retains
the original complete-residual fallback. The source class's general
`analytic_mechanics` flag remains false; this change does not enable a different
structural formulation.

| Measured work | Before | After |
|---|---:|---:|
| Residual evaluations per N48 Jacobian | 31 | 19 |
| Profiled N48 Jacobian assembly | 0.419 s | 0.302 s |
| Full N96 above-critical modal dispatch | 103.11 s | 96.55 s |
| Reported residual evaluations in that full case | 10,463 | 7,545 |

The full-case reduction is approximately 6.4% in these single observations.
The matrix timings include profiler overhead. These are not general speedup
estimates; the deterministic improvement is fewer residual evaluations for the
same Jacobian columns. Accuracy gates and physical input settings are unchanged.

The updated N96 case passes the independent discrete beam-column pole and
complete mode-shape references, fresh restored equilibrium, mass and wrench
balance, and all eight original-pencil eigenvector checks. The earlier
[symmetric fixed-fixed study](isae-st6-fixed-fixed-20261104.md) retains its nine
cases under its recorded source hashes; this is one fresh fine-grid case under
the updated kernel, not a rerun of that entire study or a native ASWING match.

The physical requests are identical. The modal mass matrix is exactly
unchanged; the largest A-matrix difference, scaled by its largest entry, is
1.92e-16. Scaled pole difference is 9.90e-15. The steady Newton matrix differs
from its former finite-difference estimate by 1.04e-10 on the same scaling;
the new load columns separately pass the full-residual derivative tests.

A complete profile of the small N16 above-critical reference records **242
steady Jacobian assemblies**. Under profiling, 62.6 of 72.1 dispatch seconds
are in the cold equilibrium. Repeated Newton/continuation work is therefore
the next investigation; faster individual matrices alone do not remove the
remaining delay. This profile includes substantial instrumentation overhead.

Eight new tests check all load/reaction columns against complete centered
residual differences for zero-offset, section, vacuum, coupled, airflow and
fuselage operators. They also verify exact fallback behavior. Thirty-two
existing source-physics tests and 42 joint/time tests pass. The existing test
that prevents midpoint-law substitution now poisons every midpoint compatibility
row and verifies its complete replacement. Four legacy nonlinear comparisons
pass separately; the first 11 legacy checks completed before the original
90-second batch cap, which remains recorded as an incomplete invocation.

The browser harness now accepts named column cases and either bending
direction, while retaining full phase-normalized output/vector comparison and
exact saved-project restoration. A small-mesh browser reference is checked
against the exact discrete solution; it does not establish spatial convergence.

Detailed profiles, saved matrices, requests, results and test receipts are in
`artifacts/isae/source-static-mechanics-20261104/`. The production build passes.
The offline N16 browser run passes all 420 checks, including both bending
directions, complete physical base and modal outputs, left/right vectors,
desktop/mobile layout and saved-project restoration. Its solve takes 44.02 s;
the complete browser invocation takes 78.00 s. The first invocation stopped
before launching Chrome because the harness expected the former dense-only
matrix-export expression. That harness assertion is corrected for the existing
sparse-aware exporter; the failed invocation remains in `browser/` and the
passing invocation in `browser-retry/`. No solver change or tolerance change
was needed for that harness correction.
