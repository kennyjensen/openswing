# Terminal circulation correction and FFWT mesh refinement

Updated 2026-10-15. This study follows the
[archived-curve comparison](isae-ffwt1-curves-08.md). ISAE coverage remains
**17 partial / 24 pending / 0 fully validated**. The original ASWING executable
is unavailable. Experimental validation and the full ASWING goal remain open.

## Recovering the fine-mesh equilibrium

The prior frozen-influence 400/160/160 endpoint stopped when an inner
circulation residual of 1.0398516e−12 exceeded the reference's 1e−12 gate.
The generic circulation continuation uses a 1e−11 endpoint tolerance; merely
tightening that tolerance can cause additional continuation and subdivision.
The implementation instead applies a bounded Newton correction after the
existing solver reaches the physical equations and before computing final
loads. The equations, physical inputs and existing continuation algorithm are
unchanged; recovering a previously rejected pose can change subsequent outer
solve steps.

The correction applies only to internally solved pointwise circulation without
engine feedback. Caller-supplied circulation, Fourier circulation and engines
retain their existing behavior. Each accepted correction strictly reduces the
actual normalized physical residual. At most four corrections and seven
trial factors, from 1 through 1/64, are allowed per correction. The total
change is bounded by 1e−8 times the larger of the initial maximum circulation
magnitude and the maximum section scale cV/2. This is a numerical guard,
not proof of branch identity or stability. Failed or nonfinite trials retain
the best previous state, and timeouts propagate. No core, physical index,
section property or residual acceptance gate is relaxed.

Using the original computed 100/40/40 endpoint as its seed, the tested source
reaches a fully balanced 400/160/160 state at the same scripted incidence
30.2638898547°, true speed 22 m/s and declared frozen-influence setup:

| Quantity | Accepted result |
| --- | ---: |
| Physical starboard / port fold | 50.20027654° / 50.20070227° |
| Port sensor bank | 46.10827711° |
| Lift | 19.90152473 N |
| Normalized circulation residual | 7.91e−13 |
| Maximum hinge imbalance | 6.34e−17 N m |
| Native reference evaluations | 9 |
| Timed native study | 167.22 s, within its 180 s cap |

Only two evaluations need polishing, each taking one full Newton correction.
Their maximum realized circulation changes are 4.33e−15 and 4.44e−15 in the
model's circulation units. A final evaluation with circulation explicitly
supplied reproduces the force, moment and torque arrays exactly, without
calling the correction. Independent source and saved-array review checks all
nine states and reconstructs the final hinge and support load balances.

From the previous accepted 200/80/80 mesh, the port bank changes by +0.00041248°
and Lift by −0.00008810 N. The archived Lift difference remains −0.85187527 N.
The terminal correction resolves a numerical rejection; it does not explain
that physical/model discrepancy, prove a convergence order or connect this
local root to the hanging-start branch. These timings are for a native
two-hinge reference, not a browser cold solve or a full-network speed benchmark.

## Independent finite-chord directional refinement

The separate vortex-ring reference refines chordwise and spanwise panel counts
independently from its previous 896-panel result. Every run uses the same
computed nominal seed, physical assumptions, load closure and strict gates.
No experimental angle is an input.

| Panels | Chordwise × (main + starboard + port) | Port physical fold | Change from 896 |
| ---: | --- | ---: | ---: |
| 896 | 8 × (64 + 24 + 24) | −9.92656068° | — |
| 1120 | 10 × (64 + 24 + 24) | −9.92796381° | −0.00140313° |
| 1152 | 8 × (80 + 32 + 32) | −10.00043884° | −0.07387816° |

Both new roots pass 1e−12 m/s boundary and 1e−12 N m hinge gates. Independent
saved-array checks cover all 20 evaluations, signed edge forces, moment arms,
gravity and accepted-state copies. The span changes have different main/tip
refinement ratios, so these are directional sensitivity checks, not a
Richardson convergence study. Body-z force changes by −0.013254 N and
+0.013474 N respectively. A small chordwise angle change alone does not
establish convergence of the loads or full solution.

Spanwise resolution remains the larger observed angle sensitivity. The
independent reference's half-chord datum, rigid main wing, thin-surface slope,
incompressibility and declared segment-force closure still differ from parts
of the archived lifting-line model. Its roots do not establish exact ASWING
parity or experimental agreement.

## Verification and release status

The numerical source passes 39 existing circulation tests and 21 new regression
cases, including aerodynamic integration and scope guards. A separate set of
13 analytic correction controls overlaps the new regressions; it is not an
additional independent physical benchmark. The checks include unit scaling,
local-root retention, distant-root rejection,
nonfinite/singular/domain failures and timeout propagation. Eight supplied-
circulation integration cases and two deliberately perturbed Fourier/engine
scope checks produce byte-identical complete output records against the
previous source. These scope checks do not claim that the perturbed states
meet the stricter reference equilibrium gate.

In actual Chromium/Pyodide, the native 400-mesh circulation replay has residual
2.94064e−12 and fails the unchanged strict gate. That failure is retained.
An explicit correction at the same pose changes circulation by at most
1.19e−14 and recovers residual 8.60874e−13 with maximum hinge imbalance
9.46e−17 N m. It is separate from the unmodified supplied-circulation path.
All 104 module imports and 13 helper controls pass in that run;
its small unprescribed stalled case passes but needs no terminal correction.

A separate focused Chromium/Pyodide run passes seven integration cases. Both
updated- and frozen-influence tests perturb a genuine continuation endpoint
before the automatic correction. Residuals near 1.68e−9 fall below 3.11e−17
with one correction, and final forces, moments, rate loads and strip outputs
exactly match supplied-corrected-circulation replay. Three supplied-state cases
and two Fourier/engine exclusions also pass. These are controlled integration
tests, not unperturbed aircraft operating-point benchmarks. The original
native-to-browser replay failure above remains retained.

Production source uses the same tested numerical files: `aero.py` changes and
`circulation_polish.py` is added. The 21 new regressions are installed as
`tests/test_circulation_polish.py`; UI sources and runtime dependencies are
unchanged. The general 1e−8 circulation acceptance gate also remains unchanged;
the terminal correction targets 1e−12 without weakening any existing gate.

The [recorded-result index](circulation-polish.json),
[selected evidence](circulation-polish-evidence.zip) and
[fresh-extraction verification](circulation-polish-evidence.json) retain the
inputs, source versions, original failures, arrays and reviews. Archive
verification reconstructs the result index; it does not rerun all numerical
studies. Distribution rebuilding and byte verification are separate release
checks. No browser cold-solve speedup or experimental validation is claimed.
