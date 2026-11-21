# ST-2 mechanics in the regular validation runner

**Follow-up:** the [full recurring replay and combined-report integration](isae-st2-mechanics-complete-20261109.md)
are now complete: all 43 jobs pass 91/91 comparisons, and the importer gap
described below is resolved. This report retains the earlier integration record.

The regular ISAE runner now offers **`--comparison-scope st2-mechanics`**:
43 jobs covering the existing **77 static ordinates and 14 modal frequencies**.
The targets, input qualifications and numerical gates are unchanged. Omitting
that option retains the original 490-slot archive selection.

**73 focused source/contract and shared-runner checks pass.** Two fresh
integration jobs also pass: the maximum skin-on torsion load and the horizontal
modal configuration. The full 43-job rerun is still pending; the accepted
91/91 mechanics status continues to use the preceding reviewed studies.

| Fresh integration job | Reference matches at 5% | Maximum reference error | Refinement |
|---|---:|---:|---|
| Skin-on torsion, 2.8 kg: deflection and local twist | 2/2 | 0.2853% | Deflection 0.02023%; twist 0.00358% |
| Horizontal wing: seven modal frequencies | 7/7 | 0.8649% | Frequency change ≤0.3025%; shape MAC ≥0.999995 |

The static job computes loaded and unloaded states on both 40- and 80-node
meshes. The modal job uses both 80- and 160-node meshes and requires agreement
on both. Every state passes equilibrium and independent force/moment checks;
modal states also retain all twenty roots, both eigenvectors, sparse matrices
and their equation checks. No production module or original reference changed.

## Running a small batch

From the project directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py \
  --adapters st2 --comparison-scope st2-mechanics --cases ST-2 \
  --workers 1 --max-new-jobs 1 --timeout-seconds 120 \
  --output-dir artifacts/isae/st2-mechanics-current
```

Repeat the same command with `--resume` to execute the next unfinished job.
Use a new output directory after code or scope changes. The plan retains all
91 targets while unexecuted jobs remain required. `--plan-only` prepares the
plan without running physical models. The runner records the complete family
catalog, even when execution selects only ST-2.

Use the runner's own `report.json` and `report.md` for this selection. The
separate combined-summary importer, `summarize-isae-suite.py`, still assumes
the legacy ST-2 archive schema. A source-only check of all 43 mechanics jobs
raises `KeyError('reference_rows')`; its canonical selection and rendering
also need mechanics-scope support. That integration and the full recurring
replay are the next work. The [recorded gap](../../artifacts/isae/st2-mechanics-runner-20261109/combined-summary-gap.json)
does not affect the two verified runner reports or change their pass counts.

Each physical state runs in its own foreground child with one BLAS thread,
512 MiB address space, 15 CPU seconds and 25 wall seconds. Children run one at
a time. The parent imports scientific libraries for mode-shape comparison
only after both modal children exit. Multiple mechanics workers are rejected.
Timeouts stop the remaining states in that job, and the existing supervisor
terminates/reaps the worker process group. No retry or background solver is
started automatically.

The static and modal integration jobs took 41.36 and 34.20 seconds end to end.
Their summed solver times after imports were 2.70 and 16.34 seconds. The
remaining elapsed time includes cold process startup, source verification and
runner overhead; those contributions were not separately profiled. The
original full-catalog preparation took 25.28 seconds. Integration tests reuse
that verified catalog and exercise the actual supervisor, worker, strict
assessment and 5% report path. Peak child RSS was 174,352 KiB across these two
jobs. These are validation timings, not browser performance measurements.

## Preserved scientific contract

The [input manifest](isae-st2-mechanics-inputs.json) pins original sources and
the target definitions independently of production code. Each execution plan
then pins the current solver and every execution helper. The adapter reuses
the reviewed static and modal study executors with fresh plans; their
historical plans and results are not rewritten.

Static comparisons retain the explicit 8 mm tip-pylon reconstruction and the
original MATLAB load coordinates. Displacement subtracts the fresh unloaded
tip position; local section twist retains the original sign convention and
does not subtract its unloaded value. Maximum-load refinement includes a
fresh unloaded baseline on each mesh. The six curves retain all original
ordinates, including their shared conditions; those are scalar observations,
not 77 independent physical cases.

Modal inputs remain literal, including inactive null Weight records. They
retain self-weight equilibrium and source-density still-air inertia. The
first seven positive modes are selected by frequency order, with physical
family classification and one-to-one mass-weighted shape matching. No target
frequency chooses a root. The reported scalar is the less favorable of the
two mesh predictions, so the 5% allowance must hold on both meshes. Original
raw eigenvalue components remain in the artifacts.

The 1% mesh, 0.99 shape-MAC, equilibrium and eigen-equation gates are unchanged.
The source/contract tests reject missing baselines, missing mesh states,
altered targets, wrong mode identity, incomplete eigen-equation evidence,
nonfinite shape checks and substitution of only the better mesh result.
An additional saved-field replay reproduces all fourteen prior mode
classifications and mesh/shape measurements for both orientations. It adds no
fresh native matches. An AST comparison confirms the legacy adapter bodies
are unchanged after excluding the new explicit-scope dispatch branches.

Two preliminary test processes reached their 25-second wall limit during
the broader legacy-registration test. Both terminated before any physical
solve. Focused checks then completed within the same limits: the final batch
has 73 passes in 11.13 seconds. Thirty-two unrelated or broad archive checks
were excluded; no new claim is made for them. Browser/build tests remain held.

The primary **91/91**, supplementary spanwise **275/368**, and original
archive **56/490** remain distinct. The new runner adds no targets or progress
votes. Literal static-file attachment handling, exact historical settings,
legacy display outputs and full ST-2 compatibility remain open.

A final report-only correction keeps the legacy archive from receiving an
incorrect `static` scope label. Its focused regression passes. The retained
integration jobs preceded this correction; their execution and assessment
functions are unchanged, and reassessment produces identical mechanics
summaries. Their frozen plans and results remain intact.

Evidence: [prepared full plan](../../artifacts/isae/st2-mechanics-runner-20261109/full-plan/plan.json),
[static integration](../../artifacts/isae/st2-mechanics-runner-20261109/static-smoke/report.json),
[modal integration](../../artifacts/isae/st2-mechanics-runner-20261109/modal-smoke/report.json),
[73 test results](../../artifacts/isae/st2-mechanics-runner-20261109/final-regressions.xml),
[saved-field equivalence](../../artifacts/isae/st2-mechanics-runner-20261109/measurement-equivalence.json),
[adapter](../../scripts/isae_suite_st2_mechanics.py),
[contract tests](../../tests/test_isae_st2_mechanics.py).
