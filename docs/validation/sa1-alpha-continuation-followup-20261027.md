# SA-1: nonlinear law and operating-point continuation

SA-1 remains **19/154 registered archived-output checks passing**, with all
22 baseline jobs complete. This follow-up checks the section stall law and
whether a different initialization path changes the current solutions. It
does not change the model, documented equations, acceptance tolerances or
production solver.

## Source review

The [nonlinear-law review](sa1-nonlinear-law-review-20261027.md) independently
checks the printed equations in steady descriptions 5.60 and 5.99. The signed
logarithmic leakage, perpendicular-speed normalization and finite-angle
geometry agree with the implementation. No additional cosine factor, hard
clipping rule or historical stall constant was established.

The soft transition already matters below the nominal section lift limit:
at 18.091 degrees the saved maximum section cl is 1.15007, below CLmax=1.2,
while maximum leakage/freestream speed is 0.099897. The output Boolean
`stalled` only checks limit crossing. Zero flagged strips does not mean the
smooth separation model is inactive.

The [retained branch review](../../artifacts/isae/sa1-alpha-continuation-20261027/cold-branch-review.json)
finds no turn in the regularization parameter of the eight high-angle cold
continuation traces. All reach zero regularization with residuals below
9.18e-14. The lift discrepancy is already present at 12.1 degrees, where the
current solver uses direct Newton. These observations do not prove global
uniqueness or reproduce the archived executable's initialization.

## Controlled initialization check

The original driver creates eleven ascending incidence entries before its
`XX` command. The guide describes parameter inheritance and convergence of
the stack, but does not establish whether the executable seeds each solve
from the previous converged circulation. The diagnostic therefore tests
initialization sensitivity without claiming to recover that historical detail.

Each existing 200/400-interval mesh starts at the exact zero-incidence,
zero-circulation solution. The eleven original angles are then visited in
order, with the preceding accepted circulation as the next initial guess.
The fixed policy uses the exact Jacobian, Newton/Armijo correction, a
1e-11 normalized residual gate, and at most 100 corrections per target. A
failure stops that mesh; there are no retries, angle subdivisions, clipping,
parameter changes or choices based on agreement with native output.

For this straight constant-chord wing, the scalar horseshoe matrices are
independent of incidence in current wind coordinates. Physical velocity,
force and control-point coordinates rotate at every angle. This exact
special-case reduction is not the frozen-influence approximation.

## Preserved preflight failure

The [first attempt](../../artifacts/isae/sa1-alpha-continuation-20261027/summary.json)
stopped before any Newton solve because its mandatory saved-state replay
exceeded the 1e-10 gate. Reconstructing material sample coordinates from
stored node angles changed them by at most 2.22e-15 m; the near-tip vortex
coefficients amplified that rounding. All 22 target solves were unreached.

An [independent coordinate check](../../artifacts/isae/sa1-alpha-continuation-20261027/sampling-roundoff.json)
kept the saved circulation and original equations fixed. Using the exact
retained sample coordinates reduced the high-angle residual difference from
6.15e-10 to 5.66e-14, and the attached difference from 7.46e-11 to 6.80e-15.
This diagnoses a reconstruction precision issue in the diagnostic, not a
production or native-ASWING discrepancy.

The second revision uses retained sample coordinates and unchanged gates.
The 200-interval coordinates come from an existing Fourier diagnostic only
as geometry; its Fourier circulation is never used as a pointwise cold root.
The baseline mesh metadata and both attached/high-angle geometry records
must agree. The first attempt and its terminal process receipt are preserved.

## Completed outcome

The [revised protocol](../../artifacts/isae/sa1-alpha-continuation-r2-20261027/protocol.json)
and implementation were pinned before execution. Both saved-state replays
passed the unchanged 1e-10 gate; their largest normalized differences were
5.66e-14 and 6.80e-15. All **22 angle-sequence solves completed** in the
[recorded run](../../artifacts/isae/sa1-alpha-continuation-r2-20261027/summary.json).

| Intervals | Maximum normalized residual | Maximum CL difference from cold solve | Minimum sampled Jacobian singular value (1/m) | Newton corrections across eleven targets |
|---:|---:|---:|---:|---:|
| 200 | 5.00e-12 | 2.12e-12 | 0.437485 | 36 |
| 400 | 5.01e-12 | 2.13e-12 | 0.437489 | 36 |

Every correction accepted its full Newton step; no backtracking or failed
target occurred. All seven scalar outputs reproduce the cold results to at
most 2.13e-12 after normalizing dimensional forces by qS. At the two n400
states with full cold circulation saved, maximum Gamma/U difference is
3.78e-15. The n200 comparison remains a scalar comparison because its cold
pointwise circulation field was not saved. Native precision diagnostics
retain the same 19 matches; this is not an additional acceptance batch.

The [independent verification](../../artifacts/isae/sa1-alpha-continuation-r2-20261027/verification.json)
rebuilds both influence operators with scalar arithmetic, checks all 94
accepted iterate records and 72 line-search trials, enforces the endpoint
residual gate, and independently reconstructs coefficients and cold-state
differences. It also checks 88 Jacobian directional derivatives using a
separately expressed complex logarithmic law. Maximum relative derivative
difference is 5.09e-15. No extra root solve was needed for verification.

Thus **following the archived angle order does not change the current SA-1
solution within the tested discretizations**. This removes one proposed
explanation for the high-angle discrepancy. Nonsingular Jacobians at the
sampled states and agreement of two initialization routes do not prove
global uniqueness, dynamic stability or the archived executable's branch.

The constitutive source review and this numerical check identify no
production correction. Exact historical discretization and discrete load
recovery remain unresolved. Original inputs, equations and acceptance
tolerances remain intact, and SA-1 is still **19/154**.
