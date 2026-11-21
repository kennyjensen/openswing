# Running ISAE comparisons in small serial batches

The suite runner defaults to one worker. Each numerical subprocess has
`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` and `MKL_NUM_THREADS` set to `1`.
Use `--max-new-jobs 1` to finish at most one previously unfinished job and
then exit. This limits execution; it does not shrink the comparison plan or
turn pending outputs into passes. A job may contain multiple physical calls,
depending on its adapter; the limit is on registered jobs, not solver calls.

For example, declare both meshes for the SA-7 full-aircraft −5° comparison:

```sh
.venv/bin/python scripts/run-isae-suite.py \
  --adapters polars --cases SA-7 \
  --job-pattern 'SA-7:Tandem_GAW2_L163_G05:row001:*' \
  --max-new-jobs 1 --timeout-seconds 60 \
  --output-dir artifacts/isae/sa7-small-batch
```

Run the same command with `--resume` to execute the next unfinished job:

```sh
.venv/bin/python scripts/run-isae-suite.py \
  --adapters polars --cases SA-7 \
  --job-pattern 'SA-7:Tandem_GAW2_L163_G05:row001:*' \
  --max-new-jobs 1 --timeout-seconds 60 \
  --output-dir artifacts/isae/sa7-small-batch --resume
```

Keep the original selection, worker count, timeout, tolerance and code
unchanged when resuming. `--max-new-jobs` is a per-invocation limit and may
change without changing the plan. Without it, the runner executes all pending
selected jobs, still serially unless `--workers` is explicitly increased.

`progress.json` records the current active job, this invocation's scheduled
and started jobs, completed results and remaining work. `report.json` records
the completed batch separately from full-plan accounting. Completed failures
and timeouts are retained on resume; there are no automatic retries. Once
every selected job has a terminal result, another resume starts no worker.

The process still exits with status **1** while full-suite validation remains
incomplete, including when a limited batch finishes normally. Check the saved
report and individual process records to distinguish archived-output
differences, pending comparisons and worker failures. Do not automatically
retry the command based only on this suite-level exit status.

This execution policy does not establish the cause of the reported UserLAnd
disconnects. It changes no aerodynamic equations, numerical tolerances or
registered reference targets.
