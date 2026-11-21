# Bode response transfer: candidate workaround

**Superseded later the same day:** the user subsequently reported a negative
typed-array length. The [`getBuffer` workaround was replaced with bounded
records and unsigned address handling](bode-result-memory-20261114.md).
The observations below describe the earlier candidate and its checks.

The user reports `Unexpected token … is not valid JSON` after the Bode
calculation has finished. This narrows the investigation to result handling,
but the original failure has **not been reproduced** and its underlying cause
is not established. No completed browser solve is claimed for this change.

The existing server at `http://127.0.0.1:5173` returned a valid source-bundle
JSON document matching all 142 Python modules exactly. Its runtime lockfile
was valid JSON; the five runtime files matched the installed Pyodide package,
and the NumPy/SciPy wheels matched their lockfile checksums. These observations
do not establish what was cached in the user's browser.

## Change

The worker now asks the unchanged `run_worker_json` serializer for UTF-8 bytes
instead of implicitly converting its large temporary Python string to a
JavaScript string. It retains the Python bytes proxy and buffer view until
synchronous decoding has produced a JavaScript-owned string. Both handles
are released in `finally`, including invalid UTF-8, malformed JSON and status
callback failures. It invokes the calculation only once; it does not retry a
solve on transfer failure. This follows the buffer ownership API in the
[Pyodide 314.0.7 documentation](https://pyodide.org/en/stable/usage/type-conversions.html#using-python-buffer-objects-from-javascript)
and the installed `node_modules/pyodide/pyodide.d.ts` declarations.

Bode completion now shows “Reading completed Bode response…”. JSON errors
identify source loading, runtime identification, solver response or the
initial-disturbance settings field. The original exception and its cause are
logged in the worker console. Response envelopes are checked before use;
structured aerodynamic rejection evidence and array-valued constraint
responses are preserved. The equations, Python serializer and aircraft input
are unchanged. This transport workaround does not resolve the separate
disagreement with Drela's reference Bode curves.

## Checks and limitations

Five focused JavaScript test definitions plus loader checks passed 50
assertions in the tool's JavaScript isolate. They cover a 2 MiB payload,
Unicode, exact response contents, buffer lifetime, malformed data, cleanup,
one calculation per request, structured rejections and actionable field
errors. The isolate uses an injected strict UTF-8 codec and small assertion
adapter; it does **not** execute browser TextDecoder or actual Pyodide.
The normal Node test files are retained but were not launched under the
existing browser/build/Node execution hold. The initial syntax-check wrapper
needed a correction for an export-from declaration; that harness failure is
recorded in the receipt.

Both native tests in `tests/test_worker_boundary.py` passed in 5.08 seconds
wall time, 2.48 seconds CPU, peak RSS 102,624 KiB. The process used one BLAS
thread and 512 MiB address-space / 15 CPU-second / 25 wall-second limits and
is reaped. These test the existing serializer and structured rejection
behavior, not the actual WASM transport.

The [verification receipt](../../artifacts/bode-json-transfer-20261114/verification.json)
pins the six changed/new implementation and test files. No Node/Vite test,
browser, build or background solver was started. The running development
server was left in place; packaged downloads were not rebuilt. ISAE fractions
and comparison scopes are unchanged.

Next confirmation is a full page reload and a retry of the user's Bode case.
If it still fails, the stage-specific message and original worker-console
exception distinguish malformed returned bytes from an internal runtime
failure. Do not report this as a confirmed browser fix until that check passes.

## Development-page resets during a 41-point solve

The user subsequently reported the app resetting partway through a 41-point
calculation. Frontend edits were being made against their running development
server at the same time. The installed Vite client handles `full-reload` by
calling `pageReload()`, and the server's `onHMRUpdate` dispatch is gated by
`serverConfig.hmr !== false`. Thus these edits can interrupt an active browser
worker; this is a concrete reset mechanism, but no captured browser event
proves which reset the user saw.

`vite.config.js` now sets `server.hmr: false`. The existing server restarted
through its own configuration watcher and continued serving the app and new
buffer helper with HTTP 200. No additional server or browser was launched.
Future app-code edits require a manual refresh instead of automatically
discarding an in-progress calculation. Editing Vite configuration itself can
still restart the server, so avoid configuration changes during user solves.

Forty-one samples are within the UI's allowed 2–200 range. Source inspection
shows one harmonic factorization at a time, while full output data accumulates
with the number of frequencies and selected inputs; the live sweep also copies
its report. Therefore memory pressure remains a plausible separate issue.
No 41-point browser memory benchmark has been run, and no sample limit or
physics setting has been changed. First retry the same case after one manual
refresh with automatic updates disabled; a subsequent reset needs browser
failure evidence rather than being attributed to sample count alone.
