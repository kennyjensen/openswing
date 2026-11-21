# AE-3 refinement on both sides of the control breaks

Three nested local refinements have completed. **The two original global mesh-convergence failures remain unresolved, and AE-3 remains pending.** This sequence measures convergence in a fixed local region; it does not refine the rest of the wing or establish experimental agreement.

At the worst-pressure 20O-05 point, each of the four original cells immediately beside the two aileron boundaries is divided into 2, 4, then 8 equal material-length pieces. All 259 baseline nodes are retained, every level contains the preceding level exactly, and the other 254 intervals remain unchanged. The first level is the exact union of the earlier outboard-only and inboard-only node additions.

| Pieces per target cell | Actual elements | Native Cl control derivative | Adjacent change / absolute finer result |
|---|---:|---:|---:|
| 1, saved baseline | 258 | -0.000221145797928 | — |
| 2 | 262 | -0.000223275496772 | 0.953844% |
| 4 | 270 | -0.000224556204572 | 0.570328% |
| 8 | 286 | -0.000225311470174 | 0.335210% |

The local percentages use |D_finer−D_coarser|/max(|D_finer|,1e-30), without a new pass/fail threshold. The earlier global n128-to-n256 failures, 1.3579% and 4.5885% against the original 1% gate, remain unchanged. No finite-control solve was run on these three meshes; previous finite-control passes apply only to their tested meshes.

The full API step stays 2.5e-6 for state, input and output probes together. Model, conditions, fixed-acceleration response, standard basis, stability axes and source are unchanged. Exactly three zero-control equilibrium calls and three full derivative calls completed, with no baseline rerun. The maximum fresh physical residual is 0, and the maximum freshly recomputed full linear residual is 9.28146e-13; both satisfy the original 1e-8 limits. Dense rank and branch checks also pass. The p column remains descriptive.

Combining the two one-sided changes additively would give -0.000223543995789; the actual two-piece result differs by +2.68499e-07. This is a diagnostic interaction of mesh changes, not a physical superposition identity or an acceptance test. Both aerodynamic and structural discretization change together.

The source review found no specific defect in the inspected pointwise circulation, Glauert sampling and control-normal rules. Those structures are described in Drela’s [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf), equations 150–159 and 200. Their presence does not verify the complete implementation. A classical continuous lifting-line reference remains a separate idealized model because its aerodynamic operator differs from the enhanced finite-chord horseshoe formulation.

An independent classical lifting-line prototype passes the analytic elliptic-wing roll check with 8, 16 and 32 even modes, using exactly three reference-only linear solves. A separate 90-digit span-integral check agrees within 5.3e-18. These checks verify the idealized reference implementation, not OpenSwing. The finite-series local residual near the control jump remains nonzero and nonmonotonic; matching the integrated roll does not establish local loading convergence.

All owned physical children are terminal and reaped. Their summed recorded elapsed time is 407.45 seconds on this native shared host; it is not a browser benchmark. No production source, default setting, runtime bundle or hosted release was changed.

The next numerical comparison must address the remaining global discretization as well as the control-boundary cells. Finite experimental control amplitude, incidence/sign, section-control provenance, specimen/fixture discrepancy, driven-roll and reversal remain open. Coverage stays **17 partial / 24 pending / 0 fully validated**.

[Machine-readable results](isae-ae3-break-refinement.json) · [Earlier one-sided study](isae-ae3-mesh-sensitivity.md) · [Evidence archive](isae-ae3-break-refinement-20261024-evidence.zip)
