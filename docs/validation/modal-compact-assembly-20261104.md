# Compact modal refinement matrix assembly

Modal Ritz refinement now builds its bordered Newton matrix directly in CSC
storage. It retains every equation and coordinate, the same sparse factorization
ordering, and the existing convergence and adjoint acceptance limits. Only
intermediate sparse-matrix copies are removed.

For the saved 4,293-coordinate ST-4 case, all **1,429,692 stored entries and both
index arrays match the previous assembly bit-for-bit**. The integrated production
builder also reproduces those recorded array hashes.

| Assembly measurement | Previous assembly | Compact assembly |
|---|---:|---:|
| Peak process resident memory | 167.2 MiB | 133.9 MiB |
| CPU time within assembly | 0.184 s | 0.046 s |
| Elapsed time within assembly | 0.237 s | 0.069 s |

These are individual measurements in separate single-thread processes, with
the same matrices and both implementations imported before timing. Peak memory
falls 19.95%; assembly CPU time falls 75.25%. This does **not** establish an
end-to-end solve speedup or remove the cost of constructing the physical A/M
matrices. Initial runs with unequal import scope remain recorded and are not
used for this timing comparison.

The seven added test cases check the derivative of the full nonlinear eigenpair
equations at every normalization pivot, real and complex vector directions,
empty sparse columns, algebraic rows, zero mass action and unchanged input
matrices. Existing known-root, adjoint, descriptor and weak-inertia checks also
pass: **44 selected tests** across a partial bounded run (37 passes) and the
seven remaining tests run separately. The timeout and an initial test-path
selection error are retained; this is not a completed single full-suite run.

Fresh self-weight-column checks cover the static threshold and two dynamic
cases on either side of it. All **six physical matrices** and both **complete
modal result objects** are exactly unchanged from the preceding verified study.
Each modal case exercises two Ritz corrections and checks four modes. Native
verification takes 27.90 seconds across the three serial cases.

The built offline browser passes **430/430 checks** for both dynamic cases,
including full physical outputs, left/right vectors, desktop/mobile views and
saved-project reopening. No external or post-disconnection network requests
occur. Browser solves take 11.40 and 10.29 seconds in this run; these timings
are observations, not a controlled full-solve performance comparison.

The native/browser equations, source inputs and validation tolerances remain
unchanged. Native ASWING comparison scores and the remaining ST-4 slow-pole
mesh/reference discrepancy are unchanged. This implementation improvement does
not establish whole-family validation or project completion.

[Portable evidence](modal-compact-assembly-20261104.json) includes the measured
assembly comparison, integrated physical checks, regression record and browser
audit. Full execution artifacts are in
`artifacts/isae/modal-compact-assembly-20261104/`.
