# AE-4: current-code comparison and bounded validation

Observed 2026-11-12 UTC. The original undeformed Pazy-wing comparison at
**101 m/s passes 8/8 native components** across the declared nominal 40/80
meshes. The cumulative declared sweep advances from **11/1,200 to 19/1,200**
at 5%. This is new coverage, not a correction of the remaining 103 m/s
discrepancy. Original targets, pairing rules and numerical gates are unchanged.

## Native comparison

The literal model and driver remain authoritative. The existing declared
scope uses density 1.23, PG Mach 0, alpha 0, gravity 9.81, a solid wall with
normal `[0,0,1]`, fixed frame, pointwise circulation, lag and updated
influences. The original local search requests four modes at shift `0+200i`.
The insertion-stack interpretation maps IAS 101 to archived point 102.
Historical startup/constraint settings remain qualified; updated influences
are an explicit declared setting, not a recovered native default.

| Archived point 102 component | ASWING | Nominal 40 | Error | Nominal 80 | Error |
|---|---:|---:|---:|---:|---:|
| Lower-frequency mode, real part | 24.111925 | 24.20353226 | 0.380% | 24.15260476 | 0.169% |
| Lower-frequency mode, imaginary part | 118.87142 | 118.56749969 | 0.256% | 118.51553081 | 0.299% |
| Higher-frequency mode, real part | −2.7015324 | −2.65727175 | 1.638% | −2.57443959 | 4.704% |
| Higher-frequency mode, imaginary part | 182.17635 | 182.27923394 | 0.056% | 181.88582829 | 0.159% |

Units are inverse seconds. Complete positive-frequency sets are paired using
the existing frequency order; the two computed real poles remain retained
and independently certified. No extra native real-pole identity is inferred.

The separate **0.1% mesh gate passes only 1/4 components**. Changes using
the fine value are 0.211%, 0.04385%, 3.217% and 0.216%, respectively. Native
agreement at 5% does not establish mesh convergence.

The cumulative selected scope is **19/48**, comprising twenty paired values
(nineteen passes, one mismatch), sixteen unmatched values at 103 m/s and twelve
blocked initial-point values. **1,152 further declared components are unrun.**
Five earlier solves are inherited historical evidence; the two 101 m/s solves
are fresh. The separate accumulated sampled count is **75/96** and overlaps
the primary sweep. It must not be added to it. All eighteen historical modal
exports and their 9,480 components remain separately inventoried.

## Current 103 m/s diagnostic

A cold nominal 40 equilibrium, sparse physical matrix assembly and four-mode
solve were run in separate bounded stages. All **25 numerical checks pass**,
including fresh residual-action checks, left/right full-pencil residuals,
mass pairing and root-clamp conditions. The base residual is 2.16e−16.
All eight returned real/imaginary root components reproduce the earlier
coarse calculation exactly. These stages use about 4.03 CPU seconds in total,
excluding library preload and parent evidence checks. They add no primary votes.

The unmatched native tiny root and candidate slow branch therefore remain
open. The slow real pole is 0.09329738979/s versus the candidate native
0.033334576/s, a conditional 179.88% difference. The previous independent
[full-spectrum check](isae-ae4-spectrum-20261105.md) remains relevant; no new
generalized-Schur calculation was run.

Twenty-four signed coordinate probes confirm the current wall/frame
limitation on the actual Pazy geometry. Normal frame velocity, all three
frame angular rates, normal Earth position, bank and elevation are rejected.
The other five coordinates admit both signs. A complete prescribed-frame
pencil is consequently not supported at this wall mount. No rejected column
was replaced by zero or bypassed.

This confirms the limitation already disclosed by the
[earlier frame study](isae-ae4-frame-constraints-20261105.md). Its free-air
tests and block-triangular argument show that retaining prescribed-acceleration
integrators does not change nonzero wing poles under their stated assumptions.
It could explain extra near-zero roots, but does not repair the slow nonzero
pole discrepancy or authenticate the archived restraint mask.

## Validation memory fix

The nominal 80 cold solve completed and saved its full result, but its validation
worker failed when NumPy attempted a 37 MiB complex copy of a real matrix.
The two AE-4 validation paths now compute real-matrix products with the real
and imaginary vector parts separately. They retain the original full residuals,
mass pairing and thresholds. A second failure exposed a whole-file hash read;
the helper now streams SHA-256 without changing its byte-count/digest contract.
The shared runner and summarizer pin the new numerical-check helper explicitly.

**72 focused regressions pass** after the vector-action change. After streamed
hashing, **22 regressions pass**, including one new hash check and 21 repeats:
**73 distinct tests have passing evidence**, not 94 independent tests. The
coarse eigenvalues and reference decisions are exactly unchanged on reassessment.

The saved fine result passes both validation paths in a final
**2.10 CPU /2.49 supervised wall-second** worker, with peak RSS 327.9 MiB and
the unchanged **512 MiB address-space /15 CPU /25 wall-second** limits. The
coarse full comparison took 4.92 CPU /6.83 wall seconds. The original fine
worker used 9.27 CPU /12.87 wall seconds before its validation allocation failed;
that failed receipt remains preserved. Neither cold solve was repeated.

One recovery worker passed numerically but its parent source guard rejected
changed resolved paths caused by PRoot hard-link emulation. All four affected
files had identical lengths and hashes. The final recovery uses independent
file copies and passes the original source guard. The earlier constructor
error, plan-creation timeout, allocation failures, parent-guard failure and
two strict-view accounting errors are retained in their artifact directories.
They contribute no comparison passes.

Production equations and browser code are unchanged. Browser/build checks
remain held. All launched children are terminal and reaped.

## References and evidence

Jan Part IV §3.4, pp.13–16, distinguishes the vertical unloaded Pazy setup,
flutter/divergence and nonlinear limit cycles. Drela steady §5.1 Eq.178,
p.37, gives prescribed acceleration for a tunnel clamp; Eq.177, p.36,
retains Earth-position/attitude dependence with ground effects. Unsteady
§13.3.1, Eqs.147–152, pp.28–29, specifies the reused shifted LU/Arnoldi and
left-eigenvector normalization. The user guide maps `% D` to DONE, not
anchored defaults. See the [authoritative reference index](aswing-authoritative-references.md).

- [Combined comparison audit and mesh errors](../../artifacts/isae/ae4-current-native-20261112/assessment.json)
- [Current fixed-frame and wall probes](../../artifacts/isae/ae4-current-frame-r2-20261112/plan.json)
- [72-test receipt](../../artifacts/isae/ae4-pencil-memory-20261112/cases/tests/terminal.json)
- [22-test receipt after streamed hashing](../../artifacts/isae/ae4-pencil-memory-r2-20261112/cases/tests/terminal.json)
- [Final fine-result receipt](../../artifacts/isae/ae4-pencil-memory-r3-20261112/cases/fine/terminal.json)

Next: expand current-code coverage around the flutter boundary using small,
serial registered jobs. Keep the 103 m/s source/mode ambiguity and spatial
convergence issues open; missing wall-frame support needs its own physical
boundary formulation before testing a complete prescribed-frame spectrum.
