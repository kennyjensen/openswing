# Controller authority in cold and time solves

The controller time solve now requests the existing final numerical rank check
when accepting cold equilibrium, BDF steps, Radau stages and accuracy-controlled
steps. Previously, only typed inverse-actuator targets requested this check.
Controllers could therefore return a physically ambiguous solution even when
their equations were already satisfied to zero residual.

For example, a 1 kg body with a unit thrust actuator and the controller law
`E1 = Ax` repeats Newton's force balance. Changing the force and acceleration
together leaves both equations satisfied. The correction rejects this smooth
family and the identically zero implicit controller equation. A controller that
loses authority after a valid initial state is checked again at the next step.

Cold initialization still holds declared integral and custom-state values.
Their rates may be nonzero. The patch does not replace initialization with a
steady controller solve. The separate typed inverse-target flag, saved-state
semantics, physical equations, tolerances, finite-difference sizes and retry
policy are unchanged.

## Verification

The isolated focused tests reproduce five missing rejections on the old source
and pass all nine cases on the corrected source. Four positive cases cover
independent force and trajectory values, nonzero owned controller state/rate,
and compatibility of the unused internal steady helper. That helper test does
not establish a public nonunique steady trim feature.

Ten unchanged production tests and four independent mechanics cases pass on the
frozen candidate. The latter compare implicit PI and coupled implicit actuator
responses against an independent variable-step BDF recurrence and Radau [2/3]
matrix stability function. They cover fixed and accuracy-checked paths, including
the retained BDF midpoint. Maximum state/actuator differences are 8.03e-13 and
1.011e-11 respectively. Individual Radau stage physical values are not exported;
the original maximum stage residual is checked against its declared tolerance.

All 39 selected tests pass in the actual main checkout: the nine controller rank
tests, four independent mechanics tests and preceding 26 Newton/checkpoint tests.
The two new test files add 13 cases; complete collection is 1,260 tests. Only
the 39 selected cases were run in this main regression. Imports and all frozen
source/fixture bytes match before and after execution.

Eight actual packaged-WASM public workflows pass on the exact same 58-module
kernel and eight packaged runtime assets. They cover implicit and explicit
degeneracy, regular BDF/Radau motion, owned custom initial state/rate and the
unmodified public failure after a controller loses authority. Maximum force,
acceleration, velocity and position differences are respectively 1.69e-14 N,
1.69e-14 m/s², 1.53e-13 m/s and 5.56e-16 m.

The focused ordinary-BDF transition test stops only after production raises its
real rank error; it uses an observer sentinel to avoid repeating all halvings.
The focused Radau and accuracy transition tests exercise their actual single-step
entry points following public cold initialization. Separate unmodified public
WASM continuation checks cover the final error after production retries.

Counts from different selections overlap and must not be summed as unique
coverage. The complete 1,221-test native baseline predates both preceding
solver-consistency fixes and this controller correction. None of these targeted
results constitutes a new full-suite or browser acceptance result.

## Recorded switching-boundary failure

The following result is on the original 58-module correction. A later
[bounded original-residual diagnostic](controller-nonsmooth.md) rejects this
particular family; the recorded source and failure remain unchanged.

The reused rank test uses centered differences. It is not a general certificate
for nonsmooth controller expressions. On the same body,
`E1 - clip(E1, 0, 1) = 0` has a one-sided family at E1=0. The corrected solver
requests the rank check, which reports a regular centered tangent and accepts
both cold initialization and a BDF step. A +0.3 N force change with the matching
acceleration and trajectory preserves the full residual (zero initially and
2.276e-16 at the step). A -0.3 N change violates the controller row.

This is an unresolved physical ambiguity, not a passing validation case.
Branch-aware authority checks must preserve valid saturation and anti-windup
dynamics. Rejecting every expression containing a kink would not complete that
work. Global branch uniqueness, higher-index controller initialization and broad
aircraft/experimental validation also remain open.

## Records

The accompanying JSON records exact source hashes, selections, terminal results
and archived evidence. Before/after failures, the initial unsupported-panel
fixture, the isolated production collection failure and the nonsmooth
counterexample are retained with their original scope.

- [Machine-readable record](controller-time-rank.json)
- [Original public counterexamples](controller-time-rank-before-evidence.zip)
- [Focused before/after evidence](controller-time-rank-focused-evidence.zip)
- [Independent production regression](controller-time-rank-production-evidence.zip)
- [Actual main regression](controller-rank-integrated-evidence.zip)
- [Packaged WASM runtime and replay](controller-time-rank-wasm-evidence.zip)
- [Unresolved clipping-boundary counterexample](controller-one-sided.md)

Run the integrated focused cases with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_feedback_time_rank.py tests/test_feedback_time_recurrence.py tests/test_newton_rank.py tests/test_checkpoint_frame.py
```

The user goal remains active; all 40 broad requirements remain Partial.
