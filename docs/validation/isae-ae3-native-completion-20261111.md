# AE-3: native comparison completed with exact checkpoint reuse

Observed 2026-11-11 UTC. **434/725 comparisons pass at 5%**: **612 computed,
178 mismatches and 113 unavailable**. All native output groups now complete at
all six archived speeds; finite coefficients retain both nominal 80/160 meshes.
The original 725-target denominator, original models, equations and numerical
gates are unchanged. AE-3 is not fully validated.

| Output group | Passing / required | Computed | Mismatches | Unavailable |
|---|---:|---:|---:|---:|
| Finite coefficients, both meshes | 50/72 | 72 | 22 | 0 |
| Native derivatives | 174/252 | 252 | 78 | 0 |
| Native mass/inertia/centroid | 174/252 | 252 | 78 | 0 |
| Native normalized rates | 36/36 | 36 | 0 | 0 |
| Embedded original-ASWING locked curves | 0/43 | 0 | 0 | 43 |
| Embedded ASWING-m locked curves | 0/43 | 0 | 0 | 43 |
| Embedded ASWING-m rolling curves | 0/27 | 0 | 0 | 27 |
| **Total** | **434/725** | **612** | **178** | **113** |

Original printed-precision acceptance gives **387/725**. The 612 native
comparisons contain 576 distinct native values; the finite coefficients are
checked on two meshes. All archived rates are zero; the regression suite also
checks a nonzero body-to-stability rate transformation. The five unpaired
model inventory records remain visible with zero targets and no passes.

## Why the remaining computations now finish

The [initial expanded replay](isae-ae3-native-adapter-20261111.md) stopped with
229 passes and 401 uncomputed values. Several capped workers had already saved
converged equilibria and all 29 base physical checks. A first checkpoint-only
control then spent 13.665 seconds verifying source files and another 7.369
seconds importing modules, leaving too little of the unchanged worker budget.

The new [checkpoint runner](../../scripts/replay_isae_ae3_checkpoint.py) accepts
only a completed coefficient comparison with identical model, mesh, physical
condition, source hashes and numerical policy. It restores the exact saved
state and performs all auxiliary calculations afresh. It starts **no cold
equilibrium solve**. The original solve, restored residual and physical checks
remain attributed to their original files; incomplete auxiliary attempts are
not reused.

The supervisor performs full canonical source and artifact verification before
and after the worker. The worker additionally verifies its supervisor-supplied
request digest, literal model bytes, checkpoint bytes and restored operator
identity. Its raw output has status `pending_source_audit`; it receives no
numerical/reference acceptance until the supervisor's final audit succeeds.
The complete tangent, scaled rank check, shared factorization, seven input and
output refinements, linear residuals and apparent-mass recovery checks remain.
No matrix terms, reference values or gates are omitted.

All 11 checkpoint workers completed. Their measured worker times were
**3.386–14.759 wall seconds**, **1.662–6.569 CPU seconds**, and at most
**145,248 KiB peak RSS**. These timings exclude supervisor file auditing.
Each numerical child still has **one BLAS thread, 512 MiB address space,
15 CPU seconds and 25 wall seconds**. The three outstanding coefficient
equilibria also completed through the original bounded cold-solve route.

Two overlapping controls compare the new route with completed cold-route
outputs: all **48 mass/rate values** and all **90 full auxiliary values** agree
exactly, including unchanged reference decisions. They add no native votes.
Sixteen new checkpoint regressions pass; the previous 67 adapter/integration
regressions remain current. That is **83 distinct passing regression tests**.

The final 30 computed records contain **870 base-check records and 258
auxiliary checks**, all passing. Some base checks are inherited from the same
verified solve; these are not 870 independent numerical solves. Maximum fresh
base residual is **3.676e−13**. Across the retained history, all **41 numerical
children were reaped**: 32 completed and nine timed out, including overlapping
controls. No timeout remains the selected result for a native target.

## Remaining differences

Finite coefficient predictions agree with the earlier complete coefficient
replay within **1.475e−17** absolute difference. The higher pass count comes
from computed coverage, with no physical-model correction in this change.

Among failed coefficient comparisons, median Cl error is **51.42%**
(23.38–182.83%) and failed CX median error is **51.04%** (36.84–61.35%).
The 77 failed derivatives with reference magnitude above 1e−8 have median
**54.85%** error, range **7.52–6187.60%**. The largest percentage is `CYr` at
the last speed: reference 0.000010, prediction 0.000628760. The remaining tiny
derivative failure retains its original absolute tolerance.

The completed derivative data exposes a useful distinction:

| Native derivative | Passing speeds |
|---|---:|
| `CLa` — lift versus alpha | 6/6 |
| `Cma` — pitch moment versus alpha | 6/6 |
| `Clp` — roll damping | 6/6 |
| `CldF1` — aileron rolling effectiveness | 0/6 |
| `Clu` — rolling moment versus fractional speed | 0/6 |
| `CYa` — side force versus alpha | 0/6 |
| `CLb` — lift versus sideslip | 0/6 |

This pattern supports investigating the control/operating-constraint convention
and deformed geometry; it does not establish a unique cause. The complete
42-channel derivative comparison is retained, including all zero and small
targets. No experiment is substituted for an archived ASWING value.

Of the 78 failed mass/inertia fields, **55 have reference magnitude <=1e−8**
and keep the original absolute gate. The other 23 have median relative error
**228.63%** (40.66–583.19%). The largest absolute mass discrepancy is
`apparent_mass_yz`: reference −2.019e−5, prediction +6.90740077e−5, difference
**8.9264e−5** in the native mass unit. Small cross terms need to be assessed
with their dimensional values, alongside the dominant tensor entries.

The remaining **113 unavailable embedded values** still lack uniquely paired
producing inputs/control conventions. Original ASWING, modified ASWING-m and
experimental results remain distinct. Exact historical `MM` constraints,
original model/build identity and the ASWING-m Reynolds-dependent inputs are
open. The [authoritative reference index](aswing-authoritative-references.md)
and checksummed source catalog were consulted; the established source/setup
qualifications in the initial adapter report are retained.

## Reproduction and evidence

For a native coefficient equilibrium, use the existing bounded runner. For an
auxiliary target, point the checkpoint runner at a run containing its completed
nominal-80 coefficient state. Each invocation executes one numerical job:

```sh
.venv/bin/python scripts/replay_isae_ae3_checkpoint.py \
  --output-dir artifacts/isae/ae3-new-checkpoint-run \
  --base-run artifacts/isae/ae3-native-adapter-20261111 \
  --job-pattern '*004-derivatives'
```

For operating point 6, the authenticated coefficient base is in
`artifacts/isae/ae3-native-completion-20261111`. Existing result directories
are never overwritten. Code/setup changes require a new plan.

- [Combined assessment](../../artifacts/isae/ae3-checkpoint-completion-r2-20261111/assessment.json): all 725 targets, latest selected results, strict/5% decisions, failed attempts, error statistics and source hashes.
- [Execution/test review](../../artifacts/isae/ae3-checkpoint-completion-r2-20261111/execution-review.json): 83-test provenance, exact source continuity and operation accounting.
- [Mass/rate control](../../artifacts/isae/ae3-checkpoint-completion-r2-20261111/control-parity.json) and [derivative control](../../artifacts/isae/ae3-checkpoint-completion-r2-20261111/derivative-control-parity.json): zero-difference comparisons.
- Original partial replay, capped attempts and the first checkpoint candidate remain unchanged in their respective artifact directories.
