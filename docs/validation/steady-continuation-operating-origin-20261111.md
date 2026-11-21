# Preserve operating-target origins when resuming equilibrium

Observed 2026-11-11 UTC. Resumable equilibrium now retains the original
operating-target ramp when acceleration/net-load constraints are active.
Previously, a valid halfway checkpoint could fail its fresh residual check
because the new network treated the halfway load as the ramp's starting value.
The full-load equations and acceptance gates are unchanged.

## Reproduced failure

In the AE-3 38-mode diagnostic, the original roll-moment ramp starts at
**1.0332169790403705 N m** and ends at zero. At load fraction 0.5, the accepted
moment is **0.5166084895237298 N m**. The checkpoint omitted the original
starting moment, so a fresh network initialized the ramp from the latter value.
Its normalized residual rose from **1.2254e−13 to 5.2852e−4**.

The [independent audit](../../artifacts/isae/ae3-continuation-origin-20261111/cases/origin-audit/report.json)
shows that every non-operating row is unchanged. Restoring the original starting
value recovers the accepted residual, and the operating-row difference is
explained exactly by the changed interpolation target. This is a continuation
state defect, not an aerodynamic force-law correction.

## Change and compatibility

[steady_continuation.py](../../openswing/steady_continuation.py) now writes
`operating_initial_values` into the checksummed version-1 checkpoint. Restore
validates the finite values and their count, installs them before rebuilding
the physical residual, and restores the caller's previous values if validation
fails. Successful restore retains the saved ramp origin for subsequent stages.

Legacy-shaped unconstrained packets need no operating origins and remain
accepted when their complete context matches. Constrained packets that omit
the origins are rejected with a restart instruction. Exact kernel fingerprints
are still required; this change does not make old-kernel checkpoints portable.
The browser's existing whole-packet cloning preserves extra checkpoint fields,
but browser and WASM verification remain held and their bundles were not rebuilt.

## Validation

The [new regression suite](../../tests/test_constrained_steady_continuation.py)
passes **14 tests**. It checks exact split/uninterrupted parity with pointwise
and Fourier circulation, frozen and updated influences, and all six acceleration
constraints. It also checks missing, malformed and tampered origins, failure
cleanup, successful installation and unconstrained legacy-shaped packets.
Thirty existing checkpoint contract/JSON-boundary regressions and all three
existing serial parity checks also pass: **47 native regressions in total**.
The [adoption audit](../../artifacts/isae/ae3-continuation-origin-20261111/adoption.json)
records each passing test, source hashes and numerical evidence.

The full AE-3 38-mode control matches all **1,035 solution components exactly**
after a fresh-process restart. All six coefficients, roll acceleration and
apparent roll inertia also match exactly. The subsequent 76-mode chain completes
within the original per-child limits. See the
[mode study](isae-ae3-circulation-modes-20261111.md) and its linked assessment.

The initial larger existing-test batch and one isolated mechanical-test attempt
hit their 25-second wall caps. Both remain retained and supply no passing
evidence. Separately bounded library loading lets the unchanged mechanical and
midpoint parity checks finish in 3.23 and 3.59 supervised seconds. The two
JavaScript roundtrip tests and browser verification remain held. Numerical
children remain serial, with one BLAS thread and the unchanged
512 MiB /15 CPU /25 wall-second limits.

This source correction adds no primary ISAE passes. It enables a bounded solve
to resume the same physical path; it does not change the primary AE-3 inputs,
the 725 required comparisons or the archived 434-pass result.
