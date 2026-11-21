# SA-15 shared-runner comparison and drag breakdown

The explicit `sa15-declared-setup` comparison is now available in the shared
runner. All 26 new runs complete: **84/182 scalar comparisons pass at 5%**,
with all **312 numerical checks** passing. The independent summary verifies
the original sources, setup, numerical evidence and unchanged kernels. The
largest difference from the preceding standalone predictions is 1.11e-15.

The comparison retains all 13 original incidence tokens, both nominal 64/128
meshes and all seven archived columns. These are 91 distinct native scalar
targets, repeated on two meshes. The original blocked historical scope remains
separate: the version-specific `.set`, historical nodes and OPER output
identity have not been recovered. This is a declared reconstruction, not
whole-family validation. The [earlier setup record](isae-sa15-declared-setup-20261105.md)
describes every assumption.

| Output | Passes at 5% | Failed comparisons |
|---|---:|---|
| CD | 10/26 | Median 7.79%, maximum 16.63% |
| CL | 24/26 | Median 8.49%, maximum 8.81% |
| Cm | 26/26 | None |
| Span efficiency | 24/26 | Median 12.73%, maximum 13.40% |
| CY | 0/26 | Maximum absolute difference 2.61e-8 |
| Cl | 0/26 | Maximum absolute difference 6.96e-8 |
| Cn | 0/26 | Maximum absolute difference 1.37e-8 |

Of the 98 remaining failures, 78 compare tiny archived lateral residuals
against the symmetric solution's roundoff-level values. Percentages are
misleading for these channels. They remain in the denominator with their
existing acceptance rules. The other 20 failures concern CD, CL and efficiency.
All original printed-precision comparisons also remain recorded: 0/182 pass
that stricter test. Numerical and near-zero absolute gates are unchanged.

The drag investigation replays the six previously declared fine-grid states
at 0.227°, 5.350° and 12.338°, with current and frozen influences. It uses saved
circulation, literal section properties and the production filament formulas;
it separately reconstructs equations (67), (69), (70) and (204). All 48 checks
of geometry, velocities, stall residuals, individual strip forces and summed
drag pass. This does not independently validate the filament implementation or
identify native ASWING's startup settings. No new equilibrium or fitted
parameter is used in this diagnostic.

| Incidence | Influences | Near-field induced CD | Pressure CD | Stall-leakage CD | Total CD | Native total CD |
|---|---|---:|---:|---:|---:|---:|
| 0.227° | Current | 0.00825031 | 0.00490820 | <1e-9 | 0.01315850 | 0.0141577 |
| 0.227° | Frozen | 0.00824807 | 0.00490873 | <1e-9 | 0.01315679 | 0.0141577 |
| 5.350° | Current | 0.01820865 | 0.00485578 | 0.00233232 | 0.02539675 | 0.0273146 |
| 5.350° | Frozen | 0.01840717 | 0.00487280 | 0.00177317 | 0.02505315 | 0.0273146 |
| 12.338° | Current | 0.02176747 | 0.00481783 | 0.06126916 | 0.08785446 | 0.0753288 |
| 12.338° | Frozen | 0.02241391 | 0.00486185 | 0.04951643 | 0.07679219 | 0.0753288 |

Friction CD is zero in this literal model. The moderate-angle discrepancy
exists with negligible stall drag. At the highest angle, stall leakage is
69.74% of total drag; freezing influences reduces that component by 0.0117527,
while the other components increase slightly. Thus the high-angle sensitivity
is primarily in the smooth stall-leakage term. No strip must exceed its stated
section limit for this smooth law to contribute. The archive provides total CD,
so the missing native drag cannot yet be assigned uniquely to its components.
Neither frozen influences nor a Trefftz substitution is adopted as a fix.

Run small serial batches with the original reference cache present:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/run-isae-suite.py \
  --adapters extra_polars --cases SA-15 \
  --comparison-scope sa15-declared-setup \
  --job-pattern 'SA-15:declared:*' --workers 1 --max-new-jobs 8 \
  --timeout-seconds 45 --output-dir artifacts/isae/sa15-reproduction
```

Repeat that command with `--resume` until all 26 jobs finish, then run
`scripts/summarize-isae-suite.py --run artifacts/isae/sa15-reproduction --output-dir artifacts/isae/sa15-reproduction-summary`
with the same Python interpreter. A runner exit status indicating open
comparisons is expected while reference failures remain.

All 206 distinct Python regression checks pass (22 new and 184 existing).
The new tests check the complete scope, original blocked rows,
source and settings changes, full-wrench coefficient normalization, retained
zero-output failures, separate mesh groups and summary accounting. Production
physics and browser assets are unchanged in this registration step.

- [Machine-readable comparison and drag evidence](isae-sa15-suite-20261105.json)
- [Independent shared-runner summary](../../artifacts/isae/sa15-suite-20261105/analysis-final/summary.md)
- [Saved-field diagnostic](../../artifacts/isae/sa15-suite-20261105/drag-components.py)
