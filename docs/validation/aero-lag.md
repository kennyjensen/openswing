# Aerodynamic lag on/off

The **Aerodynamic lag** control under **Circulation representation** implements
the documented ASWING K/L option. The [public user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes switching off the circulation-rate downwash and the associated
circulation-rate lift, including its plotted force contribution. This leaves
instantaneous flow tangency coupled to the elastic and flight equations.

`FlightCondition.aero_lag` is a boolean and defaults to `true`. Disabling it
removes both rate-dependent aerodynamic terms, including their tangents and
quarter-chord moments. It preserves apparent mass, material damping, elastic
inertia, prescribed motion, gusts, controllers and the steady circulation
equations. The actual circulation derivative remains in time/strip exports:
algebraic circulation can still change with motion or forcing even though that
derivative no longer contributes a load or downwash term.

Every aerodynamic result records the setting in `aerodynamic_lag`. The browser
report states whether lag is enabled, and changing the control invalidates
computed results. New sessions start enabled. Explicit OpenSwing saved cases,
equilibria and time checkpoints retain their own setting for reproducibility;
this is not the legacy `.set` format. Older case/condition records lacking the
field use the previous enabled equations. A saved time launch uses its saved
setting, which is displayed next to the loaded equilibrium.

## Independent references

For a rigid infinite-span section in a uniform harmonic vertical gust, with
chord c, speed U and reduced frequency k=omega*c/(2U), the implemented lagged
model gives

`CL_hat / w_hat = (2*pi/U) * (1+2i*k)/(1+4i*k)`.

With lag disabled the transfer is real and frequency independent:
`CL_hat / w_hat = 2*pi/U`. The finite lifting-line checks approach this section
limit using an original very-long-span model; this is not an aircraft test or
an exact Theodorsen/Sears claim.

For a vertical gust ramp `w=a*t`, the enabled model has time constant
`tau=2*c/U` and `Gamma=pi*c*a*(t-tau*(1-exp(-t/tau)))`; rate lift contributes
`rho*c*Gamma_dot` per unit span. The disabled model has instantaneous
`Gamma=pi*c*a*t`, without rate lift. Three consistent length/time/force systems
check the disabled response, and time-step refinement checks the enabled one.

A separately assembled typical-section model checks coupled heave/pitch
eigenvalues. Disabling lag permits direct substitution of the algebraic
circulation into the two mechanical equations, producing a four-state system.
The apparent-mass matrix and noncirculatory pitch-rate terms are retained.
An independent finite-wing version uses closed planar horseshoe integrals and
only the heave, pitch and circulation coordinates. Its poles can be compared
directly at the actual aspect ratio, without a 2D-limit approximation. Increasing
wing span checks approach to the section reference; additional structural
interval/Fourier choices check the implemented finite-wing behavior.

The same independent finite-wing mechanical equations also supply uniform-gust
transfers for heave, vertical velocity, vertical acceleration and pitch angle.
A four-state lag-disabled ROM is checked against these transfers and the full
descriptor response. Its direct acceleration feedthrough is compared with the
independent mass-matrix inverse applied to the gust load. The derivative-input
feedthrough must vanish in this case; retaining algebraic circulation must not
discard instantaneous gust forcing or apparent mass.
At the chosen 50 m/s operating point both lag settings have a growing
oscillatory pair. The frequency-domain comparison checks the frozen linear
equations' transfer, not the stability of a sustained forced motion.

Long wings attached to a short support produce weak inertias in the scaled
full descriptor. The 400-span case requires rank refinement. At span 4,000 the
dense reduction rejects the unresolved derivative rank; the full-descriptor
method checks nearby roots without discarding that inertia. The 8- and 12-panel
Fourier cases at span 400 also reject a dense rank tolerance of 1e-11; development
probes resolve four modes at 1e-12 and agree with the full descriptor. The main
study uses full-descriptor solves for these finer grids. Two search shifts
and two tangent steps are compared in the development probes and the span-4,000
study cases. A full-descriptor search still leaves total
finite dimension unclassified; matched reference poles are not a general
full-spectrum completeness claim.

The targeted native regression passed **156 tests**, including the 12 new checks
for flag validation, retained added mass, rate-load removal, harmonic limits,
finite mode count and saved launch/restart. Six JavaScript project-data tests and
all four offline browser workflows passed. This is not a fresh full-repository
regression.

The [native study](aero-lag.json) passed **23 cases**, recording 58 source hashes
including all 55 numerical modules. The source hashes are checked at both ends
of execution. The study compares 297 physical values when replayed in WASM.

| Independent check | Native result |
|---|---|
| Uniform section gust transfer, both lag settings and circulation bases | Maximum relative error 1.785e-5 |
| Disabled-lag gust ramp in three unit systems | Maximum absolute CL error 2.962e-10 |
| Enabled-lag ramp at dt = 0.02, 0.01, 0.005 s | Maximum CL errors 1.983e-7, 7.099e-8, 2.150e-8 |
| Finite-wing heave/pitch poles | Maximum relative error 3.528e-12; backward error below 2.04e-14 |
| Span-4,000 approach to the 2D pole limit | Relative error 0.001059 disabled, 0.002279 enabled |
| Four-state ROM gust transfer | Independent-reference error 2.706e-8; full/reduced error 4.638e-8 |
| Direct gust-to-vertical-acceleration term | 13.38191981312624 1/s; independent value 13.38191981312609 1/s |

These are verification models, not aircraft or experimental validation.
The [standalone SVG](aero-lag.svg) and [PDF](aero-lag.pdf) show gust gain, ramp
response and the original finite-wing pole comparison. The [packaged-WASM
replay](aero-lag-wasm.json) passed all **23 cases and 297 physical comparisons**,
with maximum scaled native/WASM difference **2.311e-11**, below the unchanged
2e-8 limit. It pins all 55 modules, 59 source hashes, the native study and runtime.
Final release verification is recorded in `docs/STATUS.md`; historical studies
retain their original hashes and are not claimed as fresh current-kernel runs.

## Scope correction for mesh requirements

The [steady formulation, section 3.1, equations 62–63](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
places pointwise circulation at structural intervals and offers an independently
sized Fourier series. The extended manual's NODE example similarly combines
180 structural nodes with 19 Fourier modes. The existing OpenSwing Fourier
implementation already provides independent mode and interval refinement.

Earlier project notes incorrectly elevated separate aerodynamic sampling meshes
to a required ASWING feature. No such requirement was established by these
public sources. The active ledger now distinguishes the documented independent
Fourier resolution from that possible extension. Legacy mesh-file conventions,
zero-length intervals and broader discrete/physical parity remain open; this
correction does not close the mesh requirement or reduce the full ASWING goal.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-aero-lag.py
npm run build
node scripts/test-aero-lag-wasm.mjs
npm run test:browser -- tests/browser/aero-lag.spec.js tests/browser/circulation.spec.js
```

To regenerate the figures, install the optional `plots` dependencies and run
`.venv/bin/python scripts/plot-aero-lag.py` after the native study.
