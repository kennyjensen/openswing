# SA-11: the lower-winglet root-height mismatch is not the fix

2026-11-07. Temporarily aligning the lower-winglet roots with the main-wing
attachment height makes the rejected local velocities larger. It does not
resolve the Mach error. The supplied examples and original reference inputs
remain unchanged.

The main wing's root attachment is at z = 0.15257 m; both lower-winglet roots
are at z = 0.15250 m. In a temporary copy only, the two lower root z tokens
were changed from `1.525` to `1.5257`, before their existing 0.1 multiplier.
Only the z distributions of beams 4 and 5 change. All section inputs, physical
indices, joint definitions, forces, cores, tolerances and validity guards are
retained. No fitted parameter or alternative reference target is introduced.

All comparisons use 30 m/s, alpha 5 degrees, beta zero, automatic PG Mach,
pointwise circulation and the original per-beam cosine spacing.

| Influence setting | Requested intervals/beam | Original maximum local Mach | Height-aligned maximum local Mach |
|---|---:|---:|---:|
| Frozen | 48 | 10.357742 | 28.175673 |
| Frozen | 96 | 21.318853 | 124.002761 |
| Current wind | 48 | 3.048750 | 17.424532 |
| Current wind | 96 | 3.469369 | 66.873652 |

All eight states are rejected by the unchanged local-Mach guard. These numbers
describe invalid discrete-model states, not physical supersonic predictions or
reference-comparison results. This is a default-setting geometry diagnostic;
it is not a pre-stall validation or a stall-model modification.

At N48 with current-wind influences, the nearest dominant root-ray distance
barely changes: 0.0227921 to 0.0228032 mm. The circulation of that source strip,
however, rises from 0.242222 to 1.174215 m²/s. Thus the larger spike is not a
new, closer numerical encounter at that receiver: the solved circulation near
the connected corner changes substantially. Frozen N48 shows the same pattern,
with root circulation rising from 0.741487 to 1.773155 m²/s. The complete source
attribution and converged circulation residuals are retained for all rows.

This excludes simply closing the 70-micrometre root gap as a sufficient repair.
It also strengthens the need to resolve the force-velocity treatment at a sharp
connected lifting surface. The [preceding junction study](isae-sa11-winglet-junction-20261107.md)
already verified the published endpoint construction and identified the finite
streamwise segment represented by offset root trailing legs. Arbitrarily
changing a physical index or adding a chord-scale same-surface core would change
the documented model; this study supplies no basis for doing that.

## Reproduction and accounting

The [driver](../../scripts/verify-isae-sa11-winglet-root-height.py) can reproduce
all eight states from bundled inputs. Use a fresh output directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-isae-sa11-winglet-root-height.py \
  --output artifacts/isae/sa11-root-height-rerun
```

The executed run used one BLAS thread, an address-space cap and a 60-second
deadline. It completed all **eight fresh calls**, including four unchanged
baseline states. Those four exactly reproduce the previously saved rejection
diagnostics.

Baseline reuse was requested, but the initial driver compared JSON lists with
in-memory tuples and missed all four matches. The exact executed driver is
retained alongside the plan. The current driver normalizes condition comparison
through JSON and rejects a missing requested cache match before making physical
calls. A read-only check finds all four matches and rejects changed incidence;
no numerical run was repeated to check this recorder correction.

[Plan](../../artifacts/isae/sa11-winglet-root-height-20261107/plan.json),
[results](../../artifacts/isae/sa11-winglet-root-height-20261107/results.json),
[paired analysis](../../artifacts/isae/sa11-winglet-root-height-20261107/analysis.json),
[executed driver](../../artifacts/isae/sa11-winglet-root-height-20261107/driver-used.py),
[cache check](../../artifacts/isae/sa11-winglet-root-height-20261107/cache-match-check.json).

Production modules, supplied examples and ISAE counts/scopes are unchanged.
