# Mounted source sections coupled to steady aerodynamics

Updated 2026-10-26. Acceptance means reproducing tested **ASWING outputs with
original models and operating settings**. Matching experiment is optional.
This increment implements conservative aero/structural coupling and compares
all four saved outputs at one original AE-2 coordinate. It does **not** close
the archived-reference discrepancy.

## Implementation

Settings → Mounted aeroelastic equilibrium → Structural equations now offers
**ASWING structure + steady aero · experimental**. Its explicit numerical pair
is `drela-segspl-v1` / `drela-steady-coupled-v1`. The preceding two structural
source policies and the default midpoint policy retain their identities.

The new operator uses the general-section offsets, coupled stiffness, finite
axial/shear compliance and distributed-CG gravity rules. It retains the
existing aerodynamic interval circulation and Glauert-midpoint quadrature.
Physical aerodynamic frames remain orthonormal; the structural average
transform is not an aerodynamic frame. Each strip wrench is transferred with
equal endpoint forces and equal endpoint couples about the structural midpoint.
This conserves force and moment while keeping the mixed internal resultants
equal to their physical endpoint averages. Circulation derivatives use the
same transfer. No additional half-velocity-point arm is added to the section
couple. This follows the distinctions in Drela's
[ASWING theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
particularly structural averaging versus aerodynamic collocation. The exact
historical quadrature/transfer implementation remains unproven.

The gravity cache remains independent of aerodynamic loads, including the
reported real-mass reaction term. Newton probes skip full plotting/sensor
report construction while retaining identical residual equations.

The option supports prescribed stationary mounted conditions. Steady controls,
atmosphere, frozen influences, ground effects and spatial-gust snapshots retain
their existing definitions. Operating constraints, controllers, derivatives,
dynamics, nonzero motion, body charts, stepped axes, non-rigid joints, struts
and engines remain outside this policy. Dynamic inertia/spin are unavailable.
Changing to an incompatible analysis selects the default and reinspects.

## Unchanged AE-2 comparison

The model is the original `[03_90].asw` from the ISAE AE-2 steady-deflection
folder, commit `f62943df20e9e4d7d9f50e070477b22426b5f865`, SHA-256
`eb35a50606bcceee263352cbd40ffd509b504082c78ba61732ad52ce03193db8`.
The run script establishes sideslip 5° and speed 10 m/s. Comparison uses the
unmodified row 11 (physical line 14) of `[03_90]_A5.txt`; no baseline is
subtracted and stack indices are not interpreted as physical time/speed.

The declared candidate uses density 1.23, gravity 9.81, fixed Mach zero,
frozen influences, the original full-flow sensor, and the existing W=0.25.
Historical ASWING K/F/PG settings, exact mesh, atmosphere/startup and sensor
implementation are unresolved. This is a conditional operating-point
comparison, not a claim that those missing historical choices are known.

| Output | Archived ASWING | New source coupling, 161 intervals | Difference |
|---|---:|---:|---:|
| Sensor RY, m | −0.0258200 | −0.0259323281 | −0.0001123281 (0.4350%) |
| Sensor heading/twist, degrees | −0.572223 | −0.574174385 | −0.001951385 (0.3410%) |
| Sensor speed, m/s | 10.0115 | 10.009076772 | −0.002423228 (0.0242%) |
| Sensor sideslip, degrees | 6.27943 | 6.141835427 | −0.137594573 (2.1912%) |

None matches the archive's printed half-last-place precision. These descriptive
percentages are not substituted acceptance tolerances. Four native solves
compare current default and new source policies on the same 81/161-interval
grids (nominal 80/160, with the exact clamp station retained):

| Formulation | Intervals | Cold solve | Fresh residual |
|---|---:|---:|---:|
| Default midpoint | 81 | 1.21 s | 4.04×10⁻¹⁴ |
| Source coupled | 81 | 1.12 s | 5.84×10⁻¹³ |
| Default midpoint | 161 | 5.39 s | 6.07×10⁻¹³ |
| Source coupled | 161 | 1.62 s | 7.16×10⁻¹³ |

These are single runs on this host, not a general speed benchmark. All 66
physical/restoration checks pass, including force/moment balance and the clamp.
Paired node/station grids agree. All four deflection/twist mesh checks pass the
predeclared 1% gate; the source fine-grid changes are only 0.00176% and 0.00280%.
All 16 strict printed-output comparisons remain failures, kept separately.

At 161 intervals, changing the structural coupling changes RY by only
2.84×10⁻⁸ m and sensor sideslip by 3.80×10⁻⁶ degrees. It therefore does not
explain the existing AE-2 gap. No model properties, aerodynamic constants,
operating settings or acceptance tolerances were fitted to reduce that gap.
This covers one of the 87 finite AE-2 coordinates, not the whole family.

## Verification

Eight focused tests pass, covering independent rational transfer targets,
reference-origin/rotation conservation, circulation columns against two full
residual stencils, gravity-cache separation, zero-airflow identity, scope
checks and two small synthetic equilibrium limits. The first attempt exposed
a test fixture dividing a Python list by a scalar; converting its two literal
vectors to arrays fixed the fixture. Original failure and continuation are
retained; no production physics or tolerance changed between those attempts.

The existing structural/recovery/sensor/circulation/solver suite passes 100
tests. Boundary checks pass 181 Python and 29 JavaScript tests; five existing
solve-bearing tests were excluded from that boundary run. The four native
AE-2 solves above exercise the actual bridge and new formulation.

An independent audit of the saved fields passes 605/605 checks, including
sensor position/axes/heading/flow reconstruction, strip totals, and each source
interval’s gravity-subtracted aerodynamic wrench at three reference origins.
It performs no solves or residual evaluations and confirms all four mesh gates
and all 16 strict reference failures.

The sole offline browser solve takes **5.61 s**, after **42.35 s** of verifier
preflight/browser/runtime startup. All **44,049 numeric values** agree with
native output under the predeclared 2×10⁻⁸ absolute plus relative criterion;
maximum absolute difference is 9.03×10⁻¹³. Only the evaluation counter is
excluded. These are single-run measurements on this host.

The final saved-result continuation passes **1,110/1,110 checks** with zero
additional solves. It restores the exact new result/project and all three
preceding policy generations, verifies mode/import behavior and renders desktop
and mobile plots. No HTTP requests occur after startup, and no page/network
errors occur. The continuation reports its own startup separately (59.02 s).
The first browser attempt tried a collapsed project control before solving;
the second completed solve/parity/export checks but incorrectly expected shell
strain from a model without shell coordinates. Both failures are retained. The
continuation selects supported curvature without changing the model or solver.

The [checked AE-2 project](../../examples/isae-ae2-source-coupled-project.json)
contains one original case and its exact saved solution; it opens without
recomputing. The [machine-readable report](isae-source-coupled.json) retains
physical verification and reference failures separately. See the
[reference status](isae-aswing-reference-status.md) for the separate P-1,
ST-3 and ST-5 comparisons. The full ASWING implementation remains incomplete.
