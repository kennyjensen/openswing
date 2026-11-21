# Continuous Fourier wake reference diagnostic

2026-11-01. OpenSwing now provides an explicit continuous-wake reference
calculation for straight Fourier traces in free space. It makes the
SA-7 wake-integral investigation available through the solver API without
changing the coupled solver's discrete force or derivative definitions.

The [nonparallel extension](fourier-wake-nonparallel-20261101.md) now supports
arbitrary straight-trace orientations, shared endpoints and crossings. That
follow-up retains the original 58-state SA-7 agreement and checks 20 saved
SA-10 states. The verification counts below describe the initial parallel
implementation; the extension has its own tests, replay and receipt.

## Use

```python
from pathlib import Path
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid

model = parse_asw(Path('examples/rectangular.asw').read_text())
condition = FlightCondition(speed=30, alpha=5, circulation_modes={1: 12})
result = solve_rigid(model, condition, panels=48, fourier_wake_diagnostic=True)
reference = result['trefftz']['continuous_fourier']
print(reference['available'], reference['CDi'], reference['reason'])
```

`evaluate_aerodynamics` accepts the same keyword for prescribed-circulation
and supplied-mesh evaluations. `fourier_wake_forces` in
[fourier_wake.py](../../openswing/fourier_wake.py) also accepts explicit trace
endpoints and sine coefficients for analytical comparisons. It reports wake
force, rolling impulse, induced drag, efficiency, the mutual energy matrix and
quadrature convergence information.

Every lifting beam must already have a selected Fourier representation. The
diagnostic uses its coefficients directly; it never fits a Fourier series to
an undeclared pointwise solution. Node and sample geometry are checked against
the material cosine coordinate before treating a projected trace as straight.
An unsupported trace, ground image, mixed pointwise basis or unresolved
quadrature returns `available=False` and an explanation.

The option is off by default and its module is imported only when requested.
The main `CDi`, `efficiency`, loads, residuals and linearized outputs retain
their existing definitions. No geometry-dependent switch is inserted into
the coupled solver's output path. Browser controls and refreshed packaged
kernels were pending in this initial implementation. The later
[rigid browser control](fourier-wake-ui-20261101.md) is wired in source, with
native JSON and JavaScript checks; rendered/WASM verification and refreshed
bundles remain pending. No browser or build run was performed here.

## Mathematics and safeguards

The reference uses the circulation in steady equation 63 and wake forces in
equations 207–211 of the
[ASWING description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
For `Gamma(theta) = sum A_n sin(n theta)`, a straight trace has exact self drag

`D_self = rho pi/8 sum(n A_n²)`.

Lift and rolling impulse also use exact sine integrals. A complex Chebyshev
resolvent evaluates each source's continuous velocity analytically. Only the
target integral needs numerical quadrature. Source-tip neighborhoods are
partitioned and transformed to resolve the integrable singularities when
unequal traces lie in the same plane. Target quadrature is refined and mutual
reciprocity is checked; neither an unresolved result nor an arbitrary core
radius is substituted.

The routine works in a common wind-normal frame, including rotated traces,
reversed beam orientation and arbitrary staggering along the wind. Identical
projected traces are combined before integration, preserving cancellation.
Coefficient scaling retains very small nonzero circulation. Negative total
energy beyond roundoff is unavailable rather than reported as valid drag.

This is a reference integral for its stated representation, not an assertion
that a historical native ASWING executable used this reporting algorithm.
General curved traces and image wakes remain outside its current
scope. The primary discrete solver continues to handle its existing geometry
and image cases.

## Verification

**34 targeted tests pass**: 33 existing/new wake and Fourier-regression checks
in 7.93 seconds, plus one independent coplanar-ellipse check in 5.24 seconds.
Controls cover exact modal energy and rolling impulse, an independent adaptive
line integral at the SA-7 near-alignment gap, coplanar unequal elliptical wakes,
opposite-wake cancellation, nonnegative energy through alignment, rigid-frame
invariance, reversed orientation, circulation scaling down to `1e-80`, and
explicit rejection of unsupported or unresolved inputs. Existing solver outputs
remain unchanged when the optional diagnostic is added.

The coplanar-ellipse control has a closed form: the smaller trace lies entirely
inside the larger elliptical wake, where downwash is constant. This verifies
the tip-singular reverse integral through reciprocity, independently of the
production quadrature scheme.

All **58 saved SA-7 fields** were additionally reevaluated as prescribed
circulation in their full square Fourier bases. Those bases are determined by
the saved samples, with no native-target fit. No nonlinear ISAE solve is used.
The API diagnostic matches the preceding independently verified reconstruction:

| Check | Maximum difference |
|---|---:|
| Existing force output | 0 |
| Existing discrete CDi | 0 |
| Continuous CDi | 1.39e−15 |
| Continuous efficiency | 3.56e−15 |
| Continuous circulation lift | 5.78e−15 |
| Weighted circulation residual | 1.61e−13 |

The replay completes in 1.81 seconds after imports in one process with one
BLAS thread. The original audit supplies independent 60-digit source-integral
checks. The first test attempt used the wrong density for the rectangular
fixture; the fixture was corrected and the initial log retained.

This adds an implemented verification capability, not new registered ISAE
passes. SA-7's registered family remains **395/812**; the separate smooth-wake
coarse diagnostic remains **197/203**, with six post-stall CDi failures. All
42 status-table rows are unchanged. The full project remains incomplete.

[Replay plan](../../artifacts/isae/fourier-wake-diagnostic-20261101/plan.json),
[58-state replay](../../artifacts/isae/fourier-wake-diagnostic-20261101/replay.json),
[tests](../../artifacts/isae/fourier-wake-diagnostic-20261101/tests.log),
[coplanar control](../../artifacts/isae/fourier-wake-diagnostic-20261101/coplanar-test.log),
[receipt](../../artifacts/isae/fourier-wake-diagnostic-20261101/receipt.json).
