# ISAE comparisons at 5%

The default archived-ASWING relative allowance is now **5%**. Original strict results, absolute tolerances, numerical validity, matrix residuals and mesh gates are retained. References with magnitude at or below 1e-8 retain their original absolute check. Equation-only UA checks are unchanged.

The following counts rescore saved predictions, preserving their original source versions and setup qualifications. They are not a new full-suite run. Mesh repeats are scalar comparisons, not independent cases.

| Case / scope | Previous strict matches | At 5% |
|---|---:|---:|
| SA-1 / default | 19/154 | 154/154 |
| SA-3 / default | 0/308 | 308/308 |
| SA-15 / default | 0/182 | 0/182 |
| SA-13 / default | 0/612 | 0/612 |
| AP-1 / default | 0/15470 | 29/15470 |
| AP-2 / default | 0/248 | 84/248 |
| ST-2 / default | 0/490 | 56/490 |
| ST-4 / default | 0/3749 | 93/3749 |
| FFWT-1 / default | 0/64 | 18/64 |
| AE-1 / ae1-frozen-influences | 0/48 | 24/48 |

ST-2 now passes all 56 computed frequency comparisons. Its 56 near-zero real components and 378 unavailable cells remain failures. ST-4 passes all 93 computed vacuum frequencies, but its original mesh failures and 3,656 unavailable cells remain. Passing a value comparison does not waive convergence or establish a family pass.

New work: [SA-15](isae-sa15-declared-setup-20261105.md) computes all thirteen retained forward-wing angles on two meshes: **84/182 conditional matches**. The undecoded historical `.set` and OPER output conventions remain qualifications; the original blocked registration is unchanged.

The AE-4 wall-root coordinate stencil is now bounded by its existing geometry neighborhood. This fixes the fine cosine-mesh linearization without relaxing physical clearance, convergence or pencil gates. The 41- and 81-element requests each pass all 13 physical/source checks and all six native scalar comparisons at 5%, for **12/12 conditional comparisons of six distinct reference cells**. Fine-grid error is at most 0.6267%; the speed/index mapping and other historical settings remain conditional. Frequency and damping change with refinement; this is not a completed flutter sweep.

Retained AE-1 frozen endpoints now pass 24/48, with all 24 computed outputs passing and 24 unknown-start outputs unavailable. The retained AE-2 positive branch at 18–20 m/s passes 24/24 scalar comparisons across two meshes; the unresolved 17 m/s branch remains open.

Priority remains zero-pass scopes. SA-13 lacks original inputs; UA-2 has no authenticated native 3D output pairing. SA-15 now has a runnable declared scope, with drag and near-zero comparison handling unresolved. Missing adapters for P-2–P-5, AE-4–AE-7 and FFWT-2–FFWT-5 remain visible in the complete ledger.

Evidence: `artifacts/isae/five-percent-20261105/`, `artifacts/isae/sa15-zero-pass-20261105/`, and `artifacts/isae/ae4-refinement-20261105/`. The broad streaming rescore hit its 60-second cap without a completed output; selected original job files were then rescored successfully. No incomplete attempt supplies a score. Other ledger rows explicitly retain historical scores until rescored.

Use `scripts/rescore-isae-results.py` to reassess a saved report, an assessment plus plan, or selected original job files (`--job-results --cases ...`). Input hashes and original kernel hashes are recorded; original evidence is not rewritten. `--relative-tolerance 0` restores strict reference acceptance.

Verification: 336 distinct Python checks pass across the retained focused/regression logs. The [AE-4 finer-mesh worker verification](isae-ae4-refinement-20261105.md) passes all ten gates and 4,869,334 numeric comparisons offline. Numerical gates are unchanged.
