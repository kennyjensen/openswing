# AE-3 derivative-step refinement on the finest control-boundary mesh

The two smaller API steps pass **4/4 new finite-control comparisons**. The original 2.5e-6 failures remain recorded. These are numerical consistency checks on one saved state. **The two global mesh failures remain, and AE-3 remains pending.**

Both calls restore the exact same zero-control state on the 287-node, 286-element mesh. The 3,730 unknowns and fresh base residual match the saved reference exactly. No equilibrium, finite-control or baseline derivative was rerun. Each new derivative is compared with the two existing nonlinear pairs, h=0.05 and 0.025 in literal file-control units.

| Full API step | Native Cl control derivative | Error against h=0.05 | Error against h=0.025 |
|---|---:|---:|---:|
| 2.5e-06 (saved) | -0.000225311470173876 | 6.98954e-09 (FAIL) | 7.02763e-09 (FAIL) |
| 1.25e-06 | -0.000225316750378191 | 1.70934e-09 (PASS) | 1.74743e-09 (PASS) |
| 6.25e-07 | -0.000225318070483195 | 3.89232e-10 (PASS) | 4.27323e-10 (PASS) |

Each comparison retains the original tolerance, 1e-9 + 1e-5|D_step|, evaluated with that row's derivative. The two saved 2.5e-6 failures remain failures. The signed coefficient is native stability Cl per literal control unit; no primary-area, control-sign or radians conversion enters these gates.

The ratio of successive control-derivative changes is 0.25001021. This is a descriptive trend, without an extrapolated answer or new acceptance gate. The API step changes state probes, input probes and directional output stencils together. Improvement cannot be attributed solely to the Jacobian. Actual parameter and output steps remain in the raw results; the roll-rate column is descriptive.

Exactly two new derivative calls completed. The maximum fresh base/post-state residual is 0; the maximum freshly recomputed full linear residual, including the reused baseline, is 1.11465e-12. Both satisfy the original 1e-8 limits. Existing rank, branch and cache-ownership checks also pass. Independent saved-output review verifies the frozen inputs, restored state, full matrix-residual products, comparison arithmetic and call accounting.

Both owned children are terminal and reaped. Summed monotonic time is 312.94 seconds and summed wall-clock duration is 730.28 seconds. These are native shared-host records, not browser timings or a speedup benchmark. All 106 physics modules remain unchanged; the production API default remains 1e-5. Runtime bundles and hosted release were not updated.

The [shared-patch study](isae-ae3-global-patch.md) retains its 2.0775% and 7.1443% mesh failures. This step study does not reevaluate those comparisons with mismatched coarse/fine steps, bound the fixed patch's error, or validate the experiment. Control amplitude, incidence/sign, section-control provenance, fixture/stiffness correspondence, driven-roll and reversal remain open. Coverage stays **17 partial / 24 pending / 0 fully validated**.

[Machine-readable results](isae-ae3-fine-derivative-step.json) · [Earlier step study on a different mesh](isae-ae3-derivative-step.md) · [Evidence archive](isae-ae3-fine-derivative-step-20261024-evidence.zip)
