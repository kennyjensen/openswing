# Saving and resuming unfinished equilibrium in the workbench

2026-11-08 UTC. **Settings → Resumable equilibrium** now exposes the existing
[checked continuation API](isae-ffwt4-continuation-20261106.md). This completes
the previously missing workbench controls for that API, without changing its
equations, numerical gates or supported formulations. The ordinary **Run
analysis** button still requests a complete solve.

Select structural static or mounted equilibrium, then **Start resumable
solve**. Each job advances one accepted load step. The panel displays applied
load percentage, accepted-step count and physical residual. **Advance one load
step** continues; **Save solve progress** downloads the exact unfinished state,
ASW source, mesh, numerical policy and workbench settings. Save explicitly before
closing the page: unfinished progress is not automatically stored.

**Load solve progress** restores the saved case and settings, without solving.
Resume then invokes the core's existing checksum, source/mesh/operator/kernel,
solver-context and rebuilt physical-residual checks. Editing solve inputs blocks
resume; **Restore saved solve settings** restores the stored configuration.
Cancellation discards the interrupted step and retains the preceding checkpoint.
Errors do not silently start a new solve or overwrite that checkpoint.

The progress envelope is `openswing-equilibrium-progress`, version 1; its
checkpoint remains the existing `openswing-static-continuation`, version 1.

Follow-up, 2026-11-11: [operating-target origins](steady-continuation-operating-origin-20261111.md)
are now included in the checksummed checkpoint so acceleration/net-load solves
resume the same continuation path. Native checks pass; the browser/WASM bundle
has not been rebuilt or reverified for that correction. Old-kernel checkpoints
still require a new solve under the existing exact-kernel rule.
Partial loads have no normal result, CSV, computed-equilibrium export or time
launch. Only a checked full-load equilibrium reaches ordinary result controls.
Progress imports and converged-equilibrium/time-checkpoint imports are distinct.
Imported progress is not declared physically verified until the core checks it
on resume.

## Supported scope and limits

The UI accepts cold structural or mounted jobs under the midpoint, source
zero-offset, source-section, source-coupled and source-airflow operators already
supported by the continuation API. Feedback, derivative requests and enabled
initial-equilibrium guesses must be off. Prescribed conditions and canonical
acceleration/net-load constraints are supported; other trim targets use the
ordinary complete-solve route. An accepted-step budget is **not a wall-clock
limit**. A kernel update deliberately invalidates old unfinished checkpoints.

This is a usability improvement for bounded investigations. It does not fix
SA-11's rejected winglet-root flow, authenticate an unknown native setup or add
an ISAE comparison pass. SA-11 remains **163/9,184 at 5%**; SA-2 stall work stays
deferred. No comparison fractions, scope selections or progress events changed.

## Verification

All jobs were serial. Chromium used one worker and one BLAS thread with a
bounded JavaScript heap. The development Vite server supplied current modules;
this evidence is not a new packaged-release/offline-build audit.

- **39 JavaScript checks pass**, including six new progress-envelope tests and
  the existing project, numerical-policy and saved-state reader checks.
- **Structural browser workflow passes:** source-section axial cantilever with
  independent exact extension `m*g/(EA/L) = 0.004 m`. Saved boundaries at 25%,
  50% and 75% lead to a full-load residual **4.207e-17**. Final nodes, elements
  and equilibrium packet equal the uninterrupted solve exactly. The test checks
  page reload/import, exact input restoration without solving, changed-input
  rejection, disabled resume during unapplied mesh edits, cancellation, core
  checksum rejection and withholding normal
  result controls. The 390-pixel mobile panel has no horizontal overflow; its
  screenshot was inspected.
- **Mounted source-airflow browser workflow passes:** two lifting beams with
  structural offsets, a sprung joint and nonzero circulation. Boundaries at
  25%, 53.7711% and 81.8607% lead to a full-load residual **5.493e-16**. All node
  positions and CL/CD/CDi/Cm are identical to the ordinary solve in the retained
  results. The test requires coefficient/position agreement to 10 decimal places.
- **Existing SA-11 browser regression passes:** both Mach-invalid roots remain
  marked and exportable as failure diagnostics; no accepted CL/CSV is exposed.
  Input changes clear the diagnostics, and the lower-speed control still solves.

Evidence: [unit log](../../artifacts/steady-progress-workbench-20261108/unit.log),
[structural browser result](../../artifacts/steady-progress-workbench-20261108/browser-4.json),
[mounted browser result](../../artifacts/steady-progress-workbench-20261108/browser-3.json).
The [SA-11 regression](../../artifacts/steady-progress-workbench-20261108/sa11-browser.json)
is retained separately.
Their respective directories contain complete requests, saved boundaries and
final/reference results. Both browser runs record kernel fingerprint
`21091e2e869ed8cfa4de935f51b07e228746ea524b3caa970b85eaa5726ee909`.
The retained `browser-2.json` is a failed test-harness attempt that accessed
`result.coefficients.CL` instead of the existing top-level `result.CL` after
successful convergence. Correcting the assertion required no solver change.

Implementation: `web/steady-progress-data.js`, `web/steady-progress.js`, and the
bounded branch in `web/main.js`. Tests: `tests/steady-progress.test.mjs` and
`tests/browser/steady-progress.spec.js`, with explicit synthetic ASW fixtures.
