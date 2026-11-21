# Load-evaluation performance

The [2026-10-11 mounted follow-up](mounted-acceleration.md) records subsequent
mounted solver improvements. The inverse-history measurements below remain
specific to this earlier increment.

This increment preserves the physical residual, mesh, quadrature, finite-
difference stencils, precision and all acceptance checks. It makes three exact
changes: reuse the last section rotation-transfer matrices only when their full
input shapes, dtypes and bytes match; return the empty influence tensor directly
when there are no lifting sources; and use the existing NumPy-equivalent xyz
cross product at seven more dynamic-load/frame-motion call sites. Body and
engine calculations remain active in models without lifting surfaces.

The rotation cache stores a single entry inside the current NetworkMotion.
Changing rotations, sampling fractions or array layout cannot select obsolete
maps. Returned force and couple arrays never expose the stored maps. Independent
virtual-power checks exercise repeated loads, in-place rotations, changed
fractions, material frames and modified returned arrays.

A public curved-velocity inverse-history run, including cold completion, two
BDF steps, checkpoint replay and two resumed steps, retains its entire output
byte-for-byte: 383,124 bytes, with no excluded fields. Both runs make 13,821
observed InitialSystem residual calls. The two refinements, rank checks and
one-sided tests are unchanged. Independent force, acceleration, velocity and
position errors are identical. Instrumented native times were 192.139 seconds
before and 136.821 seconds after (CPU 186.988 and 134.054 seconds). These are
cProfile measurements on a shared host, not ordinary browser timings or a
performance guarantee. Cold inverse initialization still takes substantial time.

The default mounted wing retains its entire canonical native output, including
1,900 residual evaluations. Sequential native measurements were 26.039 seconds
before and 22.632 seconds after (CPU 24.386 and 22.002 seconds). This is an
additional improvement after the preceding mounted-tangent optimization; it
should not be confused with the historical 53.381-second original baseline.

All 138 selected native cases pass, including distributed real/apparent inertia,
energy balance, unsteady networks, propulsion, body flow, ground effects, frozen
influences and initialization. Two cases are new virtual-power checks. The exact
frozen candidate was tested, then copied and byte-verified in the main checkout.
Collection is 1,647 tests; a full current-suite pass is not claimed.

Packaged WASM runs the original and optimized 69-module kernels in the same
runtime. The complete mounted48 and curved4 cold/BDF/checkpoint/continuation
outputs match exactly, with no excluded fields. Original/candidate mounted
measurements were 43.840/49.709 seconds;
the curved-history workflows took 285.256/286.485 seconds.
These Node/WASM observations are separate from browser measurements. The
mounted sample was slower, and the curved sample showed no meaningful change;
these whole-run observations do not establish a WASM speedup. A separate
alternating-order probe on 40 identical non-equilibrium default48 states found
the optimized physical residual faster in each of four rounds: 3.370 versus
3.568 seconds total (about 5.6%). Every residual byte matched. This probe isolates
load-evaluation cost; it is not an end-to-end solve benchmark.

One actual production-browser workflow also passes. It selects mounted
equilibrium with the unchanged default48 request, solves offline, observes
tangent/load progress in the worker and UI, and exports the result. The full
export matches the preceding browser reference exactly except software
provenance; all 69 reported module hashes match this kernel. No evaluation
counter is excluded. Worker time was 42.113 seconds on the
shared host. The four mobile workspace tabs, 390-pixel layout and plots screenshot
were checked, with no page errors or external requests. The web source files
remain unchanged by this increment.

The first profiling harness used the filename profile.py and shadowed Python's
standard-library profile module. It failed during import before any scientific
call. The corrected filename and original failure are retained separately.

The complete ASWING feature/validation goal remains incomplete. This increment
changes evaluation cost; it does not establish new physical feature support.

The first WASM harness completed its mounted baseline, then rejected a requested
two-panel inverse-history model at the existing minimum-four-panel input guard.
No inverse physics ran in that attempt. The corrected runner removes that
override and uses the original four-panel checker, preserving all assertions
and numerical tolerances. The original attempt remains FAIL.

The first browser launch failed before navigation because the default cached
Chromium lacked its shared-library path. The corrected attempt uses the existing
workspace Chromium/Mesa setup; no application code or assertions changed.

The [evidence archive](load-reuse-performance-evidence.zip) contains the frozen
source versions, inputs, full outputs, profiles, test records, browser capture
and all failed harness/launcher attempts. Extract it and run `python verify.py` with
NumPy installed to check every payload hash, full-result equality and the
independent curved-motion recurrence without importing the numerical kernel.
See also the [machine-readable record](load-reuse-performance.json).
