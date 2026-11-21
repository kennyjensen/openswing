# Faster free-flight Bode matrix assembly

The 32-panel Daedalus free-flight case now assembles its dynamic matrices in **73.46 seconds**, compared with **227.52 seconds** for the preceding implementation at the same saved trim. This is a native Python phase measurement, excluding trim, frequency solves and output recovery. It is one observation per implementation, not a controlled browser speed benchmark.

Previously, all local velocity and rotation-rate derivatives used separate full-residual differences whenever the aircraft had free-flight load equations. The optimized path now groups eligible columns while retaining each column's contribution to the global force and moment balances. It combines the exact local polynomial coefficient with the analytic incident-flow derivative. Engine-mount columns and unsupported constraints retain the original full stencils. Equations, accuracy thresholds, mesh and physical parameters are unchanged.

| Same saved 32-panel state | Previous | Updated |
|---|---:|---:|
| Dynamic matrix assembly | 227.52 s | 73.46 s |
| Full residual evaluations during assembly | 5,498 | 849 |
| Descriptor dimension | 3,719 | 3,719 |
| Optimized local velocity/rate columns | 0 | 1,176 |

The 1,176 columns form 27 groups, requiring 55 residual evaluations. Six engine-mount columns keep full stencils. This accounts exactly for the reduction: `5498 - 4*1176 + 55 = 849`. No trim was repeated and no matrix entries were pruned.

Every entry of both complete matrices was compared with the preceding saved result. The maximum absolute difference in `A` was `3.35e-12`, below the unchanged per-entry comparison allowance `2e-8*(1+abs(previous))`. The mass matrix `M` and rudder forcing vector were exactly equal, including stored numeric bytes. All four complex yaw-response comparisons at 0.1, 1, 8.90352 and 10 Hz passed; the largest relative difference was `6.61e-10`. Original harmonic condition and full-equation checks also passed. An independent saved-data review reproduced the matrix and response comparisons and residual accounting in 186 checks; it did not repeat the harmonic matrix products.

Fifteen focused native tests and eleven tests in actual Pyodide/WebAssembly passed. They cover free and mixed flight constraints, every eligible local-rate column against full residual differences at two widths, combined directions, damping, offset reference points, engine exclusions, unsupported-context fallbacks, exception cleanup, full matrix parity and recovered output fields. An earlier full-file native run reached its 240-second cap after seven original cases passed, during the eighth, exhaustive Daedalus case. That incomplete run is retained separately; the entire test file is not claimed to have passed.

Source and the local public kernel are synchronized. Reload the application to create a worker with the updated module. Downloadable bundles and hosted releases were not rebuilt. The runtime tests exercise Pyodide in Node; there is no new full Daedalus browser timing measurement.

This improves setup cost without resolving aircraft-validation questions. The [203-frequency three-mesh comparison](daedalus-rudder-mesh-sweep.md) still has a maximum sampled 16-to-32 complex change of 14.28%. Drela's reference operating point remains unidentified and its magnitude curve differs. No mesh-convergence, matched-reference or finite-amplitude nonlinear-step validation is claimed.

Reproduce the focused checks from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -m pytest -q tests/test_local_rate_tangent.py \
  -k 'not test_complete_local_motion_columns'
node scripts/test-local-rate-wasm.mjs
```

[Machine-readable results and evidence hashes](daedalus-rudder-local-rates.json).
