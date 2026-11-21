# FFWT-4 full-history time refinement

Follow-up: the [quarter-step study](isae-ffwt4-quarter-step-20261106.md) reduces
the adjacent increment change to 0.113%, but still does not meet 0.1%.
This page retains the original half-step comparison and its evidence.

The independently initialized half-step history passes **200/200** native
Fixed-1 root-moment comparisons at 5%, with median/max error **0.523%/0.641%**.
It covers all 398 steps through 2.9651 s, with no rejected steps and maximum
residual **9.713e-9**. These are the same 200 native targets as the earlier
history: the fixed-wing scope remains **200/1,600**, not 400/1,600.

The strict time-accuracy study passes **1/2** gates. Total moment changes by
less than 0.1% of its maximum magnitude, but its gust-induced increment does
not yet meet the same relative limit. **Time accuracy remains open.**

| Quantity | Maximum change | Change / fine-grid scale | 0.1% gate |
|---|---:|---:|---|
| Total root moment | 0.000729913 N m | 0.064161% | Pass |
| Moment increment from t=0 | 0.000729913 N m | 0.181851% | Fail |

The largest difference occurs at 0.6407 s, during gust entry. RMS differences
are 0.019316% of total-moment scale and 0.054747% of increment scale. The
increment gate prevents the steady load from hiding a dynamic error. Neither
gate is relaxed to the 5% native-reference allowance.

![Native agreement and time-refinement differences](../../artifacts/isae/ffwt4-refinement-20261106/plots-d2/comparison.png)

## Method and scope

The [original complete history](isae-ffwt4-gust-20261106.md) uses dt=0.0149 s.
The new history uses dt=0.00745 s from the initial equilibrium onward. The
literal model, nominal32 mesh, pointwise circulation, initial condition, gust,
physical parameters, equations and 1e-8 residual limit remain unchanged. BDF2
retains its one BDF1 startup step; checkpoint boundaries do not restart the
method. No state from the coarser transient seeds the finer history.

The predeclared 0.1% gates use maximum absolute differences over all 200 exact
common ticks. Each is normalized by the maximum corresponding fine-grid
magnitude over those ticks, separately for total moment and its increment
from t=0. The curves are not interpolated, phase-aligned or amplitude-fitted.
All 399 refined states, including the interleaved ones, undergo time, residual,
root-trace and integration-order checks. This is a root-moment accuracy study;
it does not certify every state variable or spatial convergence.

The native and refined peaks occur at the same compared tick, 0.9983 s:
1.13240 N m and 1.13762424 N m respectively. Their increments from t=0 are
0.400222 N m and 0.40137921 N m. No peak timing or baseline adjustment enters
the native pass count.

## Execution and evidence

Twenty successful serial jobs retain the full history, checkpoints and source
hashes. Each uses one BLAS thread, at most 20 steps, a 60-second process cap
and a 512 MiB address-space cap. Summed reported segment time is 426.64 s;
this includes solving, serialization and final evidence checks and is not a
controlled speed benchmark or end-to-end elapsed time.

One additional attempt, `d2-s140`, hit the process cap after saving its result
and checkpoint but before completing its verification report. Its observed
exit code is 124, and it is excluded from the accepted chain. The new helper
reuses already canonical evidence paths when hashing; every source is still
read and hashed before and after solving. The retry's request and entire
result are byte-for-byte identical to that attempt. The retry completes with
exit code 0; the original helper and failed attempt remain intact.

`scripts/assess-isae-ffwt4-refinement.py` independently checks the complete
checkpoint ancestry, every retained source/result hash, initial setup,
unchanged requests, order and boundary continuity. It reads one segment at a
time and runs no physical solve. The earlier partial assessment is preserved.
The 20 focused history/refinement tests pass, including rejection of missing
rows, wrong time grids, invalid traces, integration restarts and nonfinite
states, and a large-baseline example that must fail the increment gate.

Evidence under `artifacts/isae/ffwt4-refinement-20261106/`:

- `assessment-d2-s398.json`: complete native and time-accuracy comparisons.
- `serial-terminal.json`: observed process exits, including the failed attempt.
- `d2-s020` through `d2-s398`, using `d2-s140-retry` in place of `d2-s140`:
  full states, requests, plans, reports and checkpoints.
- `plots-d2/comparison.png` and `.svg`: native agreement and refinement plots.

Next: halve the time step again to resolve the remaining increment gate,
then establish mesh accuracy and add the seven other fixed histories, hinged
models and shared-suite registration. No whole-family validation is claimed.
