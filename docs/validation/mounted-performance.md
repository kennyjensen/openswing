# Mounted equilibrium performance

The [2026-10-11 follow-up](mounted-acceleration.md) records the latest mounted
solver measurements and accuracy checks.

This record covers the earlier 60-module optimization. The subsequent
[load-evaluation follow-up](load-reuse-performance.md) records the current
69-module native/WASM checks and a 42.113-second default browser observation.

The default request is the Rectangular research wing at 30 input L/T, alpha
5 degrees, beta 0, automatic Mach/standard atmosphere, 48 default intervals,
section stall enabled, full geometry-dependent aerodynamic influences and the
file's gravity. Required material stations produce 50 actual elements. Neither
the mesh nor the governing residual, floating-point precision, finite-difference
step (1e-6 times the original scale), continuation stages (four), Newton settings
or acceptance tolerance (1e-8) was reduced.

The implementation reuses a Newton tangent only when the same continuation
attempt requests exactly the same copied state. Cached matrices are isolated
from writable solver inputs. Internal section-wrench columns share finite-
difference residual evaluations only when their equation rows are disjoint:
local compatibility plus the two endpoint force/moment balances. Endpoint
uniqueness is checked. Custom constraints and sprung hinges retain individual
columns because they can read internal loads elsewhere. All geometric,
circulation, reaction and operating columns retain the original perturbations.

Stationary endpoint angular motion uses the exact zero-rate solution of the
same SO(3) interpolation, preserving the rotation, broadcasting and pi-domain
check. A specialized three-component cross product replaces general-axis
bookkeeping at audited call sites without changing component arithmetic,
numeric promotion or broadcasting. No global NumPy function is patched.

The browser reports tangent columns and load continuation targets through its
existing worker progress channel. This is solver activity, not a prediction of
remaining time. Controller, custom-target, allocation and saved-state correction
paths currently emit an initial load-stage notification only. Cancellation uses
the existing worker mechanism.

The first
candidate passed 52 existing tests and exact full-result comparisons. Its later
composition passed 95 tests (52 existing and 43 new); the final progress-only
increment passed two additional tests, including identical complete JSON with
and without observation. These are 97 distinct tests, not a full-suite run.
The initial combined test collection failed to find the shared test fixture
module in the isolated harness; no numerical test ran in that attempt. The
corrected harness preserved the unchanged candidate and all original assertions.

Fourteen independent original-versus-optimized cases compared 181,881 complete
Jacobian entries plus every residual entry at non-equilibrium states. All were
byte-identical, including signed zeros. Cases include rigid/flexible/powered
wings, a wing/body, sprung hinges, nonzero elastic motion and circulation rate,
ordinary operating targets, override options and a structural-sensor custom
constraint. The cross-product prototype separately passed 2,480 dtype,
broadcast, layout and exceptional-value comparisons.

Native measurements on the frozen numerical candidate (before the progress-only
increment) retained exact full JSON after removing only the top-level evaluation
counter:

| Case, 48 default intervals | Original | Optimized | Residual evaluations |
|---|---:|---:|---:|
| Default rectangular wing | 53.381 s | 23.789 s | 5992 → 1900 |
| Flexible wing | 46.563 s | 23.760 s | 5788 → 1860 |

The flexible case retains 2.28335 input length units of maximum displacement.
The original production browser default case converged in 115.601 seconds from
worker request to reply. Two optimized browser attempts took 78.213 and 106.520
seconds. Both retained the complete original default result exactly after
excluding only the top-level evaluation count and software provenance: 8,027
numeric values and every remaining field matched. Both delivered actual tangent
and load-stage progress to the UI. These shared-host samples show substantial
timing variability; they do not establish a twofold browser speedup.

Both browser harness failures remain recorded. The first attempt stopped after
the default solve because its progress assertion incorrectly rejected the
intentional initial load fraction of zero. The second changed only that assertion
from greater-than-zero to greater-than-or-equal-to-zero and completed both
physical solves. Its flexible-wing solve took 102.985 seconds and converged at
a residual of 1.676e-13, but four near-zero moment fields out of 6,264 numeric
fields exceeded the original native-versus-WASM comparison bound of
1e-8 absolute plus 1e-8 relative. The largest difference was 1.576e-8.
That bound has not been relaxed and the second Playwright run remains FAIL.

A separate audit of the retained flexible-case observations passed the remaining
convergence, export, exact request, 60-module provenance, worker progress,
rendered progress and browser-error checks. This was an offline audit, not a new
browser run. The final flexible-case screenshot lay after the failed assertion
and was not captured.

The original 59-module solver was then run with the exact flexible-case request
in the identical packaged WASM runtime. Its complete export matched the optimized
browser export exactly: 7,736 numeric values and 8,284 total leaves, excluding
only top-level evaluations and software provenance. No numerical tolerance was
needed for this comparison. The original solver itself reproduces the
native-versus-WASM discrepancy; exhaustive traversal of its full kernel result
finds seven near-zero moment fields exceeding the unchanged bound (the earlier
browser assertion selected four of them). The maximum difference remains
1.576e-8. Thus the runtime discrepancy predates the optimization. It remains a
recorded limit of native/WASM agreement, while this optimization preserves the
tested results exactly within each runtime. The Node/WASM control is accuracy
evidence only; its timing is not a browser speed measurement.

The main kernel and UI match the final frozen candidate; 1,334 tests collect
successfully. This collection count does not imply a complete suite execution.

See [machine-readable results](mounted-performance.json) and the linked evidence
archives for the exact source, inputs, full outputs, imports and terminal records.

Timing samples run sequentially on a shared host and are observations, not
performance guarantees. Browser and native timings are reported separately.
The full ASWING goal remains incomplete; these optimizations do not establish
broader feature or benchmark parity.

Evidence archives:

- [Core changes, tests and preserved attempts](mounted-performance-core-evidence.zip).
- [Initial profiles](mounted-performance-profile-evidence.zip).
- [Original native outputs and first candidate](mounted-performance-native-baseline-evidence.zip).
- [Complete residual/Jacobian comparisons](mounted-performance-jacobian-evidence.zip).
- [Final numerical-candidate timings](mounted-performance-native-evidence.zip).
- [Original production browser baseline](mounted-performance-browser-before-evidence.zip).
- [Optimized browser attempts and original-WASM accuracy control](mounted-performance-browser-evidence.zip).
