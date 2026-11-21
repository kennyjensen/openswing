# Loaded half-wing with live brace: dynamic component comparison

The native model agrees with an independent continuum reference at all nine finest-mesh frequency/input cases. The largest complete-motion error is **0.13632%**, below the predeclared **1%** criterion. Errors decrease through both mesh refinements in every case. This closes a dynamic mechanical component check; the full Daedalus Bode mismatch remains unresolved.

The fixture is the actual loaded C16 positive half-wing, from root to tip at 56 ft, with its variable stiffness, distributed real mass, variable chordwise CG offset, full material rotation and live offset axial brace. Root pose and the original nodal dead forces/couples are fixed. The brace retains its physical anchor, material pylon arm and invariant rest length. Its force and rotating-arm couple vary with the motion. The native 17/34/68-element models reuse their accepted static equilibria; the independent reference reconstructs each previously accepted loose/tight continuum base from its saved root wrench. No new equilibrium/root solve or aircraft trim is performed.

Live aerodynamic derivatives, apparent mass, live gravity derivatives and free-aircraft motion are absent. Previously captured steady loads remain dead loads. No damping is added. The literal section has zero intrinsic `mgcc/mgnn` and zero payload fields: the test exercises variable line mass and its nonzero CG-offset translation/rotation coupling, including the parallel-axis contribution, but does not validate nonzero intrinsic section rotary inertia.

The fixed frequencies are **0.1, 1.0 and 1.15737773741517 Hz**. The last is the already recorded drawing-minimum frequency, not an adjusted fit. At each frequency, the three inputs are unit physical tip **Fx**, **Fz** (1 lbf each), and **My** (1 lbf-ft), in the original physical Cartesian axes. Outputs retain full nodal displacement/spatial rotation, local velocity/rate, element resultants and geometric endpoint-wrench derivatives, clamp reaction, brace force/axis couple, anchor force, brace length and tension. The endpoint derivatives exclude separate distributed inertial nodal loads; they are not full continuum section traction. The separate support and individual-channel differences are reported as diagnostics.

The agreement measure is, for each input, `max(abs([u/56, theta]_native - [u/56, theta]_reference)) / max(abs([u/56, theta]_reference))`, over all nodes and six motion channels. Displacement uses ft and rotation radians; complex responses are compared directly. There is no denominator floor or extra input/display conversion. Zero-reference channels keep their absolute errors and undefined relative ratios.

| Frequency (Hz) | Physical tip input | 17 elements | 34 elements | 68 elements |
| --- | --- | ---: | ---: | ---: |
| 0.1 | Fx | 7.332516% | 0.889929% | 0.072619% |
| 0.1 | Fz | 1.684018% | 0.499019% | 0.069126% |
| 0.1 | My | 1.108876% | 0.504495% | 0.136320% |
| 1.0 | Fx | 6.383633% | 0.793801% | 0.101993% |
| 1.0 | Fz | 4.476824% | 0.840246% | 0.095877% |
| 1.0 | My | 1.149133% | 0.507156% | 0.135897% |
| 1.15737773741517 | Fx | 6.121126% | 1.300524% | 0.132698% |
| 1.15737773741517 | Fz | 6.751913% | 1.325543% | 0.124575% |
| 1.15737773741517 | My | 1.168236% | 0.508632% | 0.135731% |

The independent reference extends the previously checked nonlinear spatial rod and live-brace tangent with distributed inertia from the unsteady theory, printed p. 9, Eqs. 37–40. For zero base rates/accelerations its spatial system is `y' = (A - omega^2 B)y`; B contains the material-frame mass, CG mixed blocks and parallel-axis term. The same massless brace jump is applied once. Each tolerance/frequency has one six-unknown boundary solve with three right-hand sides; all three grids sample that continuum solution.

Integration tolerances were fixed at 1e-9 and 1e-11, with absolute tolerances 0.01 times those values. Both reconstructed bases reproduce the accepted before/after arrays exactly. Worst loose/tight relative difference is **6.37e-10**, below the unchanged 1e-6 tightening gate for motion and support groups. Minimum boundary reciprocal condition is **2.60e-4**; maximum scaled residual is **1.03e-14**, within the original conditioning/residual/backward-error gates. No pole avoidance, frequency adjustment or retry was used in the scientific runs.

The native runs passed **204/204** technical checks, using three A/M assemblies and nine three-RHS harmonic calls, with zero equilibrium calls. The independent reference passed **82/82** checks using two base reconstructions and six three-RHS boundary solves. The saved comparison passed **53/53** technical checks and **9/9** finest agreement checks. An independent saved-array/source audit passed **547/547** checks, recomputing all 27 complete-motion metrics, 324 individual-channel metrics and 189 support metrics without physical evaluations or system products. A separate independent saved-operator audit passed **257/257** checks, including all nine full harmonic residuals, coordinate/velocity maps, clamp reaction and live-brace pretension/rotating-arm derivatives, with nine saved three-RHS matrix products and no physics or solves. The portable current-repository regression passed **1/1** test with **9/9** original agreement criteria. All scientific children and audit sessions are reaped.

The audit initially rejected a bitwise identity between scalar complex division and NumPy's vector division for `u/56`. The largest difference was **1.735e-18**, less than 0.969 binary64 epsilon relative; zero references were unchanged. Its initial script, failure and closeout are retained. Only that algebraic audit identity was corrected to allow four binary64 epsilons times the reference magnitude, with exact zeros. The original physical 1% agreement criterion, arrays and scientific runs were unchanged.

The independent material-property interpolation uses natural cubics from the literal tables, split at repeated knots. Agreement under refinement supports this implemented component formulation; it does not identify the historical executable's interpolation, the drawing's operating point or its complete aircraft dynamics. No change to production physics or Daedalus settings follows from this result.


Evidence: [summary and receipt pins](daedalus-wing-brace-dynamic.json), [all nodal complex responses](daedalus-wing-brace-dynamic.csv), and [complete evidence bundle](daedalus-wing-brace-dynamic-20261025-evidence.zip). The bundle preserves the source plans, exact dependencies, raw arrays, both saved audits, the retained first audit failure and terminal process receipts. The [portable regression](../../tests/test_daedalus_wing_brace_dynamic.py) and its [fixture provenance](../../tests/data/daedalus-wing-brace-dynamic/provenance.json) reproduce the focused 68-element comparison from repository data.
