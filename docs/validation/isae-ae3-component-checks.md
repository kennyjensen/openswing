# AE-3 independent influence and common-load structural checks

The selected aerodynamic influence coefficients agree with independent line integration, and the two structural meshes give similar responses under identical loading. These results support investigating aerodynamic discretization and force/moment integration next. They do **not** resolve the original coupled mesh failures: **2.0773% and 7.1435%**, against the unchanged 1% criterion. AE-3 remains pending.

The aerodynamic check independently reconstructs the literal jig geometry and integrates the finite bound vortex and both semi-infinite wake legs. It checks eight receiver rows on each existing mesh, adjacent to the root, control breaks and tips, against all source horseshoes: **3,568 distinct influence coefficients**, each at four quadrature orders (32, 64, 128 and 256). No OpenSwing kernel is imported and no linear system is solved.

| Existing mesh | Final coefficient mismatch / allowed tolerance | Final selected-row residual | Result |
|---|---:|---:|---|
| 160 intervals | 0.00016135 | 9.4774e-13 | PASS |
| 286 intervals | 0.00032261 | 3.7881e-12 | PASS |

The coefficient allowance is 2e-8 + 2e-8 times the absolute saved coefficient; the residual limit is the original 1e-8. All four orders pass. Across all levels, the largest tolerance fraction is 0.00032301 and the largest selected residual is 3.7882e-12. Exact control forcing agrees with the saved centered stencil within 1.735e-17; the analytic centered-stencil value agrees within 1.735e-18. The nonzero stall-leakage derivative is retained.

A closest-approach angular change of variables makes each line integral smooth. This was selected before execution to avoid missing a narrow wake-leg peak. The integrals use weighted cosine evaluations, not the production closed-form vortex formulas. All three oriented legs and all four levels are saved. Adjacent quadrature changes are diagnostic, not a rigorous error bound. This checks selected discrete influence rows and control forcing, not the entire operator, output moment integration, continuum accuracy or experimental agreement.

For the structural comparison, both existing meshes receive exactly the same **286 physical point-wrenches** from the saved fine 20O-05 control response. The loads include the quarter-chord and direct section-moment couples at their saved centerline locations. The reference-origin force lever arm is not counted twice. The same literal model is reconstructed without airflow, gravity or a base load; no nodes or material properties change. Force, moment and virtual-work transfer checks pass.

| Quantity at the 161 common nodes | Norm of fine-minus-coarse difference / fine norm | Maximum absolute difference per native file-control setting |
|---|---:|---:|
| Displacement | 0.0135461% | 7.4355e-8 m |
| Rotation vector | 0.0122131% | 5.8654e-7 rad |
| Spanwise twist | 0.0112550% | 5.6571e-7 rad |

These are descriptive Euclidean norms over the sampled common nodes, without interpolation. They are not continuum error bounds or new convergence criteria. The fine mechanical response also reproduces the saved coupled fine-mesh geometry derivative to maximum absolute differences of 4.7056e-15 m and 1.7582e-14 rad per native file-control setting. This is a consistency check under the saved loading; that loading's aerodynamic error is not assessed here.

Exactly two global structural response solves were performed, each with one column-scaled rank SVD, one LU factorization and one right-hand side. Small constitutive/rotation systems and geometry/material evaluations are separately counted in the raw evidence. The maximum mechanical equation residual is 6.725e-17 and the minimum reciprocal condition estimate is 0.0042915, passing the unchanged 1e-8 residual and 1e-10 rank gates. Root reactions balance the common applied wrench. There were no new aerodynamic evaluations, nonlinear equilibria, derivative API calls, finite-difference evaluations or mesh definitions. All owned numerical children completed and were reaped.

The independent saved-output audits pass 1,010/1,010 checks for the aerodynamic study and 1,856/1,856 for mechanics, without new physical calculations, solves, quadrature or rank factorizations. An initial aerodynamic-auditor launch used a Python interpreter without NumPy; it failed before reading results. That environment failure is retained, and the unchanged frozen auditor then passed using the study interpreter.

The small common-load structural changes and selected influence-row agreement narrow the next investigation. They do not allocate the original coupled Cl error between aerodynamics and structure, or establish that all structural responses converge. Global convergence, fixed control-boundary patch error, experimental amplitude/incidence/sign, section-control provenance, fixture/stiffness matching, driven-roll and reversal remain open. No original ASWING executable is available. Coverage stays **17 partial / 24 pending / 0 fully validated**.

Production source, runtime bundles and hosted release are unchanged. No performance gain is claimed.

[Machine-readable results](isae-ae3-component-checks.json) · [Previous decomposition](isae-ae3-clamped-circulation.md) · [Evidence archive](isae-ae3-component-checks-20261024-evidence.zip)
