# AE-4 stationary-wall unsteady support and first modal comparison

The first conditional AE-4 comparison now runs with the original solid-wall
image plane enabled. At the declared 40 m/s condition, the three positive
frequencies differ from archived operating index 41 by 0.0032–0.0616%; damping
components differ by 0.0686–0.5043%. This is not a completed flutter-boundary
validation or a registered native pass. Historical settings and the operating
index correspondence remain qualified below.

## Published equations and implementation

The local primary references are `.reference/asw_theory.txt`, section 4.5,
Eqs.165–175, and `.reference/asw_uns_theory.txt`, sections 5–6, Eqs.28–44.
The steady image construction is applied to the instantaneous circulation and
geometry in unsteady Eq.32. The volume field remains quasi-steady. The published
local apparent-mass equations, 43–44, do not introduce a separate wall-dependent
tensor. This implementation follows that approximation; it does not claim an
exact three-dimensional potential-flow added-mass solution near a wall.

The earlier wall-root guard rejected every nonzero elastic or circulation rate,
including motion away from the stationary clamp. It now admits interior motion
and time-varying circulation while requiring the physical clamp to remain
stationary. Arbitrary imposed gusts, aircraft frame motion, normal onset flow,
and propulsive jets at a wall mount remain rejected.

Modal matrix and output derivatives now own the existing bounded extension of
root geometry off the clamp constraint. They also extend root rates for the
complete descriptor's independent columns and polynomial coefficient probes.
The full clamp and kinematic equations remain present. This extension ends with
the derivative operation and invalidates cached probe loads; it does not waive
physical geometry or clamp-motion checks. No force equation, stiffness, mass,
Newton criterion, eigenvalue shift, or acceptance tolerance was fitted.

## Independent checks

Eight moving half-wing versus explicit full-mirror comparisons cover straight
and bent/twisted geometry, Mach 0 and 0.55, and aerodynamic lag on/off. Local
relative flow, circulation residuals, integrated forces/couples, circulation-rate
loads and apparent-mass loads agree at 2e-11 relative plus 2e-12 absolute
tolerances. Independent wall probes have zero normal induced velocity for both
circulation and circulation-rate fields within 2e-14.

Complete dense and sparse source modal matrices agree and reproduce separate
full-residual directional differences. Output derivatives restore the strict
physical boundary after success and after exceptions. The existing steady
wall-root tests pass. Logs retain two modal-fixture setup mistakes and a test
that initially moved a root away from the wall when it intended to test
penetration; only those fixtures were corrected.

## Original case and conditional correspondence

The reference revision is `f62943df20e9e4d7d9f50e070477b22426b5f865`, under
`4 - Aeroelasticity/AE - Aeroelastic Cases/AE-4-D Pazy Wing - Flutter boundaries/2-Flutter_Undeformed`.
The literal `Pazy_wing.asw`, `alpha_0.sh`, `alpha_0_eig.txt`, and sensor table
are retained and pinned in the run plan. The plan also inventories the entire
AE-4 folder and any `.set`, `.pnt`, or `.con` files it contains.

The original script specifies `I 40`, solid images with Earth normal `(0,0,1)`,
beta zero, IAS 1 through 109, and `NN 4` followed by `0 200`.
The manual identifies the latter as a complex eigenvalue shift, **0 + 200i
rad/s**, not a frequency range. `OPER % D` exits the constraint editor; it does
not select anchored defaults.

Every speed command follows `+`. Under the manual's insertion semantics and
one initial point, IAS 40 corresponds to operating index 41. The native sensor
table has 110 rows, but the modal file has 300 roots at indices 1–109. The author
MATLAB helper labels operating indices themselves as speed. This unresolved
offset and the missing last modal point are preserved, not selected by whichever
mapping gives a smaller error. The initial operating point and any historical
autoloaded settings are unknown.

The current declared conditions are fixed frame, alpha/beta zero, identity Earth
pose, density 1.23, gravity 9.81, PG Mach zero, pointwise circulation, enabled
aerodynamic lag and updated influences. At this density IAS equals TAS using
the file's own sea-level reference. The mesh uses nominal 40 cosine intervals
and retains the material break: **41 actual elements, 42 nodes**. Historical
node-spacing/count bookkeeping and aerodynamic flags are unconfirmed.

| Positive root | Archived real part | Current real part | Real-part error | Archived imaginary part | Current imaginary part | Frequency error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -7.0346911 | -7.03951854 | 0.06862% | 28.162071 | 28.16296997 | 0.003192% |
| 2 | -5.8716763 | -5.90128810 | 0.50432% | 183.62531 | 183.73838906 | 0.061581% |
| 3 | -6.0418110 | -6.05934009 | 0.29013% | 254.66131 | 254.64357124 | 0.006966% |

Eigenvalues have units 1/s. Positive selected roots are compared in increasing
frequency; archived mode-shape correspondence is not established. The fourth
selected current root is the negative-frequency conjugate of root 1. All 13
source, base, full left/right pencil and mass-normalization checks pass. None of
the six scalar components matches its archived printed-precision interval.
Four additional checks confirm that root displacement, rotation, velocity and
angular-rate components remain zero to within 2.46e-16 of the mode's largest
scaled component, against a 1e-8 gate. The derivative extension has not freed
the physical mount.

The original solve completed and saved its full result before the report writer
used an incorrect `counts` field. Assessment was corrected using the retained
result, with **zero additional solves** and unchanged physics/checks. Its initial
failure log remains. Exact solve-only timing was not saved on that first run;
the failure timestamp is not reported as a solver benchmark.

## Remaining work

All 67 distinct Python checks pass. The built offline WASM worker
passes 10/10 gates and 1,281,454 numerical
comparisons, covering the complete base state, both full matrices and every
selected eigenvalue. Every browser left/right vector also passes its own
full-pencil check. The browser solve takes 39.163 s in this run.
This verifies the worker; UI control selection is outside this test.

AE-4 still needs spatial/difference-step refinement,
original speed/incidence coverage, flutter crossings and mode tracking, and
registration accounting for duplicate and unpaired exports. Nonlinear LCO and
moving/gust wall configurations remain separate open requirements.

Evidence: `artifacts/isae/wall-unsteady-20261105/`. Reproduction helper:
`scripts/verify-isae-ae4-wall-modes.py`; one new case per directory, with process
limits supplied by the caller. `--assess-only` rechecks a saved result without
solving. Browser helper: `scripts/test-wall-modes-browser.mjs`.
