# FFWT influence accuracy integration

The shared-wake accuracy repair is integrated into the working source, including
cached aerodynamic fields and their circulation and geometry derivatives.
Scoped native and WASM checks pass. **It is not ready for browser release:** the
measured rigid solves are slower and the vector operators retain about twice
as much array storage. ISAE coverage remains **17 partial, 24 pending and
0 fully validated**. No original ASWING executable is available.

## What changed

Coincident wake rays now act on their combined signed circulation before
large contributions are added. Grouping requires exactly equal endpoints and
identical effective core radii for every receiver; nearby endpoints and
different cores remain distinct. Finite bound segments, own-bound exclusions,
ground images and the compressibility transformation retain their physical
definitions. The circulation residual uses the same scalar normal projection
for solved and prescribed circulation, with vector fields retained for loads.

Frozen and Newton-iteration caches support this representation. Geometry
derivatives combine wake strengths while preserving each source endpoint and
core's independent motion. Integration testing exposed a consumer that omitted
the new wake-motion terms; its three failing controls now pass at their
original tolerances. Testing also reproduced and corrected a pre-existing
torsion-hinge derivative error: the derivative must follow the network's fixed
rotation chart. Physical parameters and solver acceptance thresholds are
unchanged.

## Verification

| Check | Result and scope |
| --- | --- |
| Native cache, circulation reuse, time and frequency regressions | 138 passed on the final 105-module source |
| Affected geometry and derivative controls | 68 passed on that same final source, including all three preceding integration failures |
| Native coefficient controls | 42 passed; this snapshot predates two later derivative-only amendments |
| WASM coefficient controls | 42 passed on the final source in the local Pyodide runtime |
| Independent physical field comparisons in WASM | 3 passed on the final source |
| Selected 80-digit comparisons | All 8 evaluation-accuracy checks passed; maximum normalized residual evaluation error 4.82e-16 |

The WASM checks load current source directly under Node; they do not test a
rebuilt browser application. The selected high-precision comparison is an
evaluation check on unchanged saved circulation, not a full-vector accuracy
certificate or a new equilibrium solve. Two preceding prescribed-state
residual failures on separately rounded geometry remain failures, as explained
in the [earlier accuracy study](isae-ffwt1-influence-accuracy.md).

Earlier runs, including failures, retain their exact source snapshots. The
historical 119-pass/3-fail derivative run was followed by the 68 affected
final-source checks; it is not presented as a complete final-source rerun.
The earlier four-case hinge review also predates the final two derivative
amendments, despite its historical report's “final-source” wording. Final
native and affected-geometry suites cover the repaired hinge paths.

## Performance and release status

These are native rigid aerodynamic solves with one warmup and three timed
samples per case and implementation, using one BLAS thread. They use 48 mesh
intervals, alpha 5 degrees and Mach 0.1. Speed is 30 in each model's native
units: **30 ft/s for Daedalus and 30 m/s for the flexible-wing example**.

| Case | Previous median | Candidate median | Candidate / previous |
| --- | ---: | ---: | ---: |
| Daedalus, 217 lifting panels | 0.203 s | 0.339 s | 1.67 |
| Flexible wing, 48 lifting panels | 0.0151 s | 0.0187 s | 1.24 |

Returned circulation, forces, moments and residual comparisons pass, with
unchanged evaluation counts. Scalar projection reduced the initial Daedalus
regression from 2.31 times to 1.67 times the baseline runtime. These timings
do not measure mounted aeroelastic equilibrium, browser loading, nonlinear
time response or a Bode sweep. The benchmark snapshot precedes two subsequent
derivative-only changes; its aerodynamic value implementation matches the
final source.

For the 364- and 724-panel FFWT operators, retained arrays increase from
3.18 to 6.39 MB and from 12.58 to 25.22 MB per vector operator. Construction
is faster in the scoped benchmark, but application is approximately twice as
slow. The current browser kernel remains the previous 104-module release.

## Remaining work

Reduce operator storage and repeated contraction costs while preserving the
high-precision and derivative checks. A reviewed graph-coordinate formulation
could reduce storage for connected source groups; its numerical behavior and
benefit with receiver-dependent core groups still need demonstration.

Before release, verify the resulting performance on coupled equilibrium, time
response and frequency sweeps, and exercise the rebuilt browser application.
ISAE validation separately requires resolving fixture and archived-model
correspondence, the high-incidence lift discrepancy, flexible-wing and dynamic
comparisons, connected-circulation convergence and the remaining case families.
Independent agreement on shared assumptions does not establish experimental
validation or original-ASWING parity.

The [machine-readable summary](isae-ffwt1-influence-integration.json) records
source hashes, test scopes, measurements and retained limitations. The
[evidence archive](isae-ffwt1-influence-integration-evidence.zip) preserves
recorded reports, source snapshots and selected repository inputs; its
[receipt](isae-ffwt1-influence-integration-evidence.json) verifies archived
bytes without claiming a scientific rerun.
