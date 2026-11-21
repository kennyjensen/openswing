# Remove force-normalization damping from the steady Newton step

The cold-equilibrium trace explains the 242 Jacobian assemblies observed in
the earlier [mechanical-derivative profile](source-static-mechanics-20261104.md):
one rank check plus 241 Newton iterations. The first quarter-load step needed
a 370.11 N axial resultant/reaction change and essentially zero deformation.
Its retained force scale was 10 N, so a generic unit-coordinate cap admitted
only 10 N per iteration. Three load attempts exhausted their 30 iterations
and unnecessarily retried smaller increments. None reused its factorization
because every damped step invalidated reuse.

`openswing/structured_static.py` now applies the existing unit-step limit to
nodal configuration and circulation coordinates. Internal forces, moments,
support/joint reactions and solved frame accelerations do not receive that
arbitrary normalization-dependent cap. The full physical merit search still
accepts every candidate. Hinge rotation limits, branch tracking, adaptive load
increments, rank checks and final residual thresholds are unchanged. This is
a correction to Newton globalization, not a change to the residual equations,
section constitutive law, physical input, coordinate scale or mesh.

Drela's Technical Description §3.8 describes the full Newton beam-group solve;
it does not supply the removed unit-force cap. This study establishes physical
equation agreement and convergence, not identity with an unavailable native
ASWING executable's iteration history.

| Same physical request | Before | After |
|---|---:|---:|
| N16 cold equilibrium, without modal assembly | 41.14 s | 0.643 s |
| Newton iterations | 241 | 4 |
| Reported residual evaluations | 5,091 | 108 |
| Rejected load attempts | 3 | 0 |
| N96 complete modal dispatch | 96.55 s | 33.48 s |
| N16 above-critical solve in the built browser | 44.02 s | 8.64 s |

These are single serial observations on the same device, not a general speedup
estimate. The equilibrium traces use the same light instrumentation. The older
heavily profiled N16 modal run is deliberately excluded from the timing table.
The N96 comparison starts after the earlier exact-mechanical-column optimization.

The saved equilibrium states differ by at most 7.43e-14 in their unchanged
coordinates. The new traced residual is 7.11e-15, below the unchanged 1e-12
acceptance target. At N96 the modal mass matrix is exactly unchanged; the
largest A-entry difference divided by the largest old entry is 1.92e-16.
Matched eigenvalues differ by at most 4.98e-15 on unit-floored relative scaling.

Three fresh complete cases pass the independent discrete beam-column verifier:
N16 at 0.5 and 1.5 times the continuum critical load, and N96 at 1.5 times.
All 12 poles, 24 left/right pencil checks and 3,144 mode-shape components pass,
as do fresh restored residuals, mass, straight geometry and wrench balances.
The prior nine-case fixed-fixed mesh study retains its recorded kernel hashes;
it has not been silently replaced or counted as a complete current-kernel rerun.
Small browser meshes establish discrete correctness, not continuum convergence.

Ten new regressions cover tension/compression across legacy, source-static and
source-dynamic operators, the actual initial gravity-override path, and large
extensions that must still damp. Ten existing source physical-solve tests pass,
including analytic moments, coupled bending, airloads and finite hinges. Six
nonlinear aircraft/fallback tests pass, including full-solver comparisons.
The initial-frame batch completed five checks before its 90-second cap; only
the three remaining checks were run afterward, and all passed. That interrupted
invocation is retained rather than reported as a successful complete batch.
The first new-test invocation had six fixture failures because construction
correctly scaled forces to its initially supplied gravity; the fixture was
corrected to reproduce the later gravity override while preserving coordinates.
All ten then passed; no production behavior or tolerance changed for that fix.

The kernel is synchronized into the production Vite build. Two complete offline
browser cases pass 426/426 harness checks, including source hashes, all physical
base and modal outputs, both eigenvector sides, stability, desktop/mobile plots,
and exact project/result save-reopen without another solve. The below-critical
browser solve takes 7.50 s. The complete two-case invocation takes 58.42 s.

Raw requests, source hashes, traces, matrices, reports, test receipts, browser
exports and screenshots are under
`artifacts/isae/equilibrium-step-limit-20261104/`. Native ASWING agreement,
original ST-6 fixture reconstruction and whole-project completion remain open.
