# Local strip differentiation for Fourier steady matrices

Follow-up, 2026-11-12: [76-mode controls](isae-ae3-mode-mesh-20261112.md)
also match the complete original matrices and Newton corrections exactly at
two tested states. Its full cold replay differs by up to 7.99e-14 in normalized
coordinates; its predeclared zero gate fails, while the existing 2e-10 parity
gate passes. The earlier exact 38-mode result remains specific to that control.

Observed 2026-11-11 UTC. The steady Newton assembly now differentiates local
strip tangency equations before applying their Fourier projection. On the saved
AE-3 82-interval/38-mode state, geometry perturbation groups fall from **498 to
18**. One measured matrix build takes **0.167 CPU seconds versus 3.449 seconds**
with the original implementation: about **20.6 times faster for that build**.
This is not an end-to-end browser speed measurement.

The complete original and optimized matrices, their Newton corrections, and
the physical residual match exactly at both the accepted AE-3 state and an
independently perturbed state. A fresh four-step cold solve then reproduces all
**1,035 solution components**, six coefficients and roll acceleration exactly.
It completes in **1.408 CPU / 1.579 supervised wall seconds**, excluding the
separately bounded library preload. Its Cl remains **.000497363046637764**.

## Equations and implementation

Drela's [steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
§5.6, Eq. 201, projects local flow-tangency defects onto material-coordinate sine
modes. That projection makes each mode row depend on all strips, even though
the section geometry derivatives are local when induced fields are held fixed
for the existing approximate Newton matrix.

Previously, matrix grouping treated those projected rows as globally coupled,
so each geometry coordinate required a separate residual evaluation. The
[structured assembler](../../openswing/structured_static.py) now groups the
unprojected strip rows. For each recovered column it restores every untouched
strip to its base value and applies the original projection **before** taking
the finite difference. This preserves the original cancellation and roundoff;
it does not substitute a differently rounded projection of differences.

The [aerodynamic evaluator](../../openswing/aero.py) exposes the already-computed
local residual only during this internal capture. Pointwise circulation retains
its existing assembly. Mixed pointwise/Fourier beams, original matrix factors,
frame constraints, fresh physical residuals, convergence tolerances, initial
rank checks, full-matrix fallback and continuation acceptance retain their
existing definitions. Neither a physical parameter nor the chosen number of
circulation modes changes.

## Verification and retained attempts

The [adoption audit](../../artifacts/isae/ae3-fourier-local-tangent-20261111/adoption.json)
records two changed production files, before/after kernel hashes, **16 exact
matrix/control checks**, **17 passing native regression cases**, and the full
cold-solution comparison. The regressions include frozen/updated influences,
zero/partial load, direct/fallback mechanics, six acceleration constraints,
strong circulation, mixed lifting/body/engine models, the previous Fourier
matrix test, and four split/uninterrupted continuation cases.

The [new regression file](../../tests/test_structured_fourier_flow.py) requires
exact equality for mechanical, aerodynamic and circulation matrix rows.
Aggregate frame rows use the **existing** `test_structured_initial_frames`
roundoff gate, absolute 2e-8 / relative 1e-9: grouped assembly differences local
nodal wrenches before summing, while the ungrouped control differences their
global sum. An initially stricter new assertion failed only in those rows by
4.05e-11; that attempt and its original source snapshot are preserved. Existing
regression tolerances were not changed.

Two pytest-launch attempts reached their wall caps before yielding results.
They supply no passing evidence. The successful serial workers invoke the same
regression functions directly with every selected parameter; no pytest
collection pass is claimed. Library/test-module imports do no solver work and
are separately bounded. Every numerical worker retains one BLAS thread,
512 MiB address space, 15 CPU seconds and 25 wall seconds.

The earlier 164-interval attempt with original assembly reached its first load
step and then hit the wall cap. Its initial matrix alone used 990 geometry
perturbation groups (992 total tangent progress steps). The [fixed-mode refinement plan](../../artifacts/isae/ae3-fixed-mode-mesh-local-20261111/plan.json)
restarts that study under the optimized, verified assembly; it does not reuse an
unaccepted partial state or increase the resource limits.

This optimization adds **zero primary ISAE passes**. AE-3 remains **434/725**;
the sibling-control/free-roll diagnostic is still not an authenticated archived
input. Browser/WASM checks remain held and bundles have not been rebuilt.
