# UserLAnd interruption during kernel-loading checks

The user reported repeated SSH disconnections and requested that the current
test stop. All browser benchmarks, Node/Vite tests and builds remain stopped.
Solver jobs were also stopped for the initial source-only investigation;
the later bounded SA-11 resumption is recorded below. Do not automatically retry the
interrupted commands when their execution handles disappear.

## Observations

- The most recent command ran `tests/kernel-sources.test.mjs` and
  `tests/dev-kernel.test.mjs` with Node's serial test-file option, a 192 MiB
  JavaScript heap limit and a 40-second timeout. The latter test imported Vite
  and created a real development server. This was a source-loading test, not an
  aerodynamic solve. Serial test files and a JavaScript heap limit do not cap
  the complete native process tree's resources.
- Three retained Node test logs in `artifacts/kernel-bundle-20261108/` are
  empty. The earlier browser benchmark retained two result exports, but its
  final report is empty. Neither run is being counted as a completed pass.
- At 15:59 UTC on 2026-11-08, the UserLAnd support process, PRoot and SSH server
  had been running for approximately 83 seconds. This supports the user's
  report of an environment restart, beyond an ordinary test assertion failure.
  Subsequent process inspection found no running test, browser, Vite or solver.
- PRoot's `kill-report.log` contains only the new session's start and one
  guest-origin signal 9. It does not identify the cause of the preceding
  environment exit. Reading Android's crash log returned no entries.
- Available memory was measured only after the restart. There is no retained
  evidence establishing an out-of-memory kill, native bundler fault or Android
  process-limit event as the cause.

## Resource reduction and verification hold

`tests/dev-kernel.test.mjs` now attaches the actual kernel middleware to a small
Node HTTP server instead of importing Vite. It retains the live source edits,
bundle/manifest contents, stale public-copy rejection, HEAD and cache-header
checks. A real public-file fallback also checks middleware fallthrough. This
removes the Vite bundler and watcher dependency from that unit test; it does
not claim to test Vite integration or resolve the platform crash.

The replacement test has not been executed while honoring the stop request.
The new one-request kernel-loading implementation is still unverified and has
not replaced the previously checked downloadable app. ISAE comparison counts
and solver equations have not changed. Further browser/build verification must
remain deferred while the crash is unresolved.

A subsequent [source-only review](kernel-loading-review-20261108.md) isolated
startup error ordering and removed automatic Vite startup from the static-app
test configuration. Those changes are unverified and are not evidence that the
UserLAnd crash cause has been found or fixed.

## Bounded SA-11 work after the source review

For the user's requested investigation of small ASW changes, three
[incidence diagnostics](isae-sa11-angle-response-20261108.md) subsequently ran
serially. Each process made one 64-interval Python solve with one BLAS thread,
no subprocesses and its own 512 MiB address-space, 15-second CPU and 25-second
wall limits. All completed normally, in 3.48–7.17 seconds including imports,
with reported peak RSS of 215–217 MiB. The original browser/build/Node commands
were not retried. This narrower work does not identify or resolve the earlier
environment crash, and the kernel-loading verification remains pending.
