# AE-2: warm-start correction and equilibrium branches

Updated 2026-11-05. The warm-start implementation fix is verified in Python and
the offline browser. The negative-coupling, beta=5° comparison now reproduces
the archive's positive-deflection branch at 18–20 m/s on both nominal meshes.
All four native output channels at these points differ by at most **2.724%**;
deflection and rotation differ by at most **0.888%**. The 17 m/s discrepancy
remains unresolved. Historical initialization and complete native validation
remain open; the registered baseline stays **2/2,200**.

## Native comparison

The model bytes, condition at each point, section laws, ground plane and all
acceptance limits are unchanged. The registered frozen-influence, PG=0 setup
is retained. A cold full-load Newton solve at 20 m/s finds the positive branch;
the 19 and 18 m/s solves use the preceding accepted equilibrium, without editing
its fields. These are explicit diagnostic paths, not changes to the application
default or a claim about ASWING's historical initialization.

Fine-mesh signed errors, relative to the original printed native values:

| IAS (m/s) | OpenSwing RY (m) | ASWING RY (m) | RY error | Psi error | Sensor speed error | Sensor beta error |
|---:|---:|---:|---:|---:|---:|---:|
| 18 | +0.22002980 | +0.218111 | +0.880% | +0.830% | +0.0450% | +1.102% |
| 19 | +0.18994539 | +0.190580 | -0.333% | -0.337% | +0.0363% | +2.671% |
| 20 | +0.16992800 | +0.170538 | -0.358% | -0.366% | +0.0305% | +2.723% |

The maximum nominal-80 to nominal-160 change across these four observables is
**0.019982%**. All 24 scalar comparisons across the six positive-branch states
are within 3%, but **0/24** meet the existing AE-2 half-printed-unit acceptance.
The 3% policy remains specific to SA tests; it was not applied to the AE ledger.
Repeated paths to the same native cell are not added to the baseline score.

Ascending from 1 m/s instead retains negative deflection at 17–19 m/s. At
19 m/s, both signs pass the full nonlinear equations and physical checks on
the same nominal-80 mesh: RY=-0.32014685 m ascending and +0.18995452 m descending.
This explains much of the previously large discrepancy at 18–20 m/s as a
difference in the equilibrium reached. It does not establish stability,
uniqueness, or which algorithm generated the archived points.

## Complete outcomes and retained failures

| Diagnostic | Outcome |
|---|---|
| Ascending nominal-80, 1–20 m/s | 19/20 states computed; 266/266 physical checks over computed states. At 20 m/s, Newton line search fails at residual 0.0873. |
| Full-load cold, nominal-80, 17 m/s | Computed, 18/18 physical checks; negative deflection remains, RY error 230%. |
| Full-load cold, nominal-160, 17 m/s | 90-second timeout; process terminated and reaped, no accepted result. |
| Full-load cold, both meshes, 20 m/s | 2/2 computed, 36/36 physical checks; positive branch. Solve times 2.80/6.01 s, excluding process startup and independent recovery. |
| Descending, both meshes, 19 and 18 m/s | 4/4 computed, 56/56 physical checks; positive branch. |
| Descending, both meshes, 17 m/s | 2/2 numerical failures, not timeouts; no accepted state or native pass credited. |

The fine ascending series is unrun. The original zero-speed reference outputs
are NaNs and remain unavailable. The first eight ascending states retain the
original requested tolerance of 1e-8. An earlier 9 m/s state passed that residual
gate but failed moment balance; its result is retained. New ascending states
9–20 and the full-load/descending diagnostics requested a tighter 1e-10 residual.
Physical and native-reference acceptance gates were not relaxed. All numerical
jobs ran serially with one BLAS thread and bounded memory/time.

The original driver queues operating points and then executes `XX`. The manual
states that inserted points inherit settings/parameters and `XX` converges the
stack; it does not specify the initialization or iteration history needed to
identify these diagnostics as an exact replay. No new source evidence confirms
historical K/F, atmosphere or node bookkeeping.

## Implementation and browser verification

A generic warm-start Jacobian probe displaced a clamped root through the ground
image plane. The source-coupled saved-state corrector now uses the network's
existing boundary-aware complete Jacobian, including dense-factor recovery.
Eligible mounted source networks also use the existing sparse Newton matrix and
beam elimination. Full residual acceptance, physical clearance checks and the
fresh final tangent/rank check remain in place. No aerodynamic law or default
branch-selection policy changed.

All **104 Python tests** pass: four new wall-root cases covering updated/frozen
influences and sparse/dense recovery, 56 existing seeded-corrector tests, 22
time/progress tests, and 22 saved-state/source-coupled tests. The new cases
compare complete warm and independent cold equilibria, check force/moment
balance and unchanged seeds, release factor owners, and reject real crossings.

An actual offline UI import, saved-state solve and result export passes
**12 verification gates and 22,460 numerical comparisons** against the retained
Python IAS2-from-IAS1 case. The browser solve takes **16.64 s**, after **25.76 s**
startup/import. This is one browser case, not browser verification of the whole
speed sweep. Execution counters/timings are excluded from physical parity;
factor use, cleanup and final rank work are checked separately.

Two verifier issues are preserved: the initial attempt did not open the project
panel; the next completed solve was rejected because JavaScript contained an
optional `derivatives: undefined` property. The worker serializes requests to
JSON, which omits that property. Correcting comparison to the actual wire payload
allowed reassessment of the unchanged saved result with the original numerical
tolerances; no additional physical solve was needed.

## Evidence and next work

- [Machine-readable results, source hashes, checks and failures](isae-ae2-continuation-20261105.json)
- [Earlier checkpoint](isae-ae2-continuation-checkpoint-20261105.md)
- [Ascending plan and retained outcomes](../../artifacts/isae/ae2-continuation-tight-20261105/plan.json)
- [Four full-load controls](../../artifacts/isae/ae2-full-load-20261105/serial.log)
- [Six descending controls](../../artifacts/isae/ae2-descending-20261105/serial.log)
- [Browser reassessment](../../artifacts/isae/ae2-continuation-delivery-20261105/browser-reassessment.json)
- [Delivery scripts and test logs](../../artifacts/isae/ae2-continuation-delivery-20261105/)

Next: resolve the positive branch near 17 m/s using bounded parameter refinement
and complete-equation checks, and determine whether the archived point can be a
converged solution under the available inputs. Branch stability and historical
settings remain separate questions. The goal and broad ASWING requirements remain
incomplete.
