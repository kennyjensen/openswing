# Guarded real64 certificate: additive design review

The proposed replacement has a valid conservative derivation for the **true reciprocal 2-norm condition number of the original floating dense-normalized matrix**, under the arithmetic and storage assumptions below. This is a source and mathematical review, not a numerical test or an activation approval. The original audit remains unchanged. The candidate implementation and resolution of its source-review findings are pinned separately in `design-review.json`.

The threshold remains `1e-10`, the column-norm floor remains the same binary64 `1e-30`, and an inconclusive certificate returns to the original dense SVD. A true-condition certificate does not prove bit-identical decisions to the rounded LAPACK SVD ratio at its threshold. This distinction must remain explicit.

## Target and eligibility

Let A contain the exact values of the caller's finite real binary64 sparse matrix. Stored entries must describe a canonical CSR/CSC matrix: valid pointer/index bounds and strictly increasing indices within each compressed segment, with no duplicates. Cached `has_canonical_format` alone does not prove this when the backing arrays can be changed. Reject unsupported storage without mutating the caller. A private CSC conversion must preserve those values exactly; construct B by direct per-entry division, not multiplication by a separately rounded reciprocal.

The original dense path computes C by dividing the dense representation of A by `max(norm(A[:,j]), F)`, where F is the unchanged floor. Its square/sum/square-root order can differ from the sparse norm order. The proof below allows that difference. There is no pruning, sampling of inverse columns, change of physical equations, or change of the dense fallback.

Assume binary64 round-to-nearest, correctly rounded elementary scalar operations and square root, gradual underflow, and classical sparse product accumulation, possibly using FMA, with no more operations than the stated conservative counts. Unsupported fast-math/flush-to-zero behavior is outside this proof. Let u=2^-53, and let gamma(k) be an upward enclosure of k*u/(1-k*u), with every denominator positive and finite. Dimension/count conversions must be exact. All finite/range checks are eligibility restrictions; they do not relax the original rank criterion.

Every nonzero entry of A, B, the returned inverse batches Y, and the computed residual batches is required to have magnitude at least sqrt(tiny), where tiny is the smallest positive normal binary64 value. Overflow, nonfinite values, or unsafe ranges make the certificate inconclusive. Each inverse result must be a real float64 array with exactly the RHS shape. Factor-construction or factor-solve RuntimeError is inconclusive. MemoryError, interruption, progress-callback exceptions, and unrelated unexpected exceptions propagate.

## Outward norm bounds

For m stored binary64 values whose nonzero squares are normal, form the usual computed positive square sum s. A conservative error count is `2*m+2`. With g_m=gamma(2*m+2)<1, an upper bound for the exact square sum is

    S_U = up(s / down(1 - g_m)).

This includes rounding of squares and any ordinary positive reduction order with at most m-1 additions. Overflow/nonfinite sums decline. The Frobenius norm bound is `sqrt_up(S_U)`. Sum the per-batch squared bounds upward before the final square root; do not merely sum normally rounded norms. Explicit zeros contribute exactly zero. Canonical storage makes the sum of stored squares equal the matrix's Frobenius square sum.

Every positive add, multiply, divide and square root that contributes to an upper bound must round upward. The denominator of an upper quotient must be bounded downward. The final certificate numerator and quotient round downward, and its denominator rounds upward. Applying `nextafter` only to the final result would be insufficient.

## Sparse-to-dense normalization transfer

Set g=gamma(2*n+3), where n is the matrix order, and require g<1/4. The generous count covers n squares, a positive sum, square root and its rounding. If t is the true Euclidean norm of a nonzero column, both computed column norms lie in `[(1-g)*t, (1+g)*t]`, provided the reductions are finite. Thus their ratio is between 1/q and q, with

    q = (1+g)/(1-g).

Applying the same positive floor F to both norms preserves these ratio bounds, even when only one norm crosses the floor. This follows directly by considering whether each argument is below or above F; no identical floor branch is assumed.

Each path then performs one correctly rounded direct division. Let B_ij and C_ij be the resulting entries. For nonzero A_ij,

    1/r <= C_ij / B_ij <= r,
    r = q * (1+u)/(1-u),
    rho = r - 1,
    |C_ij - B_ij| <= rho * |B_ij|.

The ratio is positive even for negative entries. Since `1-1/r <= r-1`, the same rho bounds either direction. Compute q, r and rho upward. For zero entries the difference is zero. Consequently

    ||C-B||F <= rho * ||B||F,
    ||C||F <= (1+rho) * ||B||F.

The earlier reciprocal-multiplication implementation needed an additional division-rounding factor and was not covered by this direct-division formula.

The candidate's norm ceiling supplies the missing finite-range proof. Requiring each sparse column norm to be no larger than `down(sqrt(MAX))/2`, together with g<1/4, implies its true square sum is at most 4*MAX/9. Any supported positive dense accumulation is then bounded by 5*MAX/9. There is enough margin to rule out a different dense reduction order overflowing; the bound can be applied to every positive partial sum. The half multiplication is exact in this range.

The hypothetical dense direct division is normal as well. Before its final rounding, its magnitude lies between `|B_ij|/[q*(1+u)]` and `|B_ij|*q/(1-u)`. Here q<5/3, B's retained nonzeros are at least sqrt(tiny), and normalized B entries have magnitude at most `(1+u)/(1-g)`. Therefore the lower endpoint is far above tiny and the upper endpoint is below 3. This also justifies applying the relative division model to C without allocating C. A broader eligibility range would require a new proof or explicit range enclosures.

## Product, underflow and inverse-residual enclosure

Treat every returned binary64 Y batch as arbitrary data. No correctness claim about SuperLU is needed beyond its output shape/type and the verified residual. Let R_hat be the saved result of `B @ Y - I`, across all inverse columns. With k=2*n+2, the standard componentwise product/subtraction model gives the global Frobenius enclosure

    ||B*Y-I-R_hat||F
      <= gamma(k) * (||B||F * ||Y||F + sqrt(n)) + nu.

The product inequality `||abs(B)*abs(Y)||F <= ||B||F*||Y||F` avoids a second absolute matrix product. The operation count permits ordinary accumulation or FMA and includes residual subtraction. Applying this global bound once is valid after accumulating the complete Y and R_hat Frobenius bounds across every batch. It must not omit columns or confuse per-batch and full-identity dimensions. The classical componentwise product bound is given in [Higham's primary presentation](https://web.cs.ucdavis.edu/~bai/ECS231/References/Higham18a.pdf); the additional scalar/range enclosures here are part of this review.

For gradual underflow, a conservative additive term is

    nu = n * k * eta / (1-k*u).

Each of the n^2 residual entries has at most k rounding operations, and the Frobenius combination contributes n rather than n^2. The candidate deliberately uses eta=tiny, the smallest NORMAL, instead of the smaller subnormal quantum. This is a valid, larger absolute allowance and keeps its own outward calculation in the normal range. It is not a claim to support flush-to-zero arithmetic. Compute this quotient upward with its denominator downward; decline any invalid or nonfinite bound.

With bU, yU and rU denoting the outward Frobenius bounds for B, Y and R_hat, define, all upward,

    pU = bU*yU,
    EU = rU + gamma(k)*(pU + sqrt_up(n)) + nu + rho*pU,
    cU = (1+rho)*bU.

Then `EU >= ||I-C*Y||F` and `cU >= ||C||F`. Require EU<1. The inverse-residual/Neumann argument implies

    rcond2(C) >= (1-EU)/(cU*yU).

It is the verified residual, not an a priori quality claim about Y, that proves nonsingularity; see [Rump's Theorem 10.2](https://www.tuhh.de/ti3/rump/intlab/ActaNumerica2010.pdf). A safe returned value is `max(0, down(down(1-EU) / up(cU*yU)))`, with all bounds finite and denominators positive. A value above the unchanged threshold certifies the mathematical criterion. Otherwise the original dense SVD decides.

## Additive diagnostic evidence and limits

After the original source-only audit, a different agent executed four predeclared 2x2 baseline-helper diagnostics. Its pinned report now supplies an **observed unsupported-complex false acceptance**: the helper accepted approximately 1.5983003449290672e-6, whereas the proper dense column-normalized oracle was 5.109175874811749e-12 and the analytic value was 5.109089028063325e-12, both below 1e-10. Two ComplexWarnings were retained. A float32 control raised a safe-casting TypeError instead of falling back. A noncanonical duplicate CSC control was mutated from six stored entries to three. The normal real64 control accepted a conservative bound below its dense oracle. These observations support the eligibility/fallback guards; they do not demonstrate a false acceptance for a real64 aircraft Jacobian.

The diagnostic's four rank calls, four oracle SVDs, four attempted inverse solves and three completed residual products belong to that separate recorded execution. This review performs no production import, matrix product, solve, factorization, SVD, test or physical call. Its original findings and all prior physical validation failures remain unchanged. Candidate tests can expose implementation mistakes but cannot replace the arithmetic proof or extend its stated assumptions. Performance, browser behavior and activation of any new final-rank path remain separate work.
