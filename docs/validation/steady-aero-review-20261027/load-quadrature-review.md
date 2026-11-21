# Steady aerodynamic load quadrature review — 2026-10-27

The published equations do **not uniquely establish the complete aerodynamic-to-structural load transfer** used by the historical executable. They establish the structural endpoint average and the aerodynamic Glauert-midpoint sampling separately. This review therefore identifies a notation and recovery ambiguity, not a proved replacement quadrature or a demonstrated production defect.

The structural rule is in **§2.1, Eqs. 55–56**, not §5.1. The preceding definition makes subscript `a` the arithmetic average between adjacent structural stations. Those equations use `f_a Δs` and `m_a Δs`. Section 4.2 then explicitly redefines `a` **“In this section”** as the Glauert-angle midpoint. Equations 150–154 sample Fourier circulation there, or use interval-constant pointwise circulation. Equation 67 evaluates the lift velocity at the bound-vortex location; Eq. 155 defines that location using the Glauert midpoint. The inspected text gives no explicit recovery of endpoint aerodynamic force densities or unique nodal circulation traces at interval jumps. Section 5.1 sums the structural equations to obtain the total ground reaction; that conservation statement does not resolve the missing recovery rule.

These statements are pinned and line-referenced in [the JSON evidence](load-quadrature-review.json). The unsteady extension, Eqs. 263–267, also derives the global moment using the arithmetic spatial midpoint. An aerodynamic load applied elsewhere must retain its lever-arm correction during structural transfer. Conservation can verify that transfer while leaving the force quadrature itself unproved.

## Independent retained-field calculation

Only saved SA1 results were read: the attached-flow row at α = 1.9971°, with existing 200/400 intervals and 40 Fourier modes, plus the 400-interval pointwise result. No solve, residual, matrix or production-module evaluation was performed.

For a cosine mesh with `N` intervals, semispan `R`, and `Γ = Σ A_k sin(kθ)` with `K < N`, discrete sine orthogonality gives:

- Midpoint integral: `M = R N sin(π/(2N)) A_1`.
- Endpoint trapezoid: `T = cos(π/(2N)) M`.
- Continuous sine integral: `C = π R A_1 / 2`.

These are independent identities; no archived output enters their derivation. The retained Fourier fields satisfy the first two identities within `1.1e-14` in circulation-integral units. Their saved velocity component parallel to freestream equals the freestream speed within `7.11e-15`, so their circulatory lift is independently `ρ V M`. Profile-force projection contributes approximately `−9.4251e-5` to total CL, as allowed by Eq. 185.

| Existing mesh | Total CL discrepancy | Change in circulatory CL from endpoint trapezoids | Remaining discrepancy if only that term changed |
|---|---:|---:|---:|
| 200 intervals, K=40 | +8.40332e-5 | −4.47138e-6 | +7.95618e-5 |
| 400 intervals, K=40 | +8.40336e-5 | −1.11785e-6 | +8.29157e-5 |

The archived CL half-printing-unit tolerance is `5e-7`. These diagnostic substitutions remain outside it. The table rejects only the narrow hypothesis that replacing the retained circulation integral with endpoint trapezoids resolves the discrepancy. It is **not** a recomputed prediction: nodal induced velocity, drag, moments and circulation were not reevaluated.

## Tests that would distinguish the interpretations

1. Prescribe a sine circulation field on two cosine meshes, with uniform velocity and zero drag/moment. Use the closed-form integral for the explicitly declared transfer policy as the oracle; do not reuse production aggregation.
2. Use unequal endpoint circulation and velocity/frame fields. Averaging the complete Kutta–Joukowsky force differs from multiplying separately averaged factors: `mean(ΓV) − mean(Γ) mean(V) = ΔΓ ΔV / 4`. A Gamma-only trapezoid is not a general endpoint-force average.
3. Give an interval force `P` and couple `C` at a noncentral aerodynamic position `rθ`. With structural midpoint `r̄`, transfer `C̄ = C + (rθ − r̄) × P`; independently check force and moment about two origins. This tests conservation, not quadrature selection.
4. For adjacent intervals with different constant circulation, require an explicit nodal or one-sided trace policy before asserting endpoint-trapezoidal loading.

No production change is justified by this review alone. An explicit primary description or retained v5.96 implementation of aerodynamic `f_a` construction would resolve the remaining transfer question. Neither internal agreement nor choosing a discretization by archived match counts establishes that historical behavior.
