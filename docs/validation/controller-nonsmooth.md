# Bounded controller ambiguity diagnostic

The controller time solver now checks for resolved nearby alternatives that
satisfy the complete original residual at its original tolerance. This addresses
the recorded `E1 - clip(E1,0,1) = 0` boundary family, which can appear regular to
the centered rank check. It preserves unique saturation, unequal one-sided
slopes, and declared controller initial values.

Only syntactically nonsmooth expression controllers request the extra probes.
The diagnostic uses explicitly owned controller rows in cold initialization,
BDF steps, all three Radau stages, and accuracy-controlled steps. The accepted
physical cache is restored after probing. Invalid optional probes are not
evidence of ambiguity; programming errors still propagate. The numerical
construction and thresholds are in [NUMERICS.md](../NUMERICS.md).

## Retry ownership

An earlier diagnostic used the ordinary recoverable `StepFailure`. On a 1 kg
body with `E1 - clip(E1,0,time) = 0`, the initial force is uniquely zero but every
positive time has a force/acceleration family. Step halving narrowed the family
below the diagnostic's finite sample distances. That attempt accepted five
intermediate steps before ultimately failing after fifteen rejections; it did
not produce a converged result. Its exact evidence is retained.

The correction raises a specific `UnresolvedControllerAuthority` subtype. Both
marching loops propagate it before their normal retry handler. The same public
BDF1 and Radau examples now stop at the first requested endpoint, with only the
initial snapshot, zero accepted steps and zero retries. The full residuals at
the witnessed alternative states remain within the original tolerance. Smooth
Newton/rank and other recoverable step failures retain their existing retries.

## Scope

This is a finite diagnostic, not a general nonsmooth uniqueness certificate.
It can miss narrow or curved families and does not cover generalized nonlinear
initial derivative arrays or every source of switching in the physical model.
Refusing an attempted run after a witness does not prove that every smaller-step
problem is nonunique. All broad ASWING requirements remain Partial.

## Verification records

The isolated candidate preserves the original failure, the optional-domain
probe correction, and the retry-evasion attempt. Its 26 focused controls and two
unmodified public BDF/Radau calls passed. The new main tests additionally cover
actual public accuracy-controlled BDF/Radau refusal and the independent unique
boundary equation `F = clip(.3-.5*a,0,.2)`, with `F = m*a` and `m=1 kg`. Its unique
solution is `F=.2 N`, `a=.2 m/s²`; the BDF1 and Radau trajectory checks use their
independent discrete formulas. No physical solver method is intercepted or
injected in those public tests. Separate synthetic tests check retry dispatch
and make no mechanics claim.

All 68 selected tests pass in the actual main checkout: 29 new tests and 39
unchanged controller-rank, independent recurrence, Newton and checkpoint cases.
All 204 setup/call/teardown phases pass; the exact 59-module kernel, test and
fixture pins remain unchanged, and 38 actual imported modules match main. The
complete collection is 1,289 tests; this is not a full-suite execution.

All 13 actual packaged-WASM public workflows pass on that same kernel: eight
unchanged prior rank checks, the cold clipping-family refusal, BDF/Radau
time-opening-family refusal, and two saturated negative-feedback mechanics
cases. Original residuals at the witnessed cold/BDF/Radau alternatives are at
most 0, 1.138e-15 and 7.106e-16, respectively. The two positive cases use
`F=clip(.3-.2*a,0,.2)` and independently require `F=a=.2` for the 1 kg body.
The exact 59 modules, eight runtime assets and 38 actual imports are recorded.

One actual offline mobile browser workflow also passes on that same kernel.
It first displays the cold clipping-family refusal and disables result exports,
then accepts the unique `.2 N` saturation-boundary case after editing the law.
The exported acceleration, velocity, position and original Radau stage residual
meet their independent gates. All 59 worker module hashes match main. Its UI
predates the subsequent requested editor-theme change; that visual change has
separate verification.

The records retain exact sources, inputs, outputs and original failed attempts:

- [Machine-readable scope and hashes](controller-nonsmooth.json)
- [Candidate diagnostic, domain handling and retry history](controller-nonsmooth-evidence.zip)
- [Actual main 68-test regression](controller-nonsmooth-main-evidence.zip)
- [Packaged-WASM 13 public workflows](controller-nonsmooth-wasm-evidence.zip)
- [Offline browser refusal and physical trajectory](controller-nonsmooth-browser-evidence.zip)

Earlier complete-suite and browser results retain their original fingerprints.
