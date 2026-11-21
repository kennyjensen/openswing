# AE-3 refinement of the remaining 20% aileron points

All seven planned process outcomes are terminal; 7/7 cases returned successfully. The two common-step mesh checks have 0 passes, 2 failures and 0 unavailable comparisons. The centered-control checks have 2 passes, 0 failures and 0 unavailable comparisons. **AE-3 remains pending.** Numerical agreement does not establish experimental validation.

The stage used 6 new equilibrium solves (maximum six) and 3 new derivative calls (maximum three). The plan reuses the saved 20O-05 n128 derivative and restores 20O-04 n128 for its derivative only. Every computed mesh comparison uses full API step **2.5e-6** at n128 and n256, with fixed-acceleration response, standard basis and stability axes. The step controls state/input probes and directional output stencils together.

The original mesh gate is |D256−D128|/max(|D256|, 10⁻³⁰) ≤ 1%. Here D is native stability Cl per literal file-control setting; no experimental area/sign mapping or radian conversion is applied inside the gate. The original fresh and full linear residual limits remain 1e-8, with dense rank threshold 1e-10 and existing branch checks.

| Point | q (psf) | D128 | D256 | Adjacent change (%) | Original 1% gate |
|---|---:|---:|---:|---:|---|
| 20O-04 | 29.9603 | -0.000638407334271 | -0.000647195509174 | 1.357886 | **FAIL** |
| 20O-05 | 35.0363 | -0.000210998467177 | -0.000221145797928 | 4.588525 | **FAIL** |

Only the highest-pressure 20O-05 sentinel has new finite controls, each starting independently from its n256 zero-control base. The unchanged gate is |D_h−D256| ≤ 1e-9 + 1e-5|D256|. These are numerical checks, not the unknown experimental finite amplitudes.

| Sentinel | h (file-control units) | Centered derivative | Absolute difference | Original limit | Gate |
|---|---:|---:|---:|---:|---|
| 20O-05 n256 | 0.05 | -0.000221147715838 | 1.91791e-09 | 3.211458e-09 | **PASS** |
| 20O-05 n256 | 0.025 | -0.000221147742557 | 1.944629e-09 | 3.211458e-09 | **PASS** |

Retained current-stage failures: {"kind": "mesh_control_derivative", "observation_id": "20O-04"}; {"kind": "mesh_control_derivative", "observation_id": "20O-05"}.

The largest fresh equation residual is 4.860612e-12; the largest freshly recomputed linear residual is 2.604583e-13. Both are below their unchanged 1e-8 limits. The independent saved-output audit passes; scientific gate outcomes remain separate.

The original six 32→64 mesh failures, two 64→128 mesh failures and both 20O-05 n128 centered-control failures at API step 1e-5 remain in their original reports. The later smaller-step diagnostic is separate evidence and is reused here without rewriting those outcomes. No mixed-step 64→128 comparison replaces the archived study.

Every owned child has a 600-second cap; the recorded children used 504.39 seconds of combined monotonic process time. Terminal outcomes, both elapsed clocks and phase timings are retained in the JSON. These are single planned native runs under shared-host load, not browser timings or a controlled performance comparison. No automatic retry, pressure change or further mesh refinement is part of this stage.

The normalized p column is descriptive and has no new acceptance gate. Adjacent mesh agreement is not a continuum error bound. Finite experimental deflection, incidence/sign conventions, section-control provenance and mechanical specimen/fixture discrepancies remain unresolved; no reversal or pressure-endpoint calculation is included. Coverage remains **17 partial / 24 pending / 0 fully validated**.

[Machine-readable report](isae-ae3-mesh-refinement.json) · [Earlier 70-state comparison](isae-ae3-locked-control.md) · [Raw evidence archive](isae-ae3-mesh-refinement-20261024-evidence.zip)
