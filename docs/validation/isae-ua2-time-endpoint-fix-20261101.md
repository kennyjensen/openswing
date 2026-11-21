# UA-2: checkpoint endpoint rounding repair

Updated 2026-11-01. **The reproduced continuation failure is fixed.** Four new
regression tests and 14 existing forcing checks pass. The actual UA-2 boundary
and following 128-step segment also pass, with no rejected steps. The complete
eight-cycle periodic comparison still requires a fresh run; no periodic pass
is added by this repair.

The original 640-step/cycle run stopped on segment 13. Its preceding segment
started at 0.016534698176788383 and targeted the forcing knot
0.08267349088394192. Computing `start + (target - start)` rounded the endpoint
to 0.08267349088394191. The forcing event filter excluded the intended knot,
so the saved state ended one ulp early. On continuation, the integrator tried
to reach that knot in 1.3877787807814457e-17 seconds. The backward-difference
system became numerically unusable, producing a Newton line-search failure
at residual 0.687.

The event filter now includes terminal knots within the same rounding margin
used by the existing time integrators. Their existing event snap then lands
on the exact table time. Aerodynamic equations, BDF coefficients, tolerances,
startup grids and physical initial states are unchanged. Only forcing.py
changes among the 136 production modules; the other 135 retain their hashes.
The repair prevents new rounded-endpoint checkpoints. The old failed state is
preserved; the preceding segment is recomputed rather than retiming that state.

| Verification | Result |
|---|---|
| New endpoint/checkpoint regression tests | 4/4 pass: smooth forcing, jump, cutoff and accuracy-controlled integration. |
| Existing forcing regression checks | 14/14 pass. |
| Actual UA-2 boundary replay | 128 accepted steps; zero rejected; exact endpoint 0.08267349088394192. |
| Formerly failing continuation | 128 accepted steps; zero rejected; reaches 0.14881228359109547. |
| Replay physical differences | Force <9.74e-16; circulation rate <4.61e-14, normalized by max(1, absolute saved value). |
| Minimum step in the repaired continuation | 0.0005167093180246107 seconds. |
| Maximum nonlinear residual in the two replays | 9.40e-11, below the unchanged 1e-10 limit. |

The new smooth-forcing regression failed on the original code at the exact
one-ulp endpoint mismatch. With the fix, segmented and uninterrupted trajectories
have identical times and BDF orders and matching physical states, including
proper left-side ownership at jumps and the table cutoff. Accuracy-controlled
integration also lands on the exact knot.

The [original periodic attempt](../../artifacts/isae/ua2-incidence-periodic-20261101), failure
log and raw states remain available. Its 26-segment coarse history completed,
but the fine history stopped, so it cannot establish periodic acceptance.
The [fresh 320/640 comparison](isae-ua2-incidence-periodic-20261101.md) now passes
all 17 accuracy gates, with 7,922 unique snapshots audited. Its later runtime
timeout is retained and recovered in smaller jobs on the same physical grid.
The [packaged WASM and browser replay](isae-ua2-time-endpoint-wasm-20261101.md)
passes the endpoint check and one actual continuation step. Static-build and
download identity checks and desktop/mobile startup also pass. Full periodic
browser validation remains unfinished.

Evidence: [machine summary](isae-ua2-time-endpoint-fix-20261101.json),
[raw replay histories and test receipts](../../artifacts/isae/ua2-time-endpoint-fix-20261101),
[original failure](../../artifacts/isae/ua2-incidence-periodic-20261101/n640-part13.log),
[regression tests](../../tests/test_time_endpoint_roundoff.py), and
[direct replay](../../scripts/verify-isae-ua2-time-endpoint-fix.py).
