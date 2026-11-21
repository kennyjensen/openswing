# Sparse modal adjoint recovery

**Numerical verification passed; ISAE experimental validation remains incomplete.**

The dense modal workflow previously solved the complete generalized eigenproblem
a second time solely to recover left eigenvectors, including constraint reactions.
For simple poles of sparse pencils, it now recovers those vectors with sparse
bordered linear solves. Real pencils reuse conjugate vectors after checking the
original adjoint equations. Repeated or weakly paired poles and rejected sparse
solves retain the original generalized-Schur/null-space fallback. Certified zero
integrators retain their original kernel recovery.

Only `eigensystem` and the new `_sparse_adjoint` helper change in the numerical
kernel. All other 96 modules, physical A/M assembly, finite-subspace classification,
right-vector computation and final eigenpair acceptance criteria are unchanged.
This is an exact numerical recovery method, not a fitted physical approximation
or a claim about undocumented ASWING implementation. The
[source and evidence audit](modal-adjoint-transition.json) records that boundary.

## Verification

| Check | Result |
|---|---|
| All 26 corrected Pazy modal matrices, 15–120 intervals | 416 matched eigenvalues identical in the same-process replay |
| Left/right vectors and modal residues | Maximum relative residue-error bound 1.252×10⁻¹⁰ |
| Native selected regressions | 295 passed: modal/descriptor, reactions, analytic transfers, reduced and initial response, control, repeated poles and fallback |
| WebAssembly | Three original-matrix comparisons and repeated-pole fallback passed |
| Fresh offline browser solves | Three Pazy cases rebuilt and linearized; frequencies, shapes, source hashes and exports passed |
| Separate saved-result display | Vulkan rendering and desktop/mobile layouts checked without recomputing the solution |

The [native replay](modal-adjoint-native.json) retains full before/after vectors,
matrix hashes and CPU/wall timings. [WASM results](modal-adjoint-wasm.json),
[fresh browser results](modal-adjoint-browser.json) and
[saved-result display results](modal-adjoint-display.json) are separate records.
The first browser run's SwiftShader screenshots had a blank 3D viewport despite
passing numerical assertions. They are retained as a visual failure; the separate
Vulkan check verifies a healthy context and visible geometry. Its initial launch
with an invalid driver-file path was stopped and preserved as a setup error.

The native eigensolver CPU speedup ranged from 1.45× to 2.38×, median 1.97×.
On the two larger WASM examples, this stage took about 35 seconds instead of
43–44 seconds. These are host observations with concurrent verification jobs,
not portable benchmarks. The complete fresh browser solves still took about
34 seconds at 15 intervals and 166–191 seconds at 60 intervals. Base solving,
linearization and finite-subspace reduction remain substantial work; an overall
browser speedup is not established by these tests.

## Scope and reproduction

The 26 native comparisons reuse the saved corrected Pazy A/M matrices. Three
browser checks are fresh physical solves. The selected regression suite passed;
the complete repository suite was not rerun for this increment. Historical ISAE
studies retain their original solver hashes, and their archives are unchanged.
The [coverage ledger](isae-coverage.md) remains 16 partial families, 25 pending,
and zero fully validated families. Swept-force mesh behavior, literal input
conflicts, Pazy experimental discrepancies, flutter and time-response validation
remain unresolved.

`modal-adjoint-evidence.zip` contains both source versions, the original matrices,
full vector comparisons, exact tests, runtime results and original failed/setup
attempts. Its README gives replay commands. Re-extracting it and running
`verify-modal-adjoint-transition.py` reproduces the transition audit byte for byte.
