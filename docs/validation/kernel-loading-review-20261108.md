# Pending kernel-loading implementation: source review

This work is **unverified**. Browser tests, builds and solver jobs remain stopped
after the [UserLAnd interruption](userland-test-interruption-20261108.md). The
previously checked downloadable ZIP has not been rebuilt. No loading speedup,
completed test run or new ISAE pass is claimed.

## Pending transport change

`scripts/kernel-sources.mjs` captures the Python module files as UTF-8 strings,
rejecting invalid UTF-8 or module names. `scripts/prepare.mjs` writes both the
individual source files and `kernel/sources.json` from the same capture. The
development middleware constructs that JSON from the current working sources.
The browser requests the bundle once with `cache: 'no-store'`; it rejects
malformed or duplicate entries and requires `__init__.py` and `bridge.py`.
There is no fallback to potentially stale public sources.

`web/worker.js` writes those source strings to the same Pyodide paths, imports
the same bridge and retains the existing source/runtime provenance calculation.
No Python solver equation was edited. Byte-preservation tests are written but
have not completed; equivalence still requires the actual packaged-worker check.

## Startup failure ordering

Source inspection found that the original concurrent startup could report a
source-download error, then later post “Loading numerical libraries” when the
runtime finished. The page accepts startup status messages independently of
request errors, so that late message could restore a loading spinner after the
request had already failed.

`web/kernel-startup.js` now coordinates runtime/source loading. It preserves
concurrent downloads and the three existing stage labels. Once a dependency
fails, late runtime completion skips library loading and emits no further
startup status. If libraries are already loading, their completion cannot
advance to solver preparation. The original error propagates to the worker's
existing request-error handler. A second dependency rejection is still handled
by the same `Promise.all`; it does not replace the first error.

Five test definitions in `tests/kernel-startup.test.mjs` cover successful
concurrency, source failure before runtime completion, source failure during
library loading, runtime/library errors and a late second failure. They mock
the runtime and do not import Vite, launch a browser or load WASM. **They have
not been run during the execution hold.**

## Static-app test isolation

`playwright.config.js` now suppresses its Vite `webServer` when
`OPENSWING_STATIC_APP` is selected. The static-app fixture already owns a small
HTTP server. Previously, omitting the separate `OPENSWING_BASE_URL` variable
would start Vite unnecessarily even for that fixture.

The interrupted benchmark explicitly set both variables, so this finding does
**not** explain that interruption. Its two retained pre-change exports are
incomplete benchmark evidence, not proof that the new transport is faster.

Verification remains outstanding: the lightweight JavaScript checks, packaged
source equality, successful offline browser execution and actual browser
startup failure display. No interrupted command should be automatically retried.
