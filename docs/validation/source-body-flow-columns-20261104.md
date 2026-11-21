# Consistent source body-load derivatives

Date: 2026-11-04. Twelve focused Python checks and two offline WASM cases pass.
The [structured record](source-body-flow-columns-20261104.json) retains the
source hashes, differential checks and native/browser comparison.

The source wing/body residual integrates each body strip's force and moment,
then transfers that section wrench symmetrically to its two endpoints. The
direct flow derivative previously used the generic quadrature-dependent nodal
weights for bodies. Both transfers can preserve total force and moment while
producing different individual nodal balances. The resulting derivative was
therefore inconsistent with the nonlinear source equations.

At fixed geometry, the corrected derivative first sums the body quadrature
force derivatives and their moments about the aerodynamic section point. It
then calls the same source transfer as the physical residual. For section
force F, moment M about r_m, and structural midpoint r_mid, each endpoint gets
F/2 and (M + (r_m - r_mid) cross F)/2; the derivative uses this same linear map.
Generic network transfer, physical load formulas, nonlinear residuals, solver
tolerances and all acceptance gates are unchanged.

Two original wing/body derivative checks failed before the correction, with
maximum scaled entry error 6.08743e-5 against a 2e-8 gate. Four checks now pass:
fixed-frame circulation columns, BDF circulation/rate columns, free-frame load
rows, and the Fourier circulation representation. Each compares every column
against two independent full-residual stencils at a loaded, moving geometry
with frame rotation, gravity, local velocities/accelerations and ground images.
The retained fixed-frame case has maximum scaled error 5.204e-12; the retained
free-frame Fourier case has maximum error 2.962e-11. These are derivative errors,
not percentages of an aircraft response or a native ASWING discrepancy.

A converged wing/body dynamic system also passes three independent state and
three rate directional checks of its complete assembled A/M matrices. Seven
existing checks pass for generic wing/body circulation and local-motion
derivatives, stepped bodies, frozen influences and source lifting-surface
circulation transfer. Together these are twelve distinct Python cases.

The shipped WASM runtime passes two offline full-residual checks: fixed-frame
panel circulation and free-frame Fourier circulation with the BDF rate term.
All 138 loaded kernel hashes match source/public/dist. All 1,136 matrix and
residual comparisons against native Python pass the unchanged
`2e-8 + 2e-8 |native|` gate. The largest difference uses 1.11e-8 of its allowed
gate. There are no page errors or HTTP requests after going offline. This is a
kernel test; it does not claim a new full workbench/project workflow.

The correction affects linearized source body coupling used by aerodynamic
derivative assembly, including modal and frequency calculations. It establishes
consistency with the complete current residual, not historical executable
agreement. All 42 ISAE rows and their error summaries remain unchanged. Full
ASWING functionality and native validation remain incomplete.

Code and checks: [flow-load derivative](../../openswing/circulation_tangent.py),
[source section transfer](../../openswing/source_coupled.py),
[physical differential oracle](../../tests/source_body_flow_case.py),
[assembled-matrix regression](../../tests/test_source_body_flow_columns.py),
[offline WASM test](../../tests/browser/source-body-flow-columns.spec.js).
Requests, results and execution logs are retained in
`artifacts/isae/source-body-flow-columns-20261104/`.
