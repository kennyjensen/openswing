# Default Daedalus trim startup

The preceding goal turn made concrete progress on file-read ordering and field
navigation. This turn checks a more consequential gap in the requested simple
steady-flight workflow: the existing completed-trim handoff evidence did not
prove convergence starting from the app's defaults.

## Exact request

The request test executes the production steady-flight configuration builder,
setting application and main.js Run analysis function. Literal flight defaults
come from the current main template. Dynamic pose/motion fields are initialized
as in the template loops, and fresh aircraft flap/power/circulation inputs are
zero. The test verifies the source against `public/examples/dae.asw` and the mesh
against `web/daedalus-mesh.json`. It does not use the checked project's solved
condition or equilibrium as the starting point.

The captured request has speed 21.981627296587927 ft/s, alpha 3°, beta 0°, initial
attitude [0°, 3°, 0°], flap and engine commands zero, standard atmosphere, automatic
Mach, frozen influences, the source-airflow policy and the regular 98-interval
mesh. Seven ordinary trim constraints enforce six load balances and zero flight
path. No initial equilibrium or controller is supplied. The request is retained
in `artifacts/default-steady-trim-20261115/request.json`.

## Resource-bounded native evidence

The authoritative index and checksummed catalog were consulted. This probe
changes no case inputs, equations, discretization or acceptance tolerance.
`scripts/check_default_steady_trim.py --tag cold-prefix-1` passes the captured
request through the real JSON bridge and native solver. It stops cooperatively
at a progress boundary after four CPU seconds within dispatch. A supervisor
also enforces one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall
seconds, and reaps the child.

The job exited 0 without timing out: 7.069524 CPU seconds including startup,
13.958471 wall seconds, 100,136 KiB peak RSS. Its source inputs remained unchanged.
The solver reached initial matrix assembly and reported 0, 618, 634, …, 794 of
1,324 columns before the cooperative stop. These are real assembly events, not
an estimate of overall completion. No load step, rank acceptance or final trim
convergence was established. No browser, Node, Vite startup or WASM run occurred.
No job remains running.

The native receipt is
`artifacts/default-steady-trim-20261115/cold-prefix-1/result.json`, with terminal
resource evidence beside it. The progress fixture in
`tests/fixtures/default-trim-progress.json` records that receipt's SHA-256.

## UI correction and remaining work

`mountedStatus` previously mapped every initial `static_tangent` event to the
same "Checking model constraints" message because applied load was zero.
It now shows the assembling column count; when assembly finishes, it reports
the initial constraint-independence check. Load continuation and final acceptance
retain their existing distinct messages and semantics. The native stop is
diagnostic-only; there is no time limit added to the application solver.

Eight request checks / 208 assertions and thirteen progress checks / 659
assertions pass in isolated V8. The latter replay the actual native events and
retain the existing steady, time, Bode, warm-correction and worker-throttling
checks. Total: 21 bodies / 867 assertions. This does not validate cold-trim
convergence or browser performance.

The next numerical question is whether the complete initial rank check and
subsequent load continuation converge from this exact request under the existing
resource constraints. The prior saved trim is not evidence for that question.
The full ASWING-equivalence goal remains open. No physics or ISAE status changed.

## Completed native trim and independent reload — 2026-11-15

The question above is now resolved for the native default request. The existing
geometry and circulation derivative decomposition was extended to ordinary
force/moment and flight-path trim rows. Flight path depends on the operating
condition and Earth attitude; its elastic-geometry and circulation derivatives
are zero. Its operating-variable derivatives remain in the full border. The
iteration residual omits unused wake/sensor report recovery for these rows;
full reporting still computes those quantities. Other target types retain their
full-residual fallback. The default optimization is limited to steady trim on
the exact source-airflow network class.

This follows the block organization discussed in Drela's steady technical
description §3.8 and §4.6. It retains the existing full local-plus-induced-field
derivative sum and production difference stencils. No physical equations,
operating inputs, mesh, lagging policy or acceptance tolerances were changed.
The authoritative catalog's steady-text checksum was reverified during the
reload audit.

On the 1,324-unknown Daedalus network, initial derivative assembly took about
1.00 CPU second with 45 residual calls. Sampled production columns agreed with
the original full-residual forward stencil to 6.05e-8 scaled error; a deformed,
fully loaded trial gave 2.51e-8. An independent fourth-order diagnostic gave
5.69e-11 maximum sampled-column error and 4.58e-10 across three complete geometry
directions at two steps. These are derivative checks, not aircraft validation.
Earlier failed diagnostic attempts remain in the artifact directory: they
exposed irrelevant sensor recovery during assembly and finite-step differences
between forward and centered/higher-order stencils. Acceptance was separated
by stencil, rather than loosening the error threshold.

The full cold trim, without any saved seed, then completed four continuation
steps in **12.39 CPU / 13.69 wall seconds**, with 182,368 KiB peak RSS and maximum
scaled residual **5.997751e-12**. Solved alpha is 3.250999°, beta 0.014923°,
pitch control −9.193199, yaw control 0.044753 and engine command 6.020264 in
the file's units. The receipt, unchanged request and serialized state are in
`artifacts/default-steady-trim-20261115/cold-trim-complete-1/`. Its generic
qualification incorrectly retained the earlier prefix-only text; the completed
solve fields and saved state are authoritative. Future receipts now distinguish
completed solves from cooperative prefixes. No prior receipt was rewritten.

The new `--stage audit` option reconstructs the original request through the
JSON bridge while intercepting the solve entry, restores the saved physical
fields with strict identity checks, and recomputes the full residual and nodal
load sums. It then reconstructs the serialized solved condition with free-flight
constraints and evaluates the dynamic equations at zero perturbation/rate.
It performs no matrix assembly, Newton solve or response sweep.

| Check | Result |
|---|---|
| Solver sources since the completed solve | All 143 hashes unchanged |
| Original steady network, full reporting | 5.997751e-12 maximum scaled residual |
| Full minus light iteration residual | Exactly zero in this check |
| Independently summed frame force | Maximum absolute component 4.21203e-11 input force units |
| Independently summed frame moment | Maximum absolute component 2.14296e-9 input moment units |
| Released free-flight equilibrium | 5.997751e-12 maximum scaled residual |
| 1,953-state free-flight dynamic equations at zero rate | 5.997751e-12 maximum scaled residual |
| Flight-path angle | 2.37e-13° |

Reload evidence is in `cold-trim-reload-1/`: 2.40 CPU / 5.42 wall seconds,
99,772 KiB peak RSS, normal exit and reaped child. The remaining automatic-default
derivative regressions ran as three separate serial jobs:
`trim-default-frozen-1/`, `trim-default-current-fields-1/`, and
`trim-default-fallback-1/`. All pass. The first two compare every column of a
small, deformed, rotating source-airflow network against independent full
residual differences; the third checks both automatic and explicitly requested
fallback against the original residual matrix. Each used one BLAS thread and
the existing 512 MiB / 15 CPU-second limits, with a 45-second wall cap. All
finished normally, reaped their child and retained unchanged pinned inputs.

The previous Editor turn made concrete UI progress. This follow-up closes its
unfinished native trim audit; it does not restart the held browser/build work.
Browser timing, actual response evolution from this particular cold trim and
complete ASWING feature equivalence remain unverified. ISAE fractions and scopes
are unchanged.
