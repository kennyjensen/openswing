# Lossless time-result transfer

The browser now shares exactly repeated checkpoint states, options and selected
descriptive metadata while transferring a computed time history. The saved
Daedalus C16 result shrinks from **22,713,890 to 15,628,686 bytes (31.19%)**.
All 26 snapshots and every numerical value survive exact Python and JavaScript
round trips. No equations, tolerances, time steps or output samples change.

This is a private worker format. The worker restores the existing result shape
before handing it to the interface. Shared objects survive the worker's
structured clone; editable standalone checkpoints receive independent copies.
Full JSON exports, saved projects and checkpoint files retain their existing
schemas. The interface now identifies the post-integration stage as preparing
plots and checkpoints.

The pool uses exact serialized contents, not numerical tolerances, timestamps
or neighboring snapshot indices. Internal adaptive midpoints, Radau seeds,
before/after event states at equal times, historical BDF schemes, hinge charts,
controller history and original forcing offsets remain intact. Pool entries
are ordinary data; references are separate, checked paths. Invalid or
overlapping references are rejected before hydration changes the result.

Validation completed:

- **14 native tests**, including saved Radau, event, legacy spline and
  position-history checkpoints.
- **37 JavaScript tests**, including existing checkpoint/archive readers,
  shared references, signed zero, malformed references and checkpoint ownership.
- Exact full saved-C16 Python-to-JavaScript comparison, including all 26
  independently editable checkpoints and structured-clone preservation.
- **One complete offline browser scenario**: solves, plots, controller history,
  branching, checkpoint save/import, BDF continuation, replacement forcing,
  mobile layout and invalid-source rejection.
- Production build and local ZIP checks, with all 109 kernel modules identical
  in native, public and built directories.

The first browser launch lacked a local host library. A later run reached the
final export assertion but waited for a button hidden after its mobile-layout
check. That run was manually interrupted; its report and the corrected timing
interpretation are retained. Restoring the desktop viewport before the final
assertion fixed the test, and the complete scenario passed. No physics or
acceptance thresholds were changed to obtain the pass.

The production WebAssembly runtime was also measured in Node using the saved
Daedalus data. Three paired output-processing observations decreased from
1.190/1.149/1.083 seconds to 1.129/1.110/1.061 seconds (2.1–5.1%). Encoding itself
was slightly slower; reduced parsing cost offset it. These shared-host
measurements cover encoding, string transfer, parsing/hydration and structured
clone. They are **not complete browser-solve benchmarks or measurements of
browser heap usage**. The confirmed byte reduction includes removing JSON
whitespace; pooling alone reduces the whitespace-compacted payload by 27.51%.

Compaction occurs after integration, so it does not reduce checkpoint creation
cost or allocations inside the numerical integrator. Full exported JSON remains
expanded. The cause of the reported browser stall is not established.
Efficient, accurate transient integration and the
[Daedalus Bode mismatch](daedalus-rudder-four-outputs.md) remain unresolved.
The earlier [time-resolution study](daedalus-rudder-time-consistency.md) retains
its failed temporal-convergence result.

[Measurements and checks](time-result-storage.json) ·
[Source, saved data and test evidence](time-result-storage-20261025-evidence.zip).
The evidence bundle contains the complete baseline and compact wire data, codec
sources, raw measurements and browser reports. Study scripts retain their
original local paths; replay requires remapping those paths and installing the
declared test/runtime dependencies.
