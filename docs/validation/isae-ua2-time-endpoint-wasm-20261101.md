# UA-2 checkpoint repair: WebAssembly replay

Updated 2026-11-01. **The packaged browser kernel passes the endpoint-event check
and one actual UA-2 continuation step.** The replay passes under Node and in
the built app's actual browser worker. All 136 packaged modules match current
production source hashes. This is not a full eight-cycle browser trajectory
or native ASWING comparison.

The fixture uses the repaired quarter-cycle checkpoint and the next state from
the verified CPython continuation. It preserves the same explicit interpolation
and structural-operator policy. The initial replay request omitted those policy
fields and was correctly rejected; that failed attempt is retained.

| Check | Result |
|---|---|
| Rounded-endpoint event selection | Exact forcing knot retained. |
| Continuation | One accepted BDF2 step, zero rejected steps. |
| Nonlinear residual | 2.263e-13, below 1e-10. |
| Largest scaled CPython difference | 9.239e-09, below the declared 2e-8 cross-runtime limit; occurs in local acceleration. |
| Force / circulation-rate differences | 1.508e-15 / 2.498e-13. |
| Frame position, velocity, attitude and rates | Identical to the saved CPython result. |
| Node runtime plus computation | 11.90 seconds. |
| Built browser worker runtime plus computation | 21.48 seconds; same maximum scaled difference. |
| Built desktop/mobile startup | One test passes, covering both layouts and all four mobile tabs. |

The static build, source ZIP and local-download ZIP contain the same 136 solver
modules. Packaged runtime bytes match the tested runtime, and the local ZIP
contains the verified source ZIP. The source archive is 208.9 MiB and the local
archive is 236.0 MiB. These are code/runtime identity checks; the archives do not
include every later documentation update. The browser worker reports the three
loading stages: runtime, numerical libraries and solver. Initial browser-launch
failures came from incomplete host Chromium files and are retained separately;
the successful checks use a complete isolated Chromium installation.

The [CPython inclined periodic comparison](isae-ua2-incidence-periodic-20261101.md)
now passes all 17 accuracy gates. The full periodic browser trajectory remains
unverified. The event-filter repair changes neither the aerodynamic equations
nor the acceptance limits.

Evidence: [machine report](isae-ua2-time-endpoint-wasm-20261101.json),
[WASM test](../../scripts/test-isae-ua2-endpoint-wasm.mjs),
[portable fixture](../../tests/fixtures/isae-ua2-endpoint.json), and
[native regression and replay](isae-ua2-time-endpoint-fix-20261101.md).
Additional evidence: [actual browser worker](../../artifacts/isae/ua2-time-endpoint-fix-20261101/browser-worker.json),
[startup receipt](../../artifacts/isae/ua2-time-endpoint-fix-20261101/browser-startup-execution.json), and
[archive verification](../../artifacts/isae/ua2-time-endpoint-fix-20261101/distribution-verification.json).
