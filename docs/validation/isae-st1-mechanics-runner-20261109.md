# ST-1 recurring mechanics runner

The reviewed ST-1 mechanics comparisons now have an explicit recurring-runner
scope, `st1-mechanics`: 201 static coordinates and 22 named modal frequencies.
It is separate from the original 200-field archive inventory. The accepted
status remains **201/201 static and 20/22 modal**; this integration adds no pass.

The runner derives all 72 job inputs from original sources and the documented
physical-property reconstructions. Their normalized input tokens match all
72 previously reviewed models. Current production code is pinned for each new
run; historical production hashes are not a prerequisite for rerunning tests.
Source/reference pins, original targets, physical checks, mode identification
and mesh checks remain required. Refinements and unloaded states add no votes.

All **50 source/contract tests** pass across
`tests/test_isae_st1_mechanics.py` and `tests/test_isae_suite_st1.py`.
The new integrated static smoke job, coupled blade at −45° and 0.4 kg, passes
all three coordinate comparisons at 5%, plus equilibrium and refinement gates.
It executes unloaded/loaded 100-interval states and a loaded 200-interval state.
Its original strict comparisons remain in the raw result; the suite applies
the existing provisional 5% rule separately.

The paired modal runner smoke and complete 72-job replay have **not** been run.
The user switched focus to ST-2 after the static smoke completed. The existing
20 modal matches come from the prior reviewed studies, not a fresh full-runner
replay. Both unresolved reference correspondences remain required.

The bounded entry point is:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  npm run test:isae:st1:mechanics -- --output-dir <new-run-directory>
```

It uses one worker and runs at most one new job per invocation; `--resume`
continues an existing run. The default job timeout is 25 seconds. The physical
worker also enforces 512 MiB address space and 15 seconds CPU. No browser build
or solver equation changed.

Evidence: [integration record](../../artifacts/isae/st1-mechanics-runner-20261109/checks.json),
[partial smoke report](../../artifacts/isae/st1-mechanics-runner-20261109/smoke/report.json),
[portable reviewed-input fixture](isae-st1-mechanics-reviewed-inputs.json),
[documented source transformations](isae-st1-mechanics-inputs.json).
