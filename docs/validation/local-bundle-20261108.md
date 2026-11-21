# Extracted local-app verification, 2026-11-08

This checks the downloadable application independently of Vite's development
server. It does not change aerodynamic equations or establish new ISAE matches.
SA-11 remains **163/9,184 at 5%**, with its local-Mach discrepancy unresolved.

## Build and contents

`npm run build` completed with one BLAS thread and a 256 MiB Node heap limit.
The ordinary build excludes optional raw validation archives. Vite reported
the existing large JavaScript chunk warning; it completed successfully.

The checked `dist/openswing-local.zip` is **254,527,904 bytes** (242.7 MiB),
SHA-256 `a2d60ea49329c1a9d91afd3a18c5dc8d9ef18d4814911dde7673cf1ee5bbfc35`.
Its source download is 224,689,787 bytes, SHA-256
`8e2f59407942efcde32dd63e58c5e71f3ff68bf7edfcd6c1f40d4c3e2ac214db`.
These hashes identify this build, not every later file at the same path.

The entire ZIP was extracted into a separate directory. Streaming checks verify
the embedded source archive against its metadata, all **141 kernel modules**
against the working Python files, and **315 implementation/UI/example files**
inside the source archive against the working files. All packaged runtime files
match the prepared runtime, and NumPy/SciPy plus their dependency closure match
the runtime lock-file SHA-256 values. The extracted metadata identifies a local
distribution with no optional raw validation download.

## Browser scope

The test harness serves only the extracted files from a temporary loopback
HTTP server owned by each test. External requests are blocked before navigation;
requests and HTTP failures are recorded. There is no development-kernel fallback.
Each job uses one browser worker, one BLAS thread and the software rendering path.

The existing SA-11 workflow passed on the extracted app in **22.06 seconds**,
including startup and teardown. It checks rejected-root markers, partial force
accounting and JSON export, disabled complete-result exports, mobile layout,
clearing diagnostics after edits and recovery to a valid low-speed solve.
The desktop capture was inspected. No external request or failed HTTP response
was observed. This is a workflow duration, not a standalone solver benchmark.

Both save/resume workflows also passed:

| Workflow | Whole-test duration | Accepted load fractions | Final residual |
|---|---:|---|---:|
| Structural axial reference | 81.25 s | 0.25, 0.5, 0.75, 1 | 4.207e-17 |
| Mounted coupled source-airflow case | 43.87 s | 0.25, 0.537711, 0.818607, 1 | 5.493e-16 |

The structural workflow includes a page reload, cancellation, input restoration,
corrupt-checkpoint rejection, mobile controls and a fresh ordinary solve. Its
tip position agrees with the independent 2.004 input-length reference; resumed
nodes, elements and equilibrium state are exactly equal to the ordinary result.
The coupled case retains nonzero circulation in its saved checkpoint. Its
resumed nodes and CL/CD/CDi/Cm are exactly equal to the ordinary result. These
durations include all workflow actions and runtime restarts, not just solving.

All three exports identify the current 141-module kernel fingerprint
`1698150361100fc6d45b11f39bc1f6b60507c5f65384af2f47bae7133e9c2ba0`.
The SA-11 rejected-state details exactly match the preceding development-browser
record for the same request. The three workflows recorded 164, 474 and 162 local
requests respectively, with **zero external requests and zero HTTP failures**.
This demonstrates operation without internet access while the static loopback
server remains available; it does not claim the app can reload without a server.

## Evidence

Evidence lives in `artifacts/local-bundle-20261108/`: `build.log`,
`check_bundle.py`, `integrity.json`, `check_results.py`,
[verification.json](../../artifacts/local-bundle-20261108/verification.json),
the browser harness/configuration, reports, downloaded numerical records,
screenshots and per-test network logs. The browser
harness reuses `tests/browser/flow-failure.spec.js` and
`tests/browser/steady-progress.spec.js` directly, rather than mocking the worker.
The downloaded ZIP remains a development distribution; full ASWING parity and
the other requirements in `docs/REQUIREMENTS.md` remain incomplete.
This audit was written after the build and is not itself included in that
already checked source archive. No numerical implementation changed during it.
