# ISAE coverage expansion: ST-2 and AP-1

Started 2026-10-26; completed 2026-10-27.

All 41 present families and 279 original models remain in the coverage ledger. Comparing every archived ASWING case is the development priority; experimental agreement is not required. The full collection is not yet reproduced.

The default plan now has **11 adapters, 3,136 jobs and 55,661 required scalar slots across selected scopes in 21 families**. 20 families still have no adapter; 19 families have an executable scope. These are scope counts, not validation percentages.

| New family | Registered scope | Fresh outcome |
|---|---|---|
| ST-2 | 396 native scalars, 10 separately qualified workbook cells, all six literal models | 11 explicitly blocked records; 0 numerical values |
| AP-1 | All six paired states, 1,000 span rows and one operating row, plus all 91 header outputs; two meshes for paired targets | 6 header jobs compute all 78 required values; 0 meet printed precision. 20 jobs remain blocked. |

The 37-job batch is terminal: six computed and 31 unsupported. Unsupported targets retain unavailable values and their original precision; none is reported as a pass. Header computations do not count as computed span rows. No entire family is declared validated. The older broad and SA-11/SA-12 runs remain separate because their kernels differ.

## What changed

The source structural solver now carries each engine with its attachment rotation and translation and transfers its force and moment once at that attachment. This follows theory Eqs.89–90 and 97–105. Shared power channels, propeller inflow and jet derivatives remain active; engine loads do not enter distributed mass or strip quadrature. AP-1 now uses this source equation route.

AP-1 compares aerodynamic Lift/CL/CD separately from net engine-inclusive force and moment. Literal reference dimensions and 500 W for each engine are preserved. All 13 header outputs are required. Current 150/300 nominal interval meshes and influence settings remain declared reconstructions; historical node locations and startup state are unresolved.

ST-2 still has literal attachment positions of .558 beyond the .55 beam endpoint. Exact generating states and modal settings also remain unresolved. All 46 static rows, 14 complex roots and separately qualified workbook cells are preserved. No original model is clamped or modified.

AP-1 span recovery still needs exact node/display interpretation, one-sided resultants and a_flap semantics. PROWIMd retains its literal zero lift slope and remains blocked. PROWIN and PROWIM.t retain their unresolved source pairing.

## Verification

Eight new engine tests and 148 focused Python tests pass. All 270 suite integration tests pass, including rejection of omitted physical checks, altered precision gates and false numerical claims for blocked outputs. Eighteen frontend policy tests and the local Vite build pass. The six initial original-model probes pass fresh residual and force/moment balance checks; native cold solves take 1.6–3.4 seconds. These timings exclude interpreter startup and report generation.

The exact browser worker request and real UI solve each match all 42,661 native numerical values, with maximum absolute difference 4.09e-12. Saved project and result restoration is byte-exact. All 122 kernel modules match source/public/dist; offline networking and browser errors are absent. A first-run harness-only gust assertion was corrected; its evidence is retained, and restoration finished with zero additional solves.

## Remaining coverage

Families without an adapter: SA-13, UA-1, UA-2, AP-2, P-2, P-3, P-4, P-5, ST-1, ST-6, AE-1, AE-3, AE-4, AE-5, AE-6, AE-7, FFWT-2, FFWT-3, FFWT-4, FFWT-5. Existing adapters also have unimplemented variants and outputs. Registration, numerical validity, refinement and ASWING agreement remain separate requirements.

| Family | Planned jobs | Executable jobs | Required scalar slots |
|---|---:|---:|---:|
| SA-1 | 22 | 22 | 154 |
| SA-10 | 324 | 270 | 2268 |
| SA-11 | 656 | 328 | 4592 |
| SA-12 | 1020 | 1020 | 4080 |
| SA-13 | 0 | 0 | 0 |
| SA-14 | 360 | 360 | 360 |
| SA-15 | 26 | 0 | 182 |
| SA-2 | 10 | 10 | 70 |
| SA-3 | 44 | 44 | 308 |
| SA-4 | 84 | 84 | 588 |
| SA-5 | 24 | 24 | 168 |
| SA-6 | 91 | 22 | 528 |
| SA-7 | 116 | 116 | 812 |
| SA-8 | 72 | 72 | 504 |
| UA-1 | 0 | 0 | 0 |
| UA-2 | 0 | 0 | 0 |
| AP-1 | 26 | 6 | 15470 |
| AP-2 | 0 | 0 | 0 |
| P-1 | 6 | 6 | 110 |
| P-2 | 0 | 0 | 0 |
| P-3 | 0 | 0 | 0 |
| P-4 | 0 | 0 | 0 |
| P-5 | 0 | 0 | 0 |
| ST-1 | 0 | 0 | 0 |
| ST-2 | 11 | 0 | 406 |
| ST-3 | 1 | 1 | 1080 |
| ST-4 | 42 | 5 | 3749 |
| ST-5 | 3 | 3 | 19440 |
| ST-6 | 0 | 0 | 0 |
| AE-1 | 0 | 0 | 0 |
| AE-2 | 182 | 174 | 728 |
| AE-3 | 0 | 0 | 0 |
| AE-4 | 0 | 0 | 0 |
| AE-5 | 0 | 0 | 0 |
| AE-6 | 0 | 0 | 0 |
| AE-7 | 0 | 0 | 0 |
| FFWT-1 | 16 | 16 | 64 |
| FFWT-2 | 0 | 0 | 0 |
| FFWT-3 | 0 | 0 | 0 |
| FFWT-4 | 0 | 0 | 0 |
| FFWT-5 | 0 | 0 | 0 |

[Batch results](isae-suite-st2-ap1-20261026/batch-report.md) · [Independent summary](isae-suite-st2-ap1-20261026/summary.md) · [Browser evidence](isae-suite-st2-ap1-20261026/browser-report.json) · [Family backlog](isae-suite-backlog.md).

The local source, browser kernel and frontend are updated. Hosted deployment and download archives are unchanged.

[Complete evidence archive](isae-suite-st2-ap1-20261026-evidence.zip) · [Archive checksum and verification](isae-suite-st2-ap1-20261026/archive-receipt.json).
