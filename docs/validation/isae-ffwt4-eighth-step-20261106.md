# FFWT-4 eighth-step time refinement

Fixed-1 now passes both declared root-moment time-accuracy gates on the latest
adjacent grids. The full dt=0.0018625 s history has 1,592 accepted steps through
2.9651 s, no rejected integration steps, and a maximum residual of
9.8114322e-9, below the unchanged 1e-8 limit. All 200 native values pass at 5%;
median/max reference error is **0.522889% / 0.680638%**.

This establishes the specified temporal comparison for this output at the
tested nominal32 mesh. Spatial accuracy, other state variables and the rest
of the FFWT-4 family remain unvalidated.

## Complete adjacent-grid comparison

Both total root moment and its increment from t=0 must change by no more than
0.1% of their respective fine-grid maximum magnitudes. The checks retain the
original 200 native times and also inspect every shared intermediate tick.
There is no interpolation, fitted amplitude or phase, extrapolation, or
shortened comparison window.

| Time-step pair (s) | Shared ticks | Maximum total-moment change | Maximum gust-increment change | Gates passed |
| --- | ---: | ---: | ---: | ---: |
| 0.00745 → 0.003725 | 399 | 0.039956% | 0.113288% | 1/2 |
| 0.003725 → 0.0018625 | 797 | 0.013163% | 0.037325% | **2/2** |
| Latest pair, original native times only | 200 | 0.013164% | 0.037331% | **2/2** |

The latest maximum absolute difference is **0.000149710974 N m**, at
**0.7599 s**. This differs from the previous pair's worst time, 1.72095 s;
earlier spot checks at that time and at the native peak were diagnostics,
not substitutes for the complete history comparison.

The original dt=0.0149 s run still fails the increment gate against the
eighth-step run: total-moment change is 0.093453%, while increment change is
0.265019%. Accordingly, `assessment-s1592.json` reports **1/2** for that
original-to-fine comparison, and `assessment-adjacent-d4-d8.json` reports
**2/2** for the latest adjacent pair. The coarse run is not retroactively
certified by the passing refined pair.

![Native history, reference error and adjacent time-grid differences](../../artifacts/isae/ffwt4-eighth-step-20261106/plots-adjacent-d4-d8/comparison.png)

[Vector plot](../../artifacts/isae/ffwt4-eighth-step-20261106/plots-adjacent-d4-d8/comparison.svg)
and [plot input hashes](../../artifacts/isae/ffwt4-eighth-step-20261106/plots-adjacent-d4-d8/inputs.json)
are retained with the comparison.

## Execution and evidence

Both histories start independently from the same equilibrium. The finer run
uses the same 138 byte-authenticated kernel files as the quarter-step run,
preserved in
`.reference/solver-snapshots/ffwt4-before-operator-cache-20261106/`.
The recent production cache optimization is not mixed into this comparison.
Original evidence hashes remain intact; the helper verifies archived files
before and after execution and records actual imported module paths.

The physical input remains the literal `FFWT_Fixed.asw` model, its first
driver gust and the nominal32 cosine mesh (63 nodes, 62 elements). Root
sensor 1 uses the left load trace. BDF1 is used only at the first physical
step, followed by BDF2; checkpoints retain both predecessor states. No
physical input, equation or numerical tolerance was changed to obtain a pass.

All **81 selected jobs** exited successfully. The two earlier 60-second
timeouts, `d8-s1400` and `d8-s1390`, remain saved and excluded. Two ten-step
retries replace those attempts, with a 90-second cap for imports, evidence
checks and serialization. Later jobs retain that cap. Every physical job
uses at most 20 steps, 512 MiB virtual address space and one BLAS thread.
The 83 attempted jobs are distinct from the 1,592 accepted physical steps;
wall-time caps do not count as integrator rejections.

Full snapshots are retained with lossless gzip compression: approximately
461 MiB compressed / 2,262 MiB uncompressed across the selected result files.
The independent audit reads every snapshot, checks physical times, residuals,
BDF order and sensor trace, authenticates source bytes and verifies the full
continuation chain. Its first read-only attempt hit a 120-second cap without
writing an assessment. The unchanged audit then completed in 128.19 seconds
under a 240-second cap, with the same memory/thread limits and no new solves.
Physical-job limits and numerical gates were not relaxed.

Thirty-one archive/refinement/audit tests pass. They cover altered or missing
kernel files, imports from the wrong package, changed evidence, lossless
compression, missing intermediate states, wrong clocks, restarted BDF order,
and errors hidden by a large static baseline or native-only sampling.

Evidence under `artifacts/isae/ffwt4-eighth-step-20261106/`:

- `serial-terminal.json` and `terminal-audit.json`: actual process exits and
  the contiguous successful continuation chain.
- `assessment-s1592.json`: full-state inspection and all 1,600 fixed-history
  target slots, with the uncomputed 1,400 retained.
- `assessment-adjacent-d4-d8.json`: independently authenticated complete-grid
  comparison and both unchanged accuracy gates.
- `assessment-terminals.json`: failed and successful read-only audit attempts.
- `audit-tests.xml`: 31 passing checks; `runtime-environment.json`: current
  runtime versions and thread settings, without inferring historical versions.

## Remaining scope

The tracked native fraction remains **200/1,600**. These are the same 200
targets compared on four time grids, counted once. Native reference agreement
and the latest temporal accuracy gate pass; neither establishes spatial
accuracy or complete physical validation. The other seven fixed histories,
hinged models, all-state accuracy, historical discretization and shared suite
registration remain open. No whole family or full-project completion is claimed.
