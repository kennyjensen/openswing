# AE-3 mesh sensitivity at the aileron boundary

Two controlled local refinements show that the control response is sensitive to the cells beside the aileron boundary. **The original two global mesh-convergence failures remain unresolved, and AE-3 remains pending.** These diagnostics do not establish experimental agreement or a continuum error bound.

Both new 20O-05 cases retain every one of the 259 baseline nodes and add exactly two nodes, giving 260 elements and 3392 unknowns. A bisects the immediately outboard cell at each aileron break; B bisects the immediately inboard cell. The literal model, zero-control condition, q=1677.5468827199024 Pa, fixed-acceleration response and full derivative API step 2.5e-6 are unchanged. Aerodynamic and structural sampling change together, so this is not a separation of their discretization errors.

| Mesh | Native Cl control derivative | Signed change from baseline | Change / absolute baseline |
|---|---:|---:|---:|
| Saved n256 baseline | -0.000221145797928 | 0 | 0% |
| A-outboard | -0.000213962924621 | +7.18287331e-06 | +3.24803% |
| B-inboard | -0.000230726869097 | -9.58107117e-06 | -4.33247% |

The percentages describe local sensitivity. No new 1% acceptance test is applied to them. The preceding same-step n128-to-n256 comparisons still fail at 1.3579% and 4.5885% against their original 1% limit. No baseline rerun or finite-control solve was added here; the prior baseline finite-control passes do not automatically validate these new meshes.

Exactly two new equilibria and two full derivative calls completed. The fresh residuals of these unloaded equilibria are exactly zero in the saved floating-point results; freshly recomputed full linear residuals are at most 2.66231e-13. Both satisfy the unchanged 1e-8 gates. Dense rank and existing branch checks also pass. All owned physical children are terminal and reaped. The summed native child elapsed time is 165.47 seconds under shared-host load; this is not a browser benchmark.

A separate saved-matrix calculation used four captured circulation-block solves with two right-hand sides each, and no new physical solve. At the n256 worst-pressure point its fixed-geometry contribution is -0.00179024353, and the coupled-minus-fixed-geometry contribution is 0.00156909773; their sum is -0.000221145798. The sum of their magnitudes is 15.191 times the small net response. Both parts change between the original global meshes. Almost all of that output drift appears in the span-arm lift moment; direct section pitching moment is much smaller.

This decomposition uses the saved approximate linear operator. It is not an independently validated rigid-wing calculation. Saved-output reconstruction remainders and support-balance differences are retained in the machine-readable report. Spatial contribution changes locate changes in the output, not the origin of a discretization error. The normalized roll-rate column is descriptive only.

The source review found both exact control boundaries in all meshes, unchanged control support, consistent material sampling and consistent virtual-power load transfer. The immediately outboard cell remained unchanged through the original 64/128/256 refinements. No missing-moment or dropped-boundary defect was established, and no production kernel change was made.

The next numerical task is a systematic refinement of the cells adjoining control discontinuities. Experimental finite-control amplitude, incidence/sign, section-control coefficient provenance, mechanical fixture discrepancies, driven-roll and reversal comparisons remain open. No original ASWING executable is available. Coverage stays **17 partial / 24 pending / 0 fully validated**. Browser bundles and the hosted release are unchanged.

[Machine-readable results](isae-ae3-mesh-sensitivity.json) · [Original refinement failures](isae-ae3-mesh-refinement.md) · [Raw evidence](isae-ae3-mesh-sensitivity-20261024-evidence.zip)
