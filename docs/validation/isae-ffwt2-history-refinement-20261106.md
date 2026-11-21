# FFWT-2 full-startup time refinement and independent aerodynamics

Completed: **408 accepted steps**, no rejected steps or failed jobs, across
42 bounded serial segments. Summed segment wall time is 1,037.91 seconds
(17.3 minutes); this is not a controlled performance comparison. The receipt is
[`serial-status.json`](../../artifacts/isae/ffwt2-history-refinement-20261106/serial-status.json).
All accepted residuals are at most **9.878e-9**. Native agreement remains
**5/25 computed values**, or **5/4,005** required values, at 5% tolerance.

The selected literal FFWT10/V15/DF21 model, nominal-16 cosine mesh, zero-motion
and zero-circulation jig seed, source equations and 1e-8 residual gate are held
fixed. The time step is halved from .01 to .005 s for the entire 0–2.04 s
history. The second original time command at 2 s takes one BDF1 step, followed
by BDF2. Ordinary checkpoint segments retain their preceding history.

Only one numerical job runs at a time, with one BLAS thread, a 90-second cap
and a 512 MiB address-space limit. Every completed segment retains its full
states, checkpoint, input/source hashes and discrete-equation replay. A real
timeout may shorten the job duration; it does not change the time step or
physical model. Failed attempts remain evidence.

The predeclared numerical accuracy gate is 0.1% of each channel's maximum
fine-grid magnitude over the five common 2.00–2.04 s output rows. The separate
native-reference allowance is 5%. All 4,005 targets in the selected archived
table remain required; the other 3,980 entries are not run by this study.

## Results

| Native channel | Passing / computed | Failed median error | Failed maximum error |
|---|---:|---:|---:|
| Roll acceleration | 0/5 | 160.56% | 199.81% |
| Roll rate | 5/5 | — | — |
| Aircraft bank | 0/5 | 7.49% | 7.56% |
| Sensor 2 bank | 0/5 | 64.83% | 73.30% |
| Sensor 3 bank | 0/5 | 31.83% | 32.12% |

The original .01 s jig scope remains separate at 5/25. The earlier
equilibrium-start scope remains separate at 10/25. No best-of-scope score is
formed, and no angle, time, physical parameter or initial state is fitted.

Full-history .01/.005 s refinement passes only **1/5 numerical accuracy
gates**, so full-history convergence is not established:

| Channel | Maximum change / fine-window scale | 0.1% gate |
|---|---:|---|
| Roll acceleration | 10.0975% | Fail |
| Roll rate | 0.1712% | Fail |
| Aircraft bank | 0.1213% | Fail |
| Sensor 2 bank | 0.2522% | Fail |
| Sensor 3 bank | 0.0660% | Pass |

The acceleration comparison includes the known time-command restart effect.
To isolate accumulated startup error, a second assessment compares the new
history with the previous **same .005 s second-command grid**, which began
from the coarse-history 2 s checkpoint. With that local step held fixed,
the maximum acceleration difference is **1.4421 degrees/s²**, or 1.9796% of
the fine-window scale. The corresponding rate and bank/tip differences are
0.3017 degrees/s and 0.3410 / 0.3177 / 0.0943 degrees. This does not certify
time convergence, but the tested refinement does not explain the much larger
native discrepancy or recover a failing channel.

## Independent aerodynamic check

The independent aerodynamic checker reconstructs the bound/wake Biot–Savart
field, bound-point velocities, circulation-lag/stall equation, lift,
circulation-rate lift, profile drag and apparent-mass force/couple. It imports
no production aerodynamic routines. Its inputs are saved geometry, kinematics,
circulation and circulation rate; this is not an independent trajectory solve.
It retains the existing nodal horseshoe construction and own-bound exclusions;
the previous qualifications about their off-filament historical interpretation
remain. Passing arithmetic checks cannot resolve those source ambiguities.

All **27 snapshot records** pass all nine local equation/load gates. Records
include repeated checkpoint boundaries, the initial .005–.05 s sequence, and
both coarse/fine 2.00–2.04 s windows. Maximum reconstructed errors are:

| Quantity | Maximum error |
|---|---:|
| Bound-point relative velocity | 5.276e-13 m/s |
| Section lift coefficient | 1.756e-15 |
| Normalized circulation equation | 4.562e-9 (limit 1e-8) |
| Strip force | 8.501e-17 N |
| Strip moment | 1.424e-18 N m |
| Apparent-mass force | 8.674e-19 N |
| Apparent-mass moment | 1.356e-20 N m |

Eight independent reference tests pass in 2.03 seconds. They compare finite
and infinite vortex integrals with direct Gauss line quadrature, verify the
known unswept-horseshoe downwash, and check orientation and translation.
The checked states have maximum absolute section Cl **0.3900** and no stalled
strips. The failing native-window response is therefore not attributable to
section stall in those saved states; this is not an all-history stall audit.

Source equations: [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
Eqs. 67–74, 155–160, 203–204; [unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
Eqs. 23, 31–36, 43–44 and 48–49. The existing objective
angular-acceleration transport interpretation is retained. This audit does
not authenticate historical initialization, solver flags or node spacing.

All 138 production kernels and the browser bundles are unchanged. Finer
full-history time steps, spatial refinement, historical startup/settings,
later native rows, other models and the shared comparison adapter remain open.
The independent mechanics and instantaneous aerodynamic checks now support
the implementation within their stated scope; they do not prove historical
ASWING equivalence. FFWT-3 is another actionable zero-coverage family: its
archive retains model/driver/output files starting at time zero, although
forcing and output contracts still need registration.

Evidence:

- [Complete history assessment](../../artifacts/isae/ffwt2-history-refinement-20261106/assessment.json)
- [Startup difference with local dt held fixed](../../artifacts/isae/ffwt2-history-refinement-20261106/startup-isolation.json)
- [Independent aerodynamic assessment](../../artifacts/isae/ffwt2-history-refinement-20261106/aero-assessment.json)
- [Eight reference tests](../../artifacts/isae/ffwt2-history-refinement-20261106/aero-reference-tests.log)
