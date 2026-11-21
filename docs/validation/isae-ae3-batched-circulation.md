# AE-3 circulation batching and full-mesh comparison

The isolated R5 candidate completed the matched 320-to-640-interval comparison. The change in the native rolling-moment/control derivative is **2.1591607%, which fails the unchanged 1% criterion**. Numerical execution passed 40/40 guards and the saved-matrix audit passed 276/276 checks; these are separate from the scientific mesh verdict. AE-3 remains pending.

| Native Cl derivative per file flap setting | Value |
| --- | ---: |
| Reused R3, 320 intervals | −0.00023513016902356907 |
| New R5, 640 intervals | −0.00023016063112549847 |
| Absolute change / absolute fine value | 0.02159160701710491 |
| Predeclared limit | 0.01 — FAIL |

R5 changes only `circulation_tangent.py` and `derivative_circulation.py` relative to the isolated R4 source. It assembles the complete analytic circulation block in contiguous column batches when the existing workspace estimate requires it. Every analytic term, checked centered probe, speed-floor/branch guard and all-or-none fallback remains. The final API still uses the default step 1e-5, fixed-acceleration standard/stability response, control.1 and p parameters, original equations and two fixed same-factor residual corrections.

The new 640-interval call retained all 16,675 derivative residual evaluations and used ten 64-column batches. Its complete block has 8,332 rows, 640 columns and 42,659,840 bytes. The original unbatched estimate is 160,808,960 bytes; the returned-block-plus-batch estimate is 58,740,736 bytes, below the unchanged 134,217,728-byte cap. The native fine capture records 39,731,384 field bytes, below their separate 67,108,864-byte cap. These are admission/storage quantities, not a claim that total process memory fits either cap.

Before reusing the R3 derivative, a fresh R5 321-node network passed 14/14 capture checks. Its complete 4,172-by-320 analytic Gamma block is bit-identical to the immutable R3 block; geometry, zero state, condition and base residual also match. This made two physical residual evaluations and one analytic capture, with no derivative API, equilibrium or linear solve. The separate prior R3-to-R4 input/geometry proof is preserved. The 320 derivative itself was not rerun or relabeled R5.

The fine run passed fresh pre/post full residual checks at zero. Its largest ordinary full linear residual is 5.998535002049721e-13, below 1e-8. The column-scaled reciprocal-condition **lower bound** is 2.4361378484142426e-10, above the unchanged 1e-10 gate; exact rcond is null. The saved audit independently recomputed one signed J·dx and one absolute-magnitude product, each with two RHS, without another solve, factorization, rank decomposition or physical evaluation. Raw CSC matrices, centered and analytic Gamma columns, partials, directions, residuals and all diagnostics remain archived.

The API took 218.96 seconds; its owned child took 225.62 seconds in total and reported a process peak of 429,850,624 bytes. These single observations are not a speedup benchmark or a browser full-solve timing.

| Additional isolated evidence | Result |
| --- | --- |
| Native batching regressions | 41 distinct cases passed across preserved revisions; 46 executions include five retained harness failures |
| Actual Pyodide, complete final small suite | 41/41 passed, zero skips |
| Six small actual-WASM APIs versus six native reference APIs | 57,122 numeric comparisons passed at 2e-8 absolute plus 2e-8 relative |
| Separate actual-WASM 641-node analytic capture | Complete 8,332-by-640 block, ten batches, original caps and owner restoration passed |

Native harness revisions corrected an omitted zero-incidence fixture setting and a nullable-output comparison; their initial failures remain. The first combined WASM run completed all small tests/comparisons, then failed before any large construction because its harness incorrectly converted the portable mesh wrapper key `default` to an integer. That outcome remains failed. A separate corrected large capture passed with exactly one network, two residuals and one analytic capture. That WASM capture records 39,644,300 field bytes, separately from the native fine capture above. Neither large capture executed centered probes, a full Jacobian, derivative API or solve; the helper's retained-probe metadata describes its API contract. No large-block native/WASM numerical comparison or full 640 browser solve is claimed.

The previous [R4 storage-fallback failure](isae-ae3-full-mesh.md) is unchanged: its derivative completed using the centered fallback, so the planned method guard failed and no matched mesh verdict was assigned there. The earlier [R3 arithmetic report](derivative-sparse-refinement.md), its three old p/body-z output-parity failures, the R3 input-cap failure and all five older mesh failures remain intact. R5 adds this new 2.1591607% mesh failure; it does not replace the historical verdicts.

The refined grid splits every 320 interval at its saved Glauert sample, preserving root, endpoints, prior stations and control breaks. It is not uniform material-coordinate halving. Aerodynamic, structural and load-transfer grids change together. One pair cannot establish continuum error, convergence order, isolated error cause or experimental agreement. The 640 case still requires its own nonlinear-control consistency checks; the previous 320 checks do not transfer. No original ASWING executable is available. Coverage remains **17 partial, 24 pending, 0 fully validated**.

The candidate remains isolated with 109 modules. ROOT source and the public kernel remain the prior 108-module version; this study makes no source promotion, hosted release or download update. The proposed [machine-readable report](isae-ae3-batched-circulation.json) and [evidence ZIP](isae-ae3-batched-circulation-20261024-evidence.zip) retain the tests, raw results, runtime pins, failures and lifecycle receipts. Historical absolute-path dependencies and reproduction limits are listed in the package; the preceding R3/R4 archives are referenced rather than duplicated.
