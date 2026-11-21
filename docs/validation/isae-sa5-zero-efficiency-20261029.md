# SA-5: exact-zero span-efficiency reporting

Updated 2026-10-29. OpenSwing now reports span efficiency as **zero for an
exactly unloaded, valid, nonempty lifting wake**, matching the native ASWING
SA-5 table. Previously those entries were unavailable because the efficiency
formula is `0/0`. This changes a reporting convention, not the aerodynamic
solution, force equations or acceptance tolerance.

## Reference evidence and scope

The original SA-5 table has two zero-incidence rows. Both print zero CL, CDi
and span efficiency; profile drag remains nonzero. Each row is checked at
200 and 400 intervals, producing four unavailable efficiency checks on each
spacing choice before this correction.

The ASWING Technical Description's Eq.211 defines
`(CLi² + CYi²)/(π AR CDi)` but leaves its zero-load convention unspecified.
The archived native table supplies that convention. Drela's retained JVL
`JTPFORC` routine also assigns zero efficiency for zero induced drag.
OpenSwing uses a narrower condition: circulation must be exactly zero in
every panel, CLi/CYi/CDi must all be zero, and the existing wake validation
must succeed with nonempty, nondegenerate projected panels and finite
reference inputs. There is no small-load threshold.

Nonzero circulation with zero drag remains undefined, including cancellation
between sheets or ground images. Empty or invalid geometry also retains its
previous behavior. Positive-drag efficiency uses exactly the previous formula.
The output description records the exact-unloaded reporting convention.

[Pinned native-output and Drela-source review](../../artifacts/isae/scn-curved-spacing-20261029/zero-efficiency-source-review.md)
and [isolated implementation diff](../../artifacts/isae/scn-curved-spacing-20261029/zero-efficiency-implementation/change.patch).

## Fresh complete SA-5 comparison

All **48 cold solves** completed successfully: 24 default-mesh jobs and
24 modified-spacing jobs. Counts, literal inputs, archived targets, solver
settings and numerical gates remain fixed. The modified arm reuses the
exact earlier node arrays. Each job gets one call, with two workers,
a 180-second cap per job and no retries.

| Spacing | Before correction | Fresh result | Recovered checks | Remaining failures |
|---|---:|---:|---:|---|
| Default cosine | 154/168 | **158/168** | 4 | Eight total-drag checks and two 18° CDi checks |
| Modified cosine | 162/168 | **166/168** | 4 | Two 18° CDi checks |

All eight recovered checks are the exact-zero efficiency outputs; no
previously passing output is lost. The 288 finite non-efficiency reference
outputs agree with the saved results within **1.50e-15 scaled difference**.
Earlier saved calls predate the analytic-Jacobian change, so bit-for-bit
agreement is not assumed. Maximum accepted residual is 4.97e-14, and
maximum section-normal Mach remains 0.726194/default and 0.979229/modified.
An independent saved-result review passes **5,486 checks with zero mismatches**,
including every process, acceptance comparison and reported gain/loss. It also
compares 267,696 saved physical scalars from the modified arm; their maximum
scaled change is 4.55e-13, within the predeclared diagnostic comparison bound.
No physical solves were repeated by the audit.

Modified-spacing CDi at 18° remains **3.306% low at 200 intervals** and
**3.350% low at 400 intervals**. Every other registered modified-spacing
output now passes at 3%. Default total-CD failures range from 3.34% to
5.27% low across their declared meshes. This reporting correction does
not address these physical differences or establish mesh convergence.

The refreshed SA-1–SA-5 totals are **1,190/1,288 default** and
**1,208/1,288 modified**; the other four cases retain their prior measured
counts. The full 3,179-job SA sweep was not repeated.

[Protocol](../../artifacts/isae/sa5-zero-efficiency-20261029/protocol.json)
and [all fresh results, numerical gates and output differences](../../artifacts/isae/sa5-zero-efficiency-20261029/report.json),
[execution receipt](../../artifacts/isae/sa5-zero-efficiency-20261029/execution-receipt.json)
and [independent review](../../artifacts/isae/sa5-zero-efficiency-20261029/independent-review.md).

## Focused checks and browser runtime

All **18 Trefftz tests pass**, including exact positive/negative zero,
circulation scaled to `1e-80`, nonzero sheet/image cancellation, unresolved
filaments, and empty/degenerate/invalid geometry. Existing continuum and
force-ledger tests also pass.

The packaged native/browser kernels were checked on nine prescribed fields
and two invalid inputs. All **40 numerical comparisons are identical**;
130 packaged modules match the native sources, and the WASM check makes
zero network requests. This is a focused reporting check, not a second full
SA-5 aerodynamic rerun in WASM.

- [Unit-test receipt](../../artifacts/isae/scn-curved-spacing-20261029/zero-efficiency-implementation/test-receipt.json).
- [Native/WASM results](../../artifacts/isae/sa5-zero-efficiency-20261029/runtime-wasm.json)
  and [terminal receipt](../../artifacts/isae/sa5-zero-efficiency-20261029/runtime-terminal-receipt.json).
