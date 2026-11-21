# AE-3 full-case comparison adapter

The adapter computes every numerical field in the six archived
`Straight_20O.fmat` files. It retains unresolved embedded curves in the required
total and distinguishes original ASWING, modified ASWING-m and experiment.
The native comparison is complete under the declared setup; agreement with
the full AE-3 reference is still incomplete.

| Compared output | Required comparisons | Passing at 5% |
|---|---:|---:|
| Six aerodynamic coefficients, two meshes | 72 | 50 |
| Stability and control derivatives | 252 | 174 |
| Mass, inertia and centroid fields | 252 | 174 |
| Normalized angular rates | 36 | 36 |
| Embedded original-ASWING and ASWING-m curves | 113 | 0; inputs unresolved |
| **Total** | **725** | **434** |

These are scalar comparisons, including 36 coefficient repeats on the second
mesh. The 612 computed entries comprise 576 distinct archived values. The
[audited result](isae-ae3-frozen-influences-20261111.md) and
[comparison CSV](../../artifacts/isae/ae3-frozen-primary-r2-20261111/comparisons.csv)
contain predictions, reference values, errors and acceptance decisions.
Unavailable predictions remain blank. A successful solve alone is not a pass.

## Implementation

- [Adapter](../../scripts/isae_suite_ae3.py): complete source ledger, original
  model/settings checks, equilibria, physical checks and output contracts.
- [Observables](../../scripts/isae_ae3_observables.py): seven derivative inputs
  share one complete coupled factorization; mass and rate fields are checked
  independently. Residual, rank and refinement gates remain unchanged.
- [Bounded runner](../../scripts/replay_isae_ae3_bounded.py): serial jobs with
  resumable, source-pinned plans and explicit uncomputed outcomes.
- [Checkpoint runner](../../scripts/replay_isae_ae3_checkpoint.py): reuse an
  identical accepted equilibrium for freshly calculated auxiliary outputs.
  It verifies model, mesh, physical settings, code and saved state before reuse.

Historical model identity, the MM constraint convention and embedded-curve
inputs remain qualified. The primary comparison uses the literal model and
documented frozen-influence default. Conditional diagnostic alternatives do
not contribute additional primary passes. See the
[authoritative reference index](aswing-authoritative-references.md).

## Run a new comparison

From the repository root, use a fresh output directory:

```sh
.venv/bin/python scripts/replay_isae_ae3_bounded.py \
  --output-dir artifacts/isae/ae3-my-replay --plan-only

.venv/bin/python scripts/replay_isae_ae3_bounded.py \
  --output-dir artifacts/isae/ae3-my-replay --max-new-jobs 1
```

Repeat the second command to advance one pending job. The runner sets one BLAS
thread and limits each numerical child to 512 MiB address space, 15 CPU seconds
and 25 wall seconds. It waits for and reaps the child before returning. Do not
run invocations concurrently. `summary.json` retains all 725 required entries,
including work not yet computed. A terminal timeout remains recorded; retry
in a new directory instead of overwriting it. Code or setup changes likewise
require a fresh plan.

For auxiliary work, first complete a matching nominal-80 coefficient job:

```sh
.venv/bin/python scripts/replay_isae_ae3_bounded.py \
  --output-dir artifacts/isae/ae3-my-bases \
  --job-pattern '*001-coefficients-m80'

.venv/bin/python scripts/replay_isae_ae3_checkpoint.py \
  --output-dir artifacts/isae/ae3-my-auxiliary \
  --base-run artifacts/isae/ae3-my-bases \
  --job-pattern '*001-derivatives'
```

Only invoke the second command after the base reports `computed`. Select
`mass_properties` or `normalized_rates` in place of `derivatives` for the other
groups, and operating-point numbers `002` through `006` for the other speeds.
Each checkpoint invocation selects exactly one job and preserves its evidence.
The base and auxiliary directories are separate runs; their files do not
automatically form a combined summary. The published 725-row CSV above is the
audited complete comparison.

## Final reporting check

The previously capped source-summary regression now exits successfully within
the same resource limits. It reconstructs the canonical source plan once per
summary and rejects edited operating settings even when both report and plan
are changed together. The runner now resolves sibling adapter imports when
loaded with `importlib`, as well as when invoked directly. This import-path
fix changes no numerical equations or reference decisions.

The [successful test receipt](../../artifacts/isae/ae3-adapter-final-check-r2-20261111/terminal.json)
records a normal exit in 22.03 supervised seconds. Earlier capped attempts and
the isolated import-error attempt remain preserved. This reporting check adds
no native-reference passes; the full numerical comparison was not rerun for
the import-path change.

Three additional registry/result-contract checks pass in 4.42 supervised
seconds. The [combined audit](../../artifacts/isae/ae3-adapter-final-check-r2-20261111/assessment.json)
retains the earlier 83-test evidence and these four current checks, giving 84
distinct regressions with passing evidence. It verifies the unchanged numerical
ledger and records source continuity; it is not a fresh run of all 84 tests.

## Diagnostic refinement follow-up

The [mesh/mode study](isae-ae3-mode-mesh-20261112.md) changes by less than 5%
on its last truncated-mode pairs, but retains an 8.97% difference from the
saved pointwise result and a 24.16% difference from native Cl at high speed.
Representation convergence remains open. It uses explicitly qualified
alternative control/constraint inputs and adds no votes to the 725-row primary
comparison. Native agreement and numerical refinement remain separate decisions.

The subsequent [current-kernel field audit](isae-ae3-representation-fields-20261112.md)
passes 47 cold-replay checks and 38 independent field/load checks, while
retaining the 8.97% coupled representation gap. The
[full coupled tangent check](isae-ae3-coupled-residual-response-20261112.md)
then passes all 38 checks and predicts this gap within 0.062%: structural
response amplifies the fixed-shape correction by 3.33×, and roll acceleration
adds another 3.17×. Aileron-boundary flow errors dominate the correction.
These diagnostics add no primary votes and do not resolve the archived-input
ambiguity or the primary native-reference mismatches.
