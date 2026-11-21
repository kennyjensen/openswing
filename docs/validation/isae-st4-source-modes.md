# Original ST-4 source-vacuum modal comparison

The later [paper-method integration](aswing-modal-integration.md) supersedes
the next-step proposal below. Fresh local shifted Arnoldi solves now cover
16/32/64/128 meshes and the browser without complete finite-spectrum
classification. This page retains the original dense-method comparison and
failure. Its failed refinement is not relabeled as passing; the new local
protocol records its own mesh checks and remaining reference differences.

Updated 2026-10-26. The unchanged ISAE `Weight7a/7a_b17.asw` now has a
preliminary comparison using the source structural dynamic equations. The
coarse run passes numerical checks, but the next mesh is rejected because
the descriptor reduction cannot resolve its dynamic rank at the declared
tolerance. **This is not a completed ASWING reference match.**

The adjacent archived driver requests 16 eigenvalues around −0.1 + 300i
and writes six positive-frequency roots to `vaccum.txt`. This comparison
retains the original model, uses a fixed vacuum frame, zero gravity and an
unloaded base, and declares uniform 16/32/64 interval meshes. The original
mesh and startup state of the vacuum toggle are not retained. Zero gravity
is a declared comparison setting, not a recovered historical setting.

The nominal 16-interval mesh has 17 actual intervals after inserting the
point-mass attachment. It produces 68 finite eigenvalues and returns the
requested 16 mode vectors. All six lowest positive frequencies occur in that
selection. The dense solver now exposes its already computed complete finite
spectrum, including deflated zero roots, so the shifted selection cannot hide
lower modes. Local Arnoldi searches do not claim a complete spectrum.

| Positive root, original order | Archived ASWING, rad/s | OpenSwing, rad/s | Difference |
|---|---:|---:|---:|
| 1 | 38.924987 | 38.944381 | +0.0498% |
| 2 | 120.74387 | 120.972221 | +0.1891% |
| 3 | 198.21227 | 199.097756 | +0.4467% |
| 4 | 379.27684 | 380.305112 | +0.2711% |
| 5 | 546.71484 | 554.975590 | +1.5110% |
| 6 | 978.17039 | 992.045412 | +1.4185% |

These are ordinal frequency comparisons; archived mode shapes and proof of
the stored list's completeness are absent. None matches printed precision.
Tiny real components are retained separately as numerical residuals, without
fitting damping or interpreting their sign as an established instability.

The native coarse solve takes 7.11 s on this host. All 173 recorded checks
pass, including source pins, complete-spectrum conjugacy and independent
left/right checks against the full saved matrices. The base residual is
5.69e-17 and the largest independent pencil backward error is 1.32e-16.
The saved base also has exactly zero gravity.

The nominal 32-interval run stops with `Dynamic derivative rank is ambiguous
at this tolerance`. Its failure and all source checks are retained. No
tolerance was loosened, no root was silently dropped and no replacement
method was used. The 64-interval run remains pending because the required
32-to-64 convergence comparison cannot yet be made. The predeclared 0.1%
frequency refinement gate is therefore **not assessed**, not passed. The next
task is to resolve descriptor scaling/rank classification while preserving
weak inertia and checking all six roots.

The [subsequent rank diagnosis](isae-st4-rank-diagnostic.md) identifies genuine
weak inertia in a constrained rigid direction. Two attempted reductions
passed the ST-4 saved-matrix checks but failed independent lost-mode tests,
including a coordinate-rotated oscillator. They were rejected and the
preceding kernel restored. The finer-mesh reference result remains unavailable.

Seven new independent spectrum-diagnostic tests and 21 existing descriptor
regressions pass. The browser test runner now supports a selected mode subset
and larger matrices; syntax and five norm checks pass. This ST-4 checkpoint
has **no new browser solve, saved browser project or packaged release**. The
earlier verified source-vacuum/still-air browser examples retain their own
scope and evidence.

The [machine report](isae-st4-source-modes.json) and
[evidence archive](isae-st4-source-modes-20261026-evidence.zip) preserve the
successful coarse run, failed refinement, original reference files and
executed source hashes. The [comparison runner](../../scripts/verify-isae-st4-source-modes.py)
and [unchanged example](../../examples/isae-st4-7a-b17.asw) are available for
reproduction. Experimental agreement is not required for this work.
