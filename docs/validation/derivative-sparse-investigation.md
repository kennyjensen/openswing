# Sparse derivative investigation: output parity remains unresolved

The isolated sparse derivative candidate preserves the complete 320-interval AE-3 Jacobian and input partials, but **three physical output entries fail the unchanged comparison with the saved dense result**. Small native, WebAssembly and browser checks pass. The candidate is **not installed**, and **no 640-interval solve or mesh comparison has run**. ISAE coverage remains **17 partial / 24 pending / 0 fully validated**; AE-3 remains pending.

The candidate stores every nonzero from the complete centered probes, retains the existing analytic circulation replacement and all branch probes, and reuses one guarded sparse LU for certification and the physical responses. Nothing is pruned. The original full `J dx + R_p` gate remains `1e-8`; sparse acceptance uses a conservative reciprocal-condition lower bound above `1e-10`, with the original dense SVD fallback. The bound is labeled separately from an exact SVD estimate. Free-flight and feedback stay on the dense route. This investigation is separate from the already integrated [final equilibrium rank check](final-equilibrium-rank.md).

## Completed small-case evidence

| Check | Recorded outcome |
|---|---|
| Native helper/rank and existing derivative regressions | 155 and 48 passes in pinned root-run logs |
| Analytic-circulation regressions | 28 numerical passes; isolated import-path guard failure retained, corrected guard passes separately |
| Independent full API checks | Initial 9 passes/9 failures; the nine corrected fallback cases pass |
| Actual local Pyodide | 150 helper tests pass; two initial physical pairs pass; corrected source passes four sparse/fallback cases, 1,336 physical matrix values |
| Corrected isolated browser build | One test, two mounted current/frozen-influence cases; exact 108-module worker provenance; offline after initialization |
| Rank formatter | 8 JavaScript tests and full-main syntax check pass |

These counts overlap; they are not a unique test total. The fallback failures exposed a sparse-to-dense storage-order change in the SVD estimate, about `5e-17`. Explicit C-order conversion restores the original matrices, scales, responses and estimate; only the nine affected native cases were repeated. Reporting-helper failures and their saved-only repairs are retained. The browser exercises lower-bound text, exports, section plots and mobile layout, not a large-aircraft benchmark. The [machine-readable report](derivative-sparse-investigation.json) records revision-specific evidence and limitations.

## Matched 320-interval replay

The one native candidate call uses 4,172 unknowns and 123,455 stored Jacobian entries. Every physical Jacobian entry, input partial, checked centered circulation column and analytic circulation column matches the audited dense baseline exactly. Sparse column-norm reductions differ by at most `1.51e-15` relatively; their actual values and normalized matrices are retained. All normalized state-response entries pass the declared comparison.

The call takes **51.05 seconds**: 49.04 seconds assembling the complete centered Jacobian, 1.19 seconds scaling/certifying/factoring, and about 0.003 seconds for physical RHS solves and their full residual check. It records 8,355 residual evaluations and a process peak of 192,260 KiB. These are single native observations, without a new paired timing baseline or a 640-grid memory bound.

| Acceptance evidence | Outcome |
|---|---|
| Fresh zero-state residual before/after | Zero |
| Certified reciprocal-condition bound | `1.40136e-9`; exact estimate explicitly null |
| Maximum full linear residual | `2.09688e-12`, below `1e-8` |
| Native roll-control derivative | Difference `4.11290e-14`, below its unchanged `3.35130e-9` tight gate |
| All saved physical outputs | 81,703 numeric values compared; **three entries fail** `2e-8 + 2e-8 |reference|` |

The failed entries are body-z force in the `p` columns of distributed-aerodynamic, fluid and net wrenches. The dense values are about `+2.1939e-8`; the sparse values are about `−4.9202e-8`. Their differences are about `7.1141e-8`, up to 3.5571 times the allowed error. The saved audit is **217/218 checks passed**, with one grouped physical-comparison failure covering those three entries. It performs one signed and one absolute sparse two-RHS product, no solves. The failure remains recorded even though equation gates and the roll-control observable pass.

## Output and equation-accuracy diagnostics

A separate replay crosses both saved `p` directions with both recorded output steps: eight output evaluations plus one fresh-zero check. Each original direction/step pair reproduces its saved wrench outputs exactly. Swapping only the step changes the distributed body-z result by at most about `4.83e-13`; changing direction retains the approximately `7.114e-8` discrepancy. The tiny adaptive-step change therefore does not explain most of this mismatch in the crossed replay.

Two fixed same-LU corrections were then evaluated in a separately counted saved-matrix diagnostic. With 113-significant-bit residual accumulation, the `p` equation residual is `3.5720e-12` for the old dense direction, `2.0813e-12` for the unrefined sparse direction, and `2.0487e-13` after either correction. All already pass `1e-8`. The maximum componentwise backward-error statistic remains **1.0**; this is not evidence of uniformly small componentwise error.

A portable FMA/accurate-sum prototype passes 156 exact-rational helper comparisons in actual local Pyodide with zero fetch attempts. On the saved real matrix, its first corrected state matches the extended-precision correction bit-for-bit; the second differs by at most `1.56e-32`, and residuals differ by at most `9.86e-32`. These are bounded diagnostic observations. They do not establish universally exact residuals: product underflow and platform summation behavior remain explicit limits. Both measured runtimes provide 113 significant `longdouble` bits, without implying that every runtime does.

Finally, both prescribed refined directions were replayed at their normal output steps: four output evaluations plus one fresh-zero check. They give identical wrench responses, with body-z forces around **`6e-12`**. Nevertheless, **both still fail the old dense-output parity gate**, by up to **1.0967 times** its allowance. No direction was selected for best agreement, no tolerance changed, and no old failure became a pass. Lower equation residual and near-zero forces alone do not establish an absolute physical oracle.

## Remaining work and evidence

A subsequent refinement revision (r3) is implementation work only; **no r3 numerical validation or integration is included here**. Full API accuracy and ownership/fallback behavior need validation before source promotion or the prepared 640-grid run. New-grid nonlinear-control consistency would need its own independent cases; the [320-grid finite-control passes](isae-ae3-320-finite-control.md) do not transfer automatically.

All five earlier 1% mesh failures remain: **2.0773%, 7.1435%, 3.4688%, 4.1729%, and 6.3620%**. The [regional mesh evidence](isae-ae3-two-axis-mesh.md), experimental setup/observable gaps, and unavailable original ASWING executable comparison are unchanged. No continuum order, experimental acceptance or end-to-end speedup is claimed. ROOT source and its 108-module public kernel still match the prior installed version; the candidate UI/source and tests remain isolated. Hosted/download releases are unchanged.

The [evidence archive](derivative-sparse-investigation-20261024-evidence.zip) preserves source/input pins, raw matrices and outputs, all failures, plans and terminal process receipts. All 1,827 archive members passed the saved CRC and SHA verification; the archive is 35,928,963 bytes.
