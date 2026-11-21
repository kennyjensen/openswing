# Exact reuse during coupled derivative assembly

Implemented in workspace source on 2026-10-24. The isolated packaged build and
offline browser check pass; no hosted release was deployed by this change.

The derivative calculation now reuses unchanged geometry, section properties
and aerodynamic influence work during its complete centered residual probes.
It retains every Jacobian entry, the existing perturbation steps and branch
checks, full column-scaled SVD, dense LU shared by all parameter columns, and
the original full linear-residual acceptance gate. It does not substitute the
lagged Newton iteration matrix for the physical derivative Jacobian. The
separate sparse-factor prototype is not included.

The cache belongs to one derivative-owned network copy. Cleanup restores its
owner and invalidates trial aerodynamic values, including after exceptions.
Free-flight, feedback and pre-existing cache owners retain their previous
path. Local-row geometry reuse remains disabled. The private audit callback
supports reproducible comparisons without changing serialized user results.

## Evidence

| Check | Result |
|---|---|
| AE-3 20O-05, 128 requested panels, 1702 equations | All 2,896,804 Jacobian entries, scaled matrix, norms and input columns byte-identical; full serialized derivative result byte-identical |
| Current-influence wing-body and powered models | All 28,832 Jacobian entries across 124/116-equation systems, scales, partials and responses byte-identical; both serialized derivative results byte-identical |
| Existing native regressions | 109/109 pass, including analytical responses, resolved perturbations, feedback/free-flight fallback and branch rejection |
| New ownership regressions | 7/7 pass, covering cleanup, parent preservation and conservative fallback |
| Actual local Pyodide | Two 64-panel saved-equilibrium derivative replays pass; 38,024 numeric comparisons, no network fetches |
| Offline packaged browser | Existing section-derivative test passes: analytical strain/stress, JSON/CSV export, missing shell data and 390px mobile layout |
| Scoped signed-zero fixtures | 32 checks pass; 31 array comparisons byte-identical |

The two current-influence fixtures use four requested panels, alpha 5 degrees,
beta 2 degrees and Mach 0.15. Wing-body includes solid ground and volume
influences; powered uses 3000 W per engine and bilateral rods. These deliberately
small fixtures exercise the cache paths; they are not mesh-converged physical
predictions. Maximum fresh physical residual is 3.109e-13, and maximum fresh
linear residual is 4.712e-15. Actual influence-cache calls and retained entries
are recorded, rather than inferred from model names.

The browser test goes offline after initial loading and disables WebGL2.
It checks warm offline section/export workflows, not cold offline startup or
3D rendering. The mobile screenshot was also visually reviewed.

The Pyodide cases retain their frozen K/F influences. Their largest fresh
physical residual is 9.104e-17 and derivative linear residual 8.938e-14.
Comparison tolerances remain 2e-8 absolute plus 2e-8 relative in each field's
units; the largest dimensionless tolerance fraction is 0.044614. No derivative
output field is excluded. The restored-equilibrium evaluation counter is
excluded from the base-result comparison because no equilibrium was re-solved.

The original native test attempt failed during collection because a reporting
plugin used the wrong hook argument. Two browser attempts failed before page
creation: a missing loader path, then an incomplete Chromium installation
without ICU data. They performed no physical solves. Their original logs and
plans remain preserved. Corrected runs changed only the reporting/environment
setup and used unchanged numerical code, physical cases and assertions.
The first saved-only consolidation also retained a relative-path resolution
mistake; its corrected report verifies all 16 pin groups without numerical reruns.

## Timing and limits

The selected 128-panel native derivative call recorded 19.13 seconds versus
49.44 seconds in the saved baseline; Jacobian assembly/scaling recorded 15.96
versus 45.99 seconds. Every result matched exactly. The baseline's wall and
monotonic clocks differ, and the runs occurred under different concurrent
load. These are observations from one case, not a controlled speedup estimate.
No browser-wide performance claim follows from them. The two small influence
pairs recorded 1.883 to 1.656 seconds and 1.418 to 1.288 seconds, respectively.

The inherited pair/material array-payload budget is 64 MiB and steady geometry
budget 16 MiB; Python objects, key overhead and separate motion-cache storage
are additional. These are not whole-operation memory limits. Signed-zero
fixtures are nonsingular and do not establish every branch or coincident-point
limit. No original ASWING executable comparison is available.

ISAE coverage stays **17 partial / 24 pending / 0 fully validated**. AE-3 remains
pending: matching the experimental finite-control observable and resolving
the retained mesh/derivative discrepancies require further work. No measured
values, stiffnesses or control coefficients were fitted.

[Machine-readable evidence](derivative-cache.json) ·
[Raw evidence archive](derivative-cache-20261024-evidence.zip) ·
[AE-3 comparison](isae-ae3-locked-control.md) ·
[Earlier factor-only investigation](derivative-factor-investigation.md)
