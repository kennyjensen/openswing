# Rigid circulation initialization at nearly zero lift

2026-10-30. A browser operating-point sequence exposed a numerical failure in
the rigid supplied-circulation solve. The retained nominal zero-lift seed has
maximum magnitude `2.87e-322`. At 5°, direct correction failed at normalized
residual `0.0872`; an exact-zero seed converged. This is an initialization
defect, separate from the remaining ISAE aerodynamic discrepancies.

## Cause and correction

MINPACK's [HYBRJ source](https://netlib.org/minpack/hybrj.f) initializes its
trust radius to `factor * norm(diag*x)`, with a finite default only when that
product is exactly zero. The retained six-strip problem starts with radius
`4.94e-322`. An independent scalar witness, `x - 1 = 0`, also stalls from
`1e-322`, `1e-300` and `1e-18`, while zero and ordinary starts converge.
The [HYBRD source](https://netlib.org/minpack/hybrd.f) has the same initial-radius
rule for numerical Jacobians. This behavior is therefore not confined to
floating-point subnormals or aerodynamic equations.

The supplied-seed path now solves for a dimensionless increment:

```
A = A_seed + s*z,    z_initial = 0
s = max(0.5 * chord * speed)
Gamma = B*A
dR/dz = (dR/dA) * s
```

Here `A` is the pointwise or Fourier coefficient vector and `B` its existing
sampling matrix. The physical initial circulation is preserved. The scale is
the existing circulation scale used by the continuation and polishing paths;
it transforms as length squared divided by time. There is no tiny-circulation
cutoff, force correction, parameter fit, or change to the residual equations.

An increment-only version fixed the stall but exposed loss of relative accuracy
when `A_seed + s*z` cancels near a zero final circulation. The first stack WASM
comparison failed: zero-incidence span efficiency was `0.14365` natively and
zero in WASM. That failed run is retained, rather than removing efficiency
from comparison.

After an incremental solution meets the existing residual gate, a final solve
in absolute dimensionless coefficients recovers relative accuracy. Its result
is accepted only if the fresh residual strictly improves and the physical
circulation change remains inside the existing terminal-polish neighborhood,
`1e-8 * max(s, max(abs(Gamma)))`. Failed, nonfinite, nonlocal or nonimproving
refinements retain the converged incremental state. External deadlines still
propagate. The original final residual, local-Mach, fallback and direct-solve
rules remain in force; both stages and their evaluation counts are reported.

Cold and prescribed-circulation paths have identical Python syntax trees after
excluding the supplied-seed block. Eight complete cold results and eight
prescribed results on straight/stalled wings and pointwise/Fourier bases are
also compared bit-for-bit against the saved pre-change module. This does not
authenticate a native ASWING initialization or nonlinear branch choice.

## Evidence

The [retained evidence directory](../../artifacts/isae/rigid-seed-increments-20261030/)
contains the preparation, original module, MINPACK source, scalar diagnosis,
failed pre-fix tests, intermediate increment-only outputs, and final replays.
The portable original browser request is
[tests/fixtures/rigid-subnormal-seed.json](../../tests/fixtures/rigid-subnormal-seed.json).
The initial regression run reproduced five failures among thirteen cases.

The regression coverage includes physical seed preservation; fresh residuals
and loads; analytic directional derivatives; numerical engine feedback;
Fourier modes; zero lift and true nonzero incidence down to `1e-18` degrees;
consistent SI, millimetre, foot/pound-force and scaled-time units; failure and
nonlocal-refinement retention; and the independent nonlinear finite-wing oracle.
Actual zero-lift efficiency remains in the portability comparison. Tiny
nonzero circulation is also checked relatively, so replacing it with zero
cannot pass merely because the absolute values are small.

Final checks:

- **174 native tests pass.** This includes the new failure reproductions and
  the existing seed, fallback, operating-stack and finite-wing checks.
- The literal failing seed now converges directly at residual `9.35e-18`.
  In `auto`, it uses **12 residual evaluations versus 17 before**, eliminating
  its cold retry. This is an evaluation-count observation for this case, not a
  general runtime benchmark.
- **617 seeded WASM comparisons pass**, including pointwise/Fourier engine
  feedback and zero/tiny lift. Maximum scaled difference is `1.21e-12`.
  Twelve additional relative circulation checks pass, maximum `2.74e-16`.
- **764 operating-stack WASM comparisons pass**, maximum scaled difference
  `4.09e-9`, retaining physical rejection and recovery after a failed point.
- The production-browser offline polar workflow passes. All three seeded
  points, including zero incidence followed by 5°, accept their seed without
  a cold retry. Source-coupled mounting, exports, inspection, project migration
  and mobile rendering remain covered by the same workflow.

The frontend and dependencies match the previously built source archive in
all 60 checked files. Only the runtime-loaded Python kernel needs replacing
in that browser build; source and local-app downloads are refreshed and their
kernel/source contents checked. The existing frontend assets are retained.

Only the supplied-seed block of `openswing/aero.py` changes production Python.
No native ISAE target, tolerance, pass count, stall law, wake model, default
mesh or mounted-equilibrium equation changes. The full ASWING goal remains
incomplete, including the existing SA-1–SA-5 discrepancies. The prior mounted
continuation timing limitation is unaffected by this rigid-solver correction.
