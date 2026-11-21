# Bode transfer and output-selection repair

The user reported `Invalid typed array length: -3871677150` when completing a
41-point Bode calculation. The previous owned-buffer workaround used Pyodide's
`getBuffer('u8')`. The installed runtime passes wasm32 addresses as signed
integers, computes `largest_ptr - smallest_ptr`, then constructs a typed array.
A buffer straddling the 2 GiB address boundary can therefore get a negative
length. A small arithmetic regression reproduces the exact reported length
without allocating gigabytes. This identifies a concrete runtime defect
consistent with the error; no browser stack trace or complete user solve has
been captured. The earlier malformed-JSON error remains separately unconfirmed.

The worker now computes once with `run_worker_parts`, then transfers a header
and one complete frequency sample per record. No output fields are dropped,
rounded, recomputed or restricted to the selected plot. Frequency gaps and all
input responses remain present. A Python-owned byte array exposes its address
as a positive Python integer. JavaScript checks the range and reads from a
fresh heap view, synchronously, before releasing the owner. This bypasses the
broken signed-pointer arithmetic. It deliberately uses Pyodide's private
`_module.HEAPU8` compatibility boundary: recheck it on runtime upgrades. Both
properties are present in the pinned installed runtime. Transfer progress now
reports the number of completed Bode samples read.

The native `run_json` and `run_worker_json` APIs remain available. Compact time
results and structured aerodynamic errors keep their existing behavior.
Transfer failures clean up owners and never trigger another solve.

## Memory and exactness checks

A saved Daedalus harmonic state supplied one full output recovery, with no new
frequency solve. Its response uses 1,036,937 JSON bytes and approximately
2.59 MB of Python objects. Repeating this object at 41 frequencies isolates
serialization overhead; it deliberately does **not** simulate storage for 41
independently computed responses, multiple inputs, matrices or browser copies.

| Native 41-sample fixture | Previous full JSON | Per-sample transfer |
| --- | ---: | ---: |
| Process peak RSS | 142,820 KiB | 25,372 KiB |
| Increase over pre-encoding peak | 124,148 KiB | 6,728 KiB |
| Serialized bytes | 42,515,860 | 42,516,293 |

All 41 decoded samples equal their original complete dictionaries. The small
wire-size difference is record framing. The new measurement includes decoding
and equality checking, so elapsed times are not a pure encoder speed comparison.
The live sweep still retains its full outputs and copies reports; this change
does not establish that the full user case fits browser memory.

Twenty-one bounded native tests pass, covering real saved fixed/free Daedalus
outputs, gaps, Unicode, signed zero, invalid numbers, structured errors and
compact time results. The test process used one BLAS thread, 512 MiB address
space, 15 CPU seconds and 25 wall seconds; it finished and was reaped. The
serialization job was separately bounded and reaped.

Fourteen JavaScript test definitions pass 162 assertions in the tool's V8
isolate. They exercise actual component/helper source with a small mock DOM,
simulated heap growth, and an injected strict UTF-8 codec. The unused geometry
callback is stubbed. These are **not** browser, WebGL or Pyodide execution tests.
The initial synthetic JS fixture expected negative zero after JS's own
`JSON.stringify`, which normalizes it to zero; that test expectation was
corrected. Native Python-to-JSON signed-zero preservation is tested separately.

## Output selectors

Changing Output group only redraws saved values. Numerical-setting callbacks
now bind explicit setting IDs, independent of DOM placement. The event-level
regression cycles all eight groups for fixed and free saved results, checks no
invalidation or refinement calls, checks the 12 free-frame channels and CSV,
and confirms that changing the numerical sample count does invalidate.
The user's reported full-app group invalidation was not independently reproduced.

Fixed-aircraft results intentionally contain no flight-motion output block.
That group now displays a disabled, labeled placeholder and explains how to
compute free flight; changing the physical Response frame still requires a
new analysis. Other unavailable groups show an explanation as well. The
Playwright regression has been extended but remains unexecuted under the
browser-test hold.

Both WebGL and software renderers now tint surface mesh lines toward white
from the surface's assigned color, replacing the uniform dark green wireframe.

Receipts and immutable job logs are in
[`artifacts/bode-result-memory-20261114/`](../../artifacts/bode-result-memory-20261114/).
No new Node, Vite, browser, build, background solver or watcher was started.
No physics equations, aircraft examples, ISAE fractions or comparison scopes
changed. Packaged downloads have not been rebuilt. Reload the development
page to use the changes; a successful full browser solve remains to be confirmed.

## Subsequent browser report and retained-result copies

The user subsequently reported that Bode works in the browser, while its
Daedalus curves still differ from Drela's. This is confirmation of usability
for that run, not a captured memory benchmark or a numerical agreement claim;
the user did not specify the final sample count in that confirmation.

A later change removes additional Python container copies: the serial worker
borrows nested sweep data for read-only encoding, with a separate outer mapping
for dispatch metadata. Public native reports still deep-copy. Refinement builds
a new sample list and header while retaining existing immutable samples; failure
before commit leaves the old grid intact. This optimization has not yet received
separate browser confirmation or a memory measurement.

Twenty-five bounded native tests pass in the
[`ownership-checks-fixed` receipt](../../artifacts/bode-result-memory-20261114/ownership-checks-fixed/terminal.json),
including native ownership, exact mechanical response, transactional failures,
session expiry and wire reconstruction. An initial test-only syntax error was
fixed after its bounded process exited; its failed receipt is retained. Both
processes were reaped. No native numerical equations changed.
