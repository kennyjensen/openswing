# AE-3 analytic circulation derivatives at the original default step

The corrected derivative method passes **both finite-control consistency checks at the unchanged default step, 1e-5**. The matched original method fails both. The exact tested source is now integrated, with regression tests. **AE-3 remains pending; this is numerical consistency, not experimental validation.**

Both calls restore the same 287-node, 286-element, 3,730-unknown zero-control state. The model, condition, mesh, two input columns and saved nonlinear solutions are identical. The study makes exactly two derivative calls, with no new equilibrium or finite-control solve; it reuses the four nonlinear solutions at control h=0.05 and 0.025.

| Method at step 1e-5 | Native Cl control derivative | Error against h=0.05 | Error against h=0.025 |
|---|---:|---:|---:|
| Original centered method | -0.000225205883705282 | 1.12576e-07 (FAIL) | 1.12614e-07 (FAIL) |
| Analytic circulation block | -0.000225318510512193 | 5.07967e-11 (PASS) | 1.27061e-11 (PASS) |

Each comparison retains the gate **1e-9 + 1e-5|D|**. Its candidate limit is 3.25319e-09. Coefficients use native stability Cl per literal file control, with S=.185 and b=1.2192; no experimental-area, sign or radians conversion enters these checks. All earlier finite-step and mesh failures remain recorded.

The change replaces only the 286 circulation columns with the derivative of the implemented smooth aerodynamic load equations. A fresh base capture supplies the influence and load data; no previous Newton matrix or lagged geometry is used. All other Jacobian columns and input partials match the original method exactly. The original checked circulation probes are also retained and match the baseline exactly. Scaling, dense SVD/LU, default steps, branch guards, rank and full-residual gates are unchanged.

The initial scope is fixed-acceleration responses without feedback, engines, type-3 hinges or inherited cache owners, with flow safely separated from the speed floor. Unsupported or unavailable analytic blocks retain centered differences. Physical branch errors still propagate. The result's method label identifies whether the analytic block was used.

Fresh base and post-state physical residuals are zero. Independent recomputation finds a maximum full linear residual below 1.33e-12, passing the original 1e-8 gate; rank checks pass. The independent saved-output audit passes 649/649 checks. The first reduction rejected roundoff-sized differences between repeated matrix products. That failure is preserved. An additive reducer compares those products using a dimension-derived floating-point bound while separately requiring both residuals to pass the unchanged physical gate. Extended-precision checks support this correction; no particular implementation cause is claimed.

Validation includes **142 distinct native tests**, three JavaScript consumer tests and two small current/frozen-influence Pyodide replays matched to native results. After integration, all 29 new regression tests pass again from the worktree. The exact candidate's 107 physics modules are installed; only `derivatives.py` changed and `derivative_circulation.py` was added relative to the 106-module baseline. The other modules are unchanged. Native tests and runtime replays are separate from the two-call AE-3 study.

This is an accuracy change. The checked-probe prototype performs 7,471 residual evaluations versus 7,470 for the original method, including one extra fresh capture. Single shared-host timing records include unequal audit I/O and are not speedup or browser benchmarks. Runtime bundles and the hosted release were not updated. A packaged-browser check of an eligible unpowered case remains necessary before claiming the rebuilt UI is verified.

The [shared-patch mesh study](isae-ae3-global-patch.md) retains its 2.0775% and 7.1443% failures. It must be repeated consistently across matched coarse/fine states using the corrected method; these old results cannot be silently reevaluated with mixed methods. Experimental amplitude/incidence/sign, section-control provenance, fixture/stiffness matching, driven-roll and reversal remain unfinished. Coverage stays **17 partial / 24 pending / 0 fully validated**, with no ASWING-executable comparison.

[Machine-readable results](isae-ae3-analytic-gamma.json) · [Earlier finest-mesh step study](isae-ae3-fine-derivative-step.md) · [Evidence archive](isae-ae3-analytic-gamma-20261024-evidence.zip)
