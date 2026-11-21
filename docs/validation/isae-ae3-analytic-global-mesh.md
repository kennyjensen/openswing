# AE-3 global mesh comparison with corrected circulation derivatives

Both matched mesh comparisons still fail the original 1% criterion. The changes are **2.0773%** and **7.1435%**. The analytic circulation correction resolves the earlier default-step control-consistency issue, but does not resolve global mesh sensitivity. AE-3 remains pending.

| Pressure point | Coarse native Cl control derivative | Fine native Cl control derivative | Change / absolute fine result | Original 1% criterion |
|---|---:|---:|---:|---|
| 20O-04 | -0.000664224586536819 | -0.000650707547716884 | 2.077283% | FAIL |
| 20O-05 | -0.000241414230841878 | -0.000225318510512193 | 7.143541% | FAIL |

Both endpoints use the exact corrected 107-module source, fixed-acceleration/standard/stability derivatives and the unchanged default API step 1e-5. The derivative is native stability Cl per literal file-control setting; no experimental area, sign or radians conversion enters the gate. The formula remains |D_fine − D_coarse| / max(|D_fine|, 1e-30) ≤ 0.01.

The coarse mesh has 161 nodes and 160 elements, and the fine mesh has 287 nodes and 286 elements. They share 32 refined control-boundary cells and two adjacent intervals; the fine mesh splits the remaining 126 coarse intervals. Aerodynamic and structural grids change together. This comparison neither separates their errors nor bounds the fixed local patch error.

Exactly three new derivative-only calls reuse the saved zero-control equilibria: coarse/fine 20O-04 and coarse 20O-05. The corrected fine 20O-05 derivative is reused from the [matched analytic-circulation study](isae-ae3-analytic-gamma.md). There are **zero new equilibrium or finite-control solves**. Conditions, meshes and restored states are checked against the saved inputs. Historical input specifications retain their original 2.5e-6 step; new calls explicitly use 1e-5.

All four base/post physical residuals are zero. The maximum recomputed full linear residual is 1.32550e-12, below the unchanged 1e-8 gate. The minimum reciprocal condition estimate is 2.23087e-7, above the unchanged 1e-10 threshold. Every derivative uses the guarded analytic circulation block and retains all checked centered circulation probes. Repeated saved matrix products use the previously reviewed dimension-dependent roundoff bound; stored and recomputed residuals each independently satisfy the original physical gate.

Both older shared-patch mesh failures (2.0775% and 7.1443%), the earlier global-family failures (1.3579% and 4.5885%), and the original finite-control failures remain recorded with their original source and step. The corrected finest-state finite-control checks already pass; they are reused evidence, not new solves or new acceptance decisions in this study. Roll-rate derivatives are descriptive and do not change the control-derivative mesh verdict.

All three owned children completed and were reaped. Their summed monotonic elapsed time is 160.07 seconds; these native shared-host runs are not a browser benchmark. Independent review checks the saved matrices, exact source/input identity, shared-patch topology, comparison formulas, original gates and call accounting. No production physics, runtime bundle or hosted release changed. The separate [packaged browser check](analytic-gamma-browser.md) passes for two small unpowered cases.

The next numerical work is to separate the aerodynamic and structural contributions to this sensitivity before selecting further refinement. Experimental amplitude/incidence/sign, section-control provenance, specimen/fixture correspondence, driven-roll and reversal remain open. No original ASWING executable is available. Coverage remains **17 partial / 24 pending / 0 fully validated**.

[Machine-readable results](isae-ae3-analytic-global-mesh.json) · [Original shared-patch study](isae-ae3-global-patch.md) · [Evidence archive](isae-ae3-analytic-global-mesh-20261024-evidence.zip)
