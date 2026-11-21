# ST-4 Fourier geometry assembly

The original 64-interval, 16-Fourier-mode Weight7a modal case now completes in
**93.16 seconds**, versus **120.16 seconds** in the retained baseline
(22.5% less time). Both timings include imports, the complete public API
solve, output recovery and matrix JSON export. These are single cold runs on the
same device, not a statistical benchmark.

The full A and M matrices and all returned eigenvalues for this case are
**identical** to the saved pre-change result. The change removes redundant work;
it does not alter physical equations, mesh settings, Fourier count or tolerances.

## Cause and change

The local geometry coloring included projected flow-tangency rows. Fourier
projection makes these rows span an entire beam, preventing otherwise disjoint
mechanical columns from sharing a residual evaluation. However, the complete
flow-row derivatives are already computed separately and replace that partial.

`geometry_tangent.geometry_columns` now excludes only those subsequently
replaced flow rows from the local coloring. Mechanical, joint and load supports
remain intact. Full moving vortex, volume, jet and section-geometry derivatives
still supply the final flow equations. The global support map used elsewhere
is unchanged.

At 64 intervals this reduces local geometry groups from **396 to 18**. At 16
intervals it reduces them from **108 to 18**; instrumented geometry assembly
falls from 8.96 to
3.82 seconds. Small-case total startup
variation masks much of that gain, so it is not used to claim an overall speedup.
The initial large-case profile excluded JSON export; it is retained as a stage
profile and was followed by the exact-boundary benchmark above.

## Verification and limits

- **25 regression cases pass**: three focused Fourier derivative checks, six
  complete modal-pencil comparisons, twelve other full geometry derivative
  checks, and four steady/continuation/Newton checks.
- Saved 16- and 64-interval comparisons pass all **64 independent left/right
  eigenvector checks**. Maximum row-scaled matrix difference is 0;
  maximum scaled pole difference is 0. The 64-interval matrices and
  poles are identical. Full projected flow rows and M are identical at both sizes.
- The real offline browser solves the 16-interval, eight-mode Fourier case in
  **23.368 seconds**, agrees with the pre-change native poles to
  9.67e-13, and saves/reopens the solution exactly.
  This test disables graphics; it validates the workbench and WASM solver path.

All numerical children run serially with one BLAS thread, 180-second limits and
512 MiB address-space caps. The browser runs separately with one worker. The first broad geometry batch
reached its time cap after nine passes; only its three unfinished cases were
continued in a second serial batch. The first browser launch lacked `libnspr4`;
the replay uses the existing local Chromium/library bundle, with that initial
launch failure retained in the evidence directory.

This is an implementation/performance check, not new ASWING validation.
ST-4 retains **1/12 conditional airflow scalar matches**, solely the near-zero
imaginary component of a real root. Spatial convergence and historical numerical
settings remain unresolved; the [preceding spacing study](isae-st4-airflow-discretization-20261103.md)
retains all native differences. No family count or acceptance threshold changes.
Local-rate grouping and base-state setup remain separate performance costs.

The [portable evidence summary](isae-st4-fourier-assembly-20261103.json) is included in the source distribution.
Raw worktree evidence: [matrix comparison](../../artifacts/isae/st4-fourier-assembly-20261103/comparison.json),
[complete benchmark](../../artifacts/isae/st4-fourier-assembly-20261103/benchmark64/execution.json),
[stage profile](../../artifacts/isae/st4-fourier-assembly-20261103/after64/execution.json),
[browser replay](../../artifacts/isae/st4-fourier-assembly-20261103/browser.json).
