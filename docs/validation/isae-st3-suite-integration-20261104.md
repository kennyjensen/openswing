# ST-3 modal suite integration

2026-11-04. All three original modal layups are now registered in the shared
ISAE suite at 64 and 128 cosine intervals. Six jobs cover **nine distinct
ASWING workbook frequencies**, repeated across two meshes. The existing
1,080-slot static comparison remains a separate job.

Reassessment of the six unchanged completed solves gives **16/18** matches
across both meshes and **8/9** at the finer mesh. All nine frequency mesh
checks pass at 0.1%. This reuses the original numerical results; it does not
claim six new executions. All 142 study pins and 24 retained evidence files
were verified before reassessment.

| Layup | Matches at 128 intervals | Remaining frequency error |
|---|---:|---|
| `0_3_90` | 2/3 | First frequency: 3.798389 versus 3.7 Hz, +2.659% |
| `p15_0` | 3/3 | None within recorded decimal intervals |
| `m15_0` | 3/3 | None within recorded decimal intervals |

One fresh `0_3_90`, 64-interval job completed through the serial shared runner.
Its three frequencies reproduce the retained results exactly:
3.798537876639406, 24.288304340795435 and 25.91405044315801 Hz.
It matches 2/3 references; the fresh equilibrium residual is 1.45e-16.
The worker exited zero and was reaped. The suite exits one because the broader
suite is unvalidated and this deliberately bounded batch leaves five jobs
unrun. The independent summarizer preserves those 15 unrun scalar slots.

The cold bridge solve took **27.68 s**, the complete worker **34.85 s**, and
the full invocation **84.90 s**. The remaining 50.05 s is outside the worker;
this timing does not separate catalog construction, source hashing, process
startup and report generation. It identifies suite overhead for profiling.

The adapter reads the original workbook cells directly, preserves their labels
and decimal tokens, and uses exact decimal interval comparisons. It selects
the first three positive frequencies from the fixed 12-mode local survey,
without matching roots to targets. Partial spectra, changed physical settings,
missing restoration evidence and altered targets are rejected. These modal
comparisons explicitly prohibit the provisional 3% relative allowance.

Validation: **17** new adapter/accounting tests and **165** selected existing
runner, summary and acceptance tests pass. An earlier broader batch reached
its 90-second cap without a reported failure and is not counted as completed.
All six saved-result reassessments and the fresh run's independent summary pass.
This changes validation tooling; no production equations or application assets
are changed.

These remain conditional **frequency-set** comparisons. Workbook labels
conflict with the primary source, and original medium, orientation, mesh and
startup settings are unavailable. Reported eigenvector backward errors are
checked, but the adapter does not independently reassemble the descriptor
pencil. Its mesh diagnostic checks frequency ranks; the prior study separately
retains mechanical-shape MAC checks. ST-3 is not fully validated.

Run a bounded fresh batch with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py --adapters st3_modal \
  --cases ST-3 --workers 1 --max-new-jobs 1 --timeout-seconds 90 \
  --relative-tolerance 0 --output-dir artifacts/isae/st3-modal-new
```

Add `--resume` with the same directory/settings to continue an unchanged plan.
Each batch runs at most one new job. The full family catalog remains visible.

[Earlier physical comparison](isae-st3-additional-20261104.md),
[integration results](isae-st3-suite-integration-20261104.json),
[saved-result reassessment](../../artifacts/isae/st3-suite-integration-20261104/saved-results.json),
[fresh suite report](../../artifacts/isae/st3-suite-integration-20261104/fresh/report.md).
