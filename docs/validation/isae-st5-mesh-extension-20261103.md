# ST-5 mesh convergence extension

All four supported ST-5 load cases now pass the existing **0.1% mesh-change limit** on the two finer grids: **56/56 measures**. All eight new cold solves and fresh saved-state residual checks pass. This resolves the selected mesh-convergence failures, not the remaining archived-ASWING differences.

The original three grids and failed comparisons remain recorded. Two exact bisections add 304/256 and 608/512 intervals on the forward/rear beams. Original loads, equations, duplicate output rows, field recovery and tolerances are unchanged; no parameter is fitted to the archive.

| Load case | 280→560 intervals | 560→1,120 intervals | Finest median archived error: Z / twist / bending moment |
|---|---:|---:|---|
| 20lb_80_20 | 13/14; max 0.13050% | 14/14; max 0.03263% | 0.4107% / 0.7938% / 1.013% |
| 20lb_90_10 | 13/14; max 0.15459% | 14/14; max 0.03865% | 0.2952% / 0.9694% / 0.7812% |
| 30lb_90_10 | 13/14; max 0.15381% | 14/14; max 0.03846% | 0.3102% / 0.9804% / 0.644% |
| 30lb_80_20 | 13/14; max 0.13336% | 14/14; max 0.03335% | 0.3925% / 0.89% / 1.024% |

Mesh percentages use the maximum absolute change over all 80 original rows divided by the corresponding fine-grid deformation envelope. Reference percentages above use all nonzero archived values with magnitude greater than 1e-8 on the finest grid. Near-zero values still receive the original absolute/printed-precision comparison. Finer convergence does not imply closer agreement with a historical finite-grid calculation.

The original registered count remains **13,833/25,920 scalar matches**. This extension adds a separate 17,280 scalar comparisons across eight grids; they are not added silently to the registered score:

| Supplemental field group | Printed-precision matches | Interpretation |
|---|---:|---|
| Structural fields | 842/8,960 | Physical output comparison; no complete row matches. |
| Conditional zero fields | 6,400/6,400 | No evidence of nonzero response. |
| Echoed input fields | 1,138/1,280 | Input/display agreement. |
| Unresolved f_reac display | 28/640 | Diagnostic only; exporter law unresolved. |

The first 608/512 attempt was rejected before solving by the application’s 512-interval input ceiling. The ceiling is now 1,024 intervals per beam, with matching global/per-beam controls. The numerical expressions are unchanged. All 13 retained grid settings and all 509 previously accepted integer counts normalize identically under the old and new code; 42 focused discretization tests pass. The Fourier-mode limit and default resolution are unchanged. The rejected attempt is retained.

The actual built browser performs one offline cold solve of `20lb_90_10` on 608/512 intervals in **22.04 s**. All **1201/1201 audit checks** pass, including both 1,024-interval controls, exact mesh import, full native-result parity, portable project export/reopen, byte-identical restored results and no recomputation. Maximum parity error is **3.8975e-05** of the unchanged `2e-8 + 2e-8*abs(reference)` allowance across **264,567 numeric fields**. GPU rendering is disabled for this bounded run; it is not a 3D rendering check.

The initial browser audit stopped after the successful solve because its older expected request omitted the now-explicit `strut_mode: bilateral`. The pinned native bridge uses the same bilateral default, both results contain no struts, and every native result field passes the original numerical parity limit. The completed browser result is retained unchanged. A second, saved-only browser session finishes export/reopen checks with zero additional solves. Both attempts are recorded; no physical tolerance or result field was removed.

Jobs run serially with one BLAS thread. Each native child has a 180-second wall limit and 512 MiB address-space limit. Receipts include source hashes, resource use and process cleanup. The retained first refinement used the old input validator; exact gate-only compatibility is verified before reuse. No completed solve was repeated.

Historical mesh/startup/exporter identity, other original configurations and whole-family/native agreement remain unresolved. Other structural families retain the [initial ST-1–ST-6 results](isae-st1-st6-current-20261103.md); ST-4 has a separate [independent equation audit](isae-st4-transfer-diagnostic-20261103.md).

[Machine report](isae-st5-mesh-extension-20261103.json). Raw plans, all comparisons, retained failed attempt and browser receipts: `artifacts/isae/st5-mesh-extension-20261103/`.
