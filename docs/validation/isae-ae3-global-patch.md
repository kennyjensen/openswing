# AE-3 global refinement with fixed control-boundary cells

The new comparison passes **0/2 mesh checks and 0/2 finite-control checks**. AE-3 remains pending. These results apply to this mesh family; the original failed global comparisons remain recorded.

The coarse mesh has 161 nodes and 160 elements; the fine mesh has 287 nodes and 286 elements. Both share the same 32 fine cells around the two aileron boundaries and the same two immediately adjacent inboard intervals. The fine mesh splits the other 126 coarse intervals. Thus this study tests sensitivity to the remaining global discretization while holding the local patch fixed; it does not bound the error in that patch or establish a continuum limit.

| Pressure point | Coarse native Cl control derivative | Fine native Cl control derivative | Change / absolute fine result | Original 1% criterion |
|---|---:|---:|---:|---|
| 20O-04 | -0.000664217518896 | -0.000650699235813 | 2.077501% | FAIL |
| 20O-05 | -0.000241408378265 | -0.000225311470174 | 7.144291% | FAIL |

The criterion is |D_fine − D_coarse| / max(|D_fine|, 1e-30) ≤ 0.01. The original n128-to-n256 changes of 1.3579% and 4.5885% remain failures. Both aerodynamic and structural meshes change together; this comparison does not isolate their errors.

The finest 20O-05 zero-control state and derivative are reused exactly from the [local refinement study](isae-ae3-break-refinement.md). Each positive and negative finite-control case starts independently from that same state. With h in literal file-control units, the centered result is [Cl(+h) − Cl(−h)]/(2h).

| h | Centered native Cl control derivative | Absolute difference from implicit derivative | Allowed difference | Result |
|---|---:|---:|---:|---|
| 0.05 | -0.000225318459715 | 6.98954e-09 | 3.25311e-09 | FAIL |
| 0.025 | -0.000225318497806 | 7.02763e-09 | 3.25311e-09 | FAIL |

The unchanged tolerance is 1e-9 + 1e-5|D_fine|. These are numerical control-consistency checks, not a match to experimental finite control amplitudes. No primary-area, sign or radians conversion enters either numerical gate.

Exactly seven new equilibrium calls and three new full derivative calls completed, including four finite-control solves. The saved finest 20O-05 baseline and derivative were not rerun. The full derivative API step is 2.5e-6; production defaults are unchanged. The maximum fresh physical residual is 6.9832e-12; the maximum freshly recomputed full linear residual, including the reused baseline, is 1.08547e-12. Both are below the original 1e-8 limits. Existing rank and branch checks pass; the roll-rate column remains descriptive.

All seven owned children are terminal and reaped. Their summed monotonic elapsed time is 521.78 seconds; summed wall-clock duration is 739.54 seconds. The differing clocks are retained in the raw records. These native shared-host timings are not a browser benchmark. The independent saved-output audit verifies the frozen inputs, conditions, exact nodes, residual products, comparison formulas and call accounting. No production source, runtime bundle or hosted release changed.

Finite experimental control amplitude, incidence/sign, section-control provenance, specimen/fixture discrepancy, driven-roll and reversal comparisons remain open. No ASWING executable is available for direct parity tests. Coverage remains **17 partial / 24 pending / 0 fully validated**.

[Machine-readable results](isae-ae3-global-patch.json) · [Earlier global study](isae-ae3-mesh-refinement.md) · [Evidence archive](isae-ae3-global-patch-20261024-evidence.zip)
