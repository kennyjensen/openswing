# ASWING modal algorithm and ARPACK source reference

This source-review checkpoint is followed by the
[production integration and fresh ST-4 comparisons](aswing-modal-integration.md).
The implementation gaps described below refer to the preceding kernel, whose
saved evidence is retained unchanged.

Updated 2026-10-26. The modal implementation target is the algorithm in
Drela's papers. The proposed custom mechanical reduction has **not** been
promoted. A complete finite-spectrum census remains a separate OpenSwing
diagnostic; it is not a prerequisite in the published ASWING modal algorithm.

## Published method

The [unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf),
§13.1, defines the coupled residual Jacobians as `A = r_x` and `M = -r_xdot`.
Section 13.3.1, Eqs. 147–149, applies Arnoldi to
`H = (A - mu M)^(-1) M`. The largest transformed eigenvalues `nu` give the
physical eigenvalues nearest the requested shift through `lambda = mu + 1/nu`.
One LU factorization of the shifted matrix is reused for operator applications.
This retains the algebraic equations and does not require an inverse of M.

The pinned [ARPACK-NG source](https://github.com/opencollab/arpack-ng) is in
[`reference/third_party/arpack`](../../reference/third_party/arpack). Its revision, archive checksum
and individual file hashes are in the [manifest](../../reference/third_party/arpack-source.json).
The upstream license is preserved. This maintained reference version is not
claimed to be the exact historical version linked by ASWING. It has not been
built or newly linked into the application; the current solver uses SciPy's
ARPACK interface.

For a general nonsymmetric descriptor M, the appropriate ARPACK interface is
complex nonsymmetric **standard mode 1**, `BMAT='I'`, `WHICH='LM'`, with the
operator callback `solve(A - mu M, M x)`. This follows from
[`znaupd.f`](../../reference/third_party/arpack/SRC/znaupd.f) and the standard example in
[`ex-complex.doc`](../../reference/third_party/arpack/DOCUMENTS/ex-complex.doc).
The identity is the Arnoldi inner-product metric, not a replacement for physical M.
Generalized mode 3 requires a Hermitian positive-semidefinite M and therefore
does not cover our arbitrary nonsymmetric descriptor. In standard mode,
[`zneupd.f`](../../reference/third_party/arpack/SRC/zneupd.f) returns nu; apply the reciprocal
transformation once, outside ARPACK.

The paper specifies left-vector inverse iteration in Eqs. 150–152, again
reusing LU factors. Its printed Eq. 151 has a complex normalization ambiguity:
for `s = w'^H M v`, division by `conj(s)` enforces the stated Eq. 152 invariant
`w^H M v = 1`. This is an algebraic qualification of the printed formula,
not evidence about ASWING's source implementation. Exact historical balancing,
Arnoldi tolerance, subspace size and starting-vector choices remain unspecified.

## Checks completed

The unchanged production `full_shift_invert` path was run on the saved original
ST-4 nominal 16- and 32-interval matrices with the archived request of 16 roots
near `-0.1 + 300i`. All 22 checks per matrix pass: selected count, finite roots,
full-state vectors, original left/right residuals, mass pairing and agreement
with independently retained local root sets. The saved-matrix solve and checks
take 0.129 s and 0.623 s on this host. These timings exclude physical matrix
assembly, imports and browser startup.

This establishes that the existing local Arnoldi path handles the saved finer
pencil. It does not establish a complete spectrum, a fresh aircraft solve,
32-to-64 mesh convergence, browser behavior or an archived-ASWING pass. The
old dense-method rank failure remains recorded as a failure of that method.

A standalone implementation of the paper's left-vector iteration passes all
12 prescribed analytic outcomes: six successful vectors, five expected explicit
failures and one normalization oracle. The maximum successful original left
backward error is 7.99e-17. Exact singular factorizations and unresolved pairings
fail explicitly. Repeated-root cross-mode duality remains unsupported. This
prototype has not been integrated or run on an aircraft pencil.

The [machine report](aswing-modal-method.json) and
[evidence archive](aswing-modal-method-20261026-evidence.zip) preserve inputs,
checks, source mappings and isolated experiments. No production numerical
module changed during this work; all 119 baseline module hashes are unchanged.

## Remaining implementation and validation

The existing direct path already implements the correct right-vector operator,
but still uses exact-integrator deflation, dense shifted LU/storage and a full
generalized-Schur calculation for left vectors. These are not all the paper's
stated implementation steps. Integrate and validate the documented full-pencil
algorithm and left iteration, with explicit treatment of singular or repeated
poles, before claiming that correspondence.

Then rerun the original ST-4 request on the declared 16/32/64 meshes and in the
browser. Report local root coverage honestly and retain the predeclared mesh
and reference criteria. Historical mesh and startup settings remain unresolved.
Neither experiment matching nor another custom rank reduction is required to
proceed with this paper-based local modal comparison.
