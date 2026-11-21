# Progress during saved-equilibrium correction

Saved-equilibrium correction now reports its Newton iteration and residual,
matrix-column assembly, and final equilibrium checks. Previously, a 120-second
Daedalus correction could leave the display on its initial loading message.
The matrix counter explicitly describes the current assembly and explains why
it can restart. It is not an overall completion percentage.

`equilibrium_state.correct` forwards observations already produced by Newton.
For the native dense fallback, it also forwards final-Jacobian progress. Custom
adapters and supplied final-tangent functions retain their existing interfaces.
The worker preserves assembly-start and completion messages while throttling
intermediate updates. The shared status renderer labels these events for both
frequency-response and time-response initialization, without advancing accepted
time or applied-load counters.

No solver equations, tolerances, derivative steps, acceptance checks or retry
decisions change. The focused native checks pass **22/22**, and JavaScript
checks pass **12/12**. Actual local Pyodide checks pass **40 assertions across
five small API attempts**. The WASM callback-on/off pair returns bitwise
identical raw states and identical 106 residual evaluations, three Newton
iterations, one tangent build and final rank diagnostics. All three observed
callback-failure phases preserve cleanup. Native tests additionally cover
ValueError, KeyboardInterrupt and adapters without a progress keyword.

The source and local public kernel are synchronized. The WASM run uses local
packages with zero network fetches; it is not a full Daedalus browser rerun or
a performance benchmark. Hosted releases and packaged downloads were not
rebuilt. [Machine-readable evidence](equilibrium-progress.json) records exact
source and test hashes, scope and process completion.
