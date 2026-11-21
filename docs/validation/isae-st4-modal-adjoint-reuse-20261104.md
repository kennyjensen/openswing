# ST-4 modal adjoint reuse

2026-11-04. Repeated sparse factorizations dominated the profiled modal stage.
For a real full descriptor pencil, the solver now reuses the conjugate of a
previously verified simple left eigenvector when the current eigenvalue and
right vector pass the original equations and mass-pairing checks. The measured
160-interval ST-4 case uses **12 sparse factorizations instead of 17**.

| Stage | Baseline | With checked reuse |
|---|---:|---:|
| Full public API case | 140.50 s | 111.45 s |
| Eigensystem | 38.44 s | 29.65 s |
| Sparse factorizations | 17 | 12 |
| Inverse-iteration adjoints / reused conjugates | 16 / 0 | 11 / 5 |

These are single-run observations. Unchanged import and assembly stages also
ran faster in the second run, so the **20.68%** total reduction cannot all
be attributed to this change. The deterministic improvement is five fewer LU
factorizations. A separate saved-pencil baseline profile spent 44.18 of 46.76 s
inside 17 sparse factorizations. The final run used 293.2 MiB peak RSS.

The input remains the literal Weight7a `7a_b17.asw`, speed 120.5, density
1.0771417304, gravity 9.81, zero incidence/sideslip, Mach zero, active lag and
stall, fixed perturbation frame, cosine mesh with mandatory attachment stations,
and 16 full-pencil modes near 0+300i. No physical term or mode is removed.

Conjugation is an algebraic symmetry of real matrices; this is not a claim
about unpublished ASWING source. The first member retains the existing inverse
iteration and normalization implementing the documented Eqs. 150–152. Reuse
requires opposite imaginary signs, a candidate eigenvalue difference below
`1e-12 * max(1, abs(lambda))`, original right/left backward errors at most
1e-10, and mass-pairing error at most 1e-10. The actual eigenvalue is never
rounded or replaced. Rejected candidates retain inverse iteration; complex
pencils and selected repeated poles retain their prior recovery paths.

Verification:

- Original A/M matrices, all 16 eigenvalues, right vectors and complete physical
  modal outputs are **exactly identical**. The saved preceding-refinement A/M
  matrices are also identical. Relative left-vector change is at most
  6.75e-12.
- All **32 independent original-equation vector checks** pass, with maximum
  normwise backward error 1.18e-15 against 1e-8.
  Maximum selected mass-pairing error is 3.67e-11 against 1e-8.
- **33 regression tests pass**: 27 modal/adjoint tests and six complete
  structured-versus-ungrouped analyses. They cover an analytic constrained
  transfer response, rejected reuse, complex pencils, repeated eigenspaces,
  weak/singular inertia, time scaling, lag, Fourier circulation and matrix export.
- The offline Python/WASM browser case uses 16 cosine intervals and eight
  circulation Fourier modes at speed 120. It reuses 4 adjoints,
  solves in 21.753 s, agrees with retained Python poles to
  9.67e-13 scaled error, and saves/reopens the result exactly.
  Graphics are disabled in this solver/workbench check. This is not a browser
  timing comparison at 160 intervals or an execution of native ASWING.

Jobs remained serial with one BLAS thread; native numerical jobs used a 512 MiB
address-space cap. Accuracy gates and registered native-family scores are unchanged.
The [critical-region study](isae-st4-critical-refinement-20261104.md) still has
43.10% lowest-frequency error at speed 120.5 and the opposite slow-root sign
from ASWING at 139.5. Its final independent mesh checks remain 52/52 and
production refinement 24/26. ST-4 and the full project remain incomplete.

[Portable evidence](isae-st4-modal-adjoint-reuse-20261104.json) is included in the
source distribution. Raw evidence is retained in the worktree under
`artifacts/isae/st4-modal-output-20261104/` (assessment, timing receipts, profile,
test logs and browser replay).
