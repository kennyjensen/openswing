# Daedalus moving-field derivative recovery

The previously unresolved derivative at column 746 now passes the original accuracy checks when given two more permitted refinement levels. Production now allows at most six levels, up from four; the `2e-8` tolerance, stencil, contraction cap and acceptance formulas are unchanged. The corrected source also completes the full 32-panel descriptor assembly and three yaw-response samples from the saved trim; those separate results are recorded below.

The [original 32-panel failure](daedalus-rudder-refinement.md) remains retained: it produced no completed descriptor matrices or harmonic curve. A separate diagnostic reconstructed the saved trim and identified zero-based column 746, the z/L translation of node 124 at beam 4's root. Its worst original field entry was `hv[116,0]`. The final four-level contraction estimate was `5.2012397635555906e-8`, still above the original `2e-8` criterion, so the original rejection was correct. The diagnostic's fresh full residual was `2.97796555486591e-14`; this later check does not retroactively add a residual result to the original failed attempt.

The bounded extension reconstructed the retained fourth-level samples **bitwise across all fields**, then evaluated both predeclared levels five and six at the same saved state:

| Check | Result |
|---|---:|
| Level 5: original contracting-stencil error estimate | `6.193780395316925e-10` — accepted |
| Level 5: observed contraction | `83.97520466641363` (original cap still applied) |
| Level 6: successive fourth-order all-field change | `1.1765164299438253e-8` — passes `2e-8` |
| Level 6: successive Richardson all-field change | `1.1933868233133186e-8` |

The extension used one reconstructed network/system, five full residual evaluations and thirteen field evaluations. It performed no trim, full linearization, harmonic solve or full-system factorization; small source-owned local algebra is recorded separately in the machine-readable evidence. The original four-level failure and all raw samples remain preserved. The additional level-six comparison checks the measured local recovery. The complete operator was then assembled in the separate follow-up below.

Native regression coverage passed **29 tests** covering analytic refinement and packed complete geometry columns against full physical residuals, including propulsion and gust cases. Actual Pyodide passed **8 cases**: four physical unit scales, zero/linear call counts, fifth-order contamination, nonsmooth/error rejection, and an analytic seventh-order fixture that fails at four levels and resolves within six against its known derivative. These are separate, overlapping scopes, not a combined count. Pyodide loaded the current ROOT modules into its virtual filesystem; the matching `public/kernel/geometry_tangent.py` was subsequently synchronized. No runtime binaries, hosted deployment or download release were updated.

Already resolved columns follow the same return path and require no additional evaluations. Previously unresolved columns can use at most eight more field evaluations. Smaller steps can still become roundoff limited; the failure checks remain active. Neither this change nor the tests establish spatial convergence, an identified ASWING reference operating point or experimental validation.


## Full 32-panel follow-up

The saved raw equilibrium was reconstructed with its original scales, preserving the declared 30 ft/s, Mach 0.1 steady free-flight case. Its fresh full residual was `2.978e-14`. The production sparse assembly returned complete A/M matrices, including all 1,182 geometry columns; the F3 input derivative was built once. No trim was repeated. The original fallback to full residual differences for unresolved engine-inflow circulation derivatives remained active.

All three harmonic responses passed the original condition and residual gates:

| Frequency (Hz) | 32-panel yaw magnitude (deg/s per F3) | Complex change from 16 panels |
|---:|---:|---:|
| 0.1 | 0.37006433 | 2.7332% |
| 1 | 0.02794939 | 3.0393% |
| 10 | 0.35118415 | 3.2245% |

The relative complex change uses the finer, 32-panel response as its denominator. Assembly took 227.52 seconds and the three harmonics 4.36 seconds; the complete native follow-up took 241.77 seconds. These timings exclude the earlier 594.81-second trim and are not a browser benchmark. The original failed attempt is retained separately.

These three anchors do not establish mesh convergence or a complete 32-panel frequency curve. The [earlier full 8/16 sweep](daedalus-rudder-sweep.svg) found larger mesh differences between these anchors. Drela's published operating point and mesh remain unidentified, and substantial disagreement with its magnitude drawing remains. Aircraft-response validation is still open.

[Machine-readable summary](daedalus-rudder-field-refinement.json) contains exact source/test/report pins and separate operation counts. No new archive or catalog entry is created by this summary.
