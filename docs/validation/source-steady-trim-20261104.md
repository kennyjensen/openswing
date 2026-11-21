# Steady trim with the source structural equations

Mounted analysis using `drela-steady-coupled-v1` now solves ordinary operating
targets together with beam deformation and circulation. Previously this route
rejected every target, even though the common operating-equation system already
implemented them. It now passes the requested constraints into that system.

The [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes adding constraints to determine free operating parameters, explicitly
including specified lift in place of prescribed incidence or speed. This change
uses those existing full residual equations, with the source section laws and
endpoint load transfer. It adds no outer fitting loop or approximate load model.
Physical coefficients, convergence tolerances and default numerical selections
are unchanged.

In the workbench, select **Mounted aeroelastic equilibrium**, then
**ASWING structure + steady aero** under **Structural equations**. Add an
operating target, for example variable `alpha`, quantity `CL`, target `0.4`.
The solved settings appear in Output and accompany the saved equilibrium and
computed solution. The JSON API uses the same `operating_constraints` records.

The supported unknowns are speed, incidence, sideslip, Earth pose, flap settings
and engine settings. Frame rates and accelerations must remain prescribed at
zero. Custom sensor equations, minimum-control allocation, feedback, derivatives,
stepped axes and dynamic launches remain outside this steady policy. In
particular, accepting ordinary trim does not establish full ASWING feature parity
or justify changing the browser's default equations.

## Verification

All **137 Python checks** and **18 JavaScript checks** pass in bounded serial
jobs. The Python total comprises 83 trim/request checks and 54 existing coupled
aerodynamics, engine and operating-point regressions.

The new physical cases check:

- Engine-force trim against the exact axial-bar extension `F L / EA`: 5 N gives
  0.010 m and 8 N gives 0.016 m. The second target reuses the first saved
  equilibrium. Forces, reactions and a fresh full residual are checked.
- Simultaneous incidence/flap trim against a separately prescribed loaded wing
  state. Solved settings, aerodynamic coefficients and all node positions agree;
  full residual derivatives agree at two perturbation sizes.
- Specified-lift speed trim together with Earth attitude targets, including the
  resulting gravity loading and deformation.
- Rejection of released rates or accelerations, malformed constraints and
  unsupported custom/allocation rows before attempting an incompatible solve.

The physical comparisons require fresh residuals below `2e-9`; the underlying
solves use `1e-10`. These are implementation checks, not native ASWING reference
comparisons, and change no ISAE scores.

The actual built browser passes two offline solves, computed-project
save/restoration without recomputation, and a changed-target warm start. The
complete workflow takes 32.84 s in this observation. Both exact exported
requests are then replayed in native Python: **3,946 numeric fields** pass
`2e-8 + 2e-8 * abs(reference)`, with maximum gate fraction `2.975e-9`.
Only the execution counter is excluded. The two native replays take 2.93 s
and 1.19 s. Browser residuals are `4.34e-19` and `1.94e-13`; the latter takes
one Newton correction from the saved state. No page errors, failed requests
or requests after disconnection occur.

The built app contains the same 137 kernel modules as Python; four modules
change, while the remaining 133 retain their previous hashes. The
[portable evidence](source-steady-trim-20261104.json) retains hashes, gates and
comparison results. This verifies a small engine/bar browser case; the loaded
lifting-wing trim checks run natively. It is not a broad aircraft trim study.

Two pre-existing bridge-test assertions were stale after earlier strut support:
one omitted the forwarded strut option and one expected wire mode to be rejected.
Their failing baseline is retained. The first new lift test requested a
nonexistent absolute `lift` output; it now obtains force from the reported
coefficient and the specified dynamic pressure/reference area. Neither fix
changes a physical gate. Browser harness setup failures are retained as well.

Code: [source solver](../../openswing/source_coupled.py),
[request validation](../../openswing/numerical_policy.py),
[physical tests](../../tests/test_source_steady_trim.py), and
[browser workflow](../../tests/browser/source-steady-trim.spec.js).
Logs, original changed files, source hashes and complete browser/native results
are retained in `artifacts/isae/source-steady-trim-20261104/`.
