# ISAE AE-1-S: source and comparison scope

The comparison uses an explicitly derived Pazy skin-on model, corrected primary structural properties, and an ideal solid-wall representation through a mirrored full wing. It preserves the literal ISAE model as separate evidence. The supplied experimental curves contain 92 paired speed coordinates: 5° at 3–56 m/s and 7° at 4–41 m/s. These processed coordinates are not a count of independent raw experiments. The [pinned source review](isae-ae1-source-scope.json) records every coordinate, qualification and input hash.

A full static sweep computes equilibria. It does **not** compute their stability, predict oscillation amplitudes, or establish full AE-1 validation. Numerical convergence and experimental agreement are separate questions.

## Experimental dynamic indications

Avin et al. report a strain-response peak and frequency coalescence near **48 m/s at 5°**, followed by disappearance of the peak as speed increases. They describe evidence of possible instability without giving exact onset and recovery boundaries. At **7°**, strain and spectral growth indicate instability at **40 m/s**; visible large oscillations at 43 m/s caused rapid manual speed reduction. These are Test 2 observations with the floor mounting and added tip mass. Later no-tip-mass flutter boundaries must not replace them. See [Avin et al., §V.B.2–3, Figs. 36–40, pp. 21–22](https://www.researchgate.net/publication/357596316_Experimental_Aeroelastic_Benchmark_of_a_Very_Flexible_Wing), DOI [10.2514/1.J060621](https://doi.org/10.2514/1.J060621).

The JSON therefore tags 81 coordinates as below the reported indicators, one as the reported possible-instability peak, eight as above that peak with an unresolved recovery boundary, and two as at or above the 7° instability indication. **None receives a certified stability classification.** High-speed equilibrium predictions remain useful comparisons, but cannot automatically represent a measured oscillatory mean.

## Measurement and model definitions

The primary comparison neglects gravity. It uses midchord displacement—measured directly at 5° and estimated from leading/trailing-edge positions at 7°—and differential-chord twist. The [Riso–Cesnik author preprint, §IV.C, p. 18](https://www.researchgate.net/publication/366714346_Impact_of_Low-Order_Modeling_on_Aeroelastic_Predictions_for_Very_Flexible_Wings) describes this setup; its published version is [10.2514/1.C036869](https://doi.org/10.2514/1.C036869).

The processed export does not explicitly resolve whether “vertical” means root-normal or tunnel-normal. Both baseline-subtracted projections are retained against the same observation, not counted as additional observations. With native wind direction `(cos α, 0, sin α)`, they are `Δz` and `−sin α Δx + cos α Δz`, normalized by the nominal 0.55 m semispan. Twist is the baseline-subtracted projected LE/TE chord angle in degrees, not an arbitrary Euler component.

The adapter retains the primary 44.1%-chord reference axis and rigid tip-section approximation. No new axis or twist-sign discrepancy was found. The actual material span remains unchanged; experimental normalization uses 0.55 m. See the [mirror/setup review](isae-ae1-mirror-source.json) for the existing limitations.

## Independent follow-up hypotheses

1. **Use the saved loads first.** Compare local incidence, circulation, stall contribution and section torque distributions with bending and twist. This can distinguish a load-distribution difference from an output-definition problem without changing inputs.

2. **Separate potential-flow model assumptions.** Riso–Cesnik use a 36-by-18-panel VLM and a separate 15-strip model with `2π` section lift slope and quarter-chord aerodynamic center. Its tip correction is tuned to VLM displacement, not twist; the reference models omit stall, viscosity and thickness. The supplied `*_UVLM.txt` curves belong to the VLM branch. See §III.C, pp. 9–13, and §IV.C, p. 21 of the [author preprint](https://www.researchgate.net/publication/366714346_Impact_of_Low-Order_Modeling_on_Aeroelastic_Predictions_for_Very_Flexible_Wings). The current inherited slope, 6.1185/rad, is 2.62% below `2π`. A separately declared `2π`, no-stall comparison would test assumptions; it would neither reproduce the VLM discretization nor justify fitting coefficients.

3. **Keep viscous pitching moment distinct.** The supplied [XFOIL polar](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/blob/f62943df20e9e4d7d9f50e070477b22426b5f865/4%20-%20Aeroelasticity/AE%20-%20Aeroelastic%20Cases/AE-1-S%20Pazy%20Wing%20-%20Steady%20Deflection/xf-naca0018-il-200000-n5.txt) uses Re = 200,000, Mach 0 and Ncrit = 5. At local section incidences of 5° and 7°, its `Cm` values are +0.0103 and +0.0061. Relative to the illustrative lift-arm torque coefficient `0.191 CL`, these are about 10.3% and 4.18%. They are **not predicted changes in wing twist**: root incidence is not local incidence, and Reynolds number and induced flow vary. This numerical polar is not matched experimental section evidence. It may inform an experiment-side hypothesis, but cannot by itself explain disagreement with an inviscid primary VLM.

These are prospective investigations. The source review changed no sweep inputs, kernel equations or model parameters and performed no aircraft calculations.
