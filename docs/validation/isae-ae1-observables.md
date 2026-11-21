# Pazy observable definitions: source limits and saved alternatives

The retained sources do not resolve the coordinate transform, zero reference or time-processing recipe used for the exported Test 2 measurements. The saved alternatives below therefore remain diagnostics. A smaller RMSE does not identify the correct experimental convention.

The independent saved-data audit passes **20,714/20,714 checks**. It reconstructs 392 derived rows from the 196 retained airflow rows, two influence settings and two matched no-flow baseline files. It preserves 184 unique finite experimental scalar observations at 92 coordinates, plus 12 missing scalar values across the 98 positive commanded coordinates. No airflow raw states were reread and no physics, residual, assembly or solve was run.

The midpoint of saved LE/TE Earth positions equals the retained sensor-3 position to a maximum z difference of 4.34e-19 m. The largest difference between projected chord angle and absolute sensor-3 elevation is 0.000243029°. Subtracting the matching baseline chord angle changes that maximum comparison to 0.000244118°. These definitions do not explain the much larger experimental twist differences.

The displacement alternatives use the same equilibrium and its own matched baseline: root-normal Δz, or wind-normal −sin(α)Δx + cos(α)Δz. Their projection changes neither the physical gravity vector nor the equilibrium. The following nominal-120 statistics use every available measured coordinate; displacement RMSE is in percentage points of the 0.55 m semispan. No experimental acceptance band is imposed.

| Influence setting | Incidence | Measured coordinates | Root-normal displacement RMSE | Wind-normal displacement RMSE | Absolute elevation RMSE (°) | Baseline-subtracted chord-angle RMSE (°) |
|---|---:|---:|---:|---:|---:|---:|
| Frozen | 5° | 54 | 3.494354 | 3.408271 | 0.212119 | 0.212093 |
| Frozen | 7° | 38 | 0.681155 | 0.630816 | 0.297729 | 0.297723 |
| Updated | 5° | 54 | 2.466610 | 2.386047 | 0.236161 | 0.236140 |
| Updated | 7° | 38 | 0.575788 | 0.527657 | 0.299503 | 0.299498 |

At nominal 120, the largest change between these displacement projections is 0.253512 percentage points of semispan (1.3943 mm). Removing coordinates at or above the previously reported dynamic indicators still leaves material differences: frozen root-normal displacement RMSE is 1.955907% span at 5° and 0.627505% at 7°, with elevation RMSE 0.190434° and 0.273932°. Those subsets contain 45 and 36 measured coordinates. They are below reported indicators, not certified stable cases; a static equilibrium does not establish an oscillatory time mean.

The new source detail is narrower than a measurement correction. Avin et al. define calibrated MRS X/Y/Z as chord/span/out-of-plane axes in §IV. Their Test 1 discussion uses incremental results excluding an initial approximately −1° twist, and §V.A.2 describes 120 Hz MRS acquisition and a 500-sample moving average for trend plots. These statements do not specify the Test 2 export transform, baseline or filtering procedure. They cannot justify shifting the present data. [Avin et al., DOI 10.2514/1.J060621, §§IV, V.A.1–2](https://www.researchgate.net/publication/357596316_Experimental_Aeroelastic_Benchmark_of_a_Very_Flexible_Wing).

A separate primary paper explicitly extracts slowly varying and oscillatory components with 1 Hz filters, and discusses camera reflections, loss of line of sight, offsets and sensitive twist recovery at large deformation. Its studied sweep is 7° to 55 m/s, so it is not established as the current Test 2 export. Its filter and approximate sensor-error sensitivity are not transferred into a present uncertainty band. This is evidence that the processing chain matters, not proof that these exported points are wrong. [Drachinsky, Freydin and Raveh, DOI 10.2514/1.J061832, §V.D, author-PDF pp. 10–11](https://www.researchgate.net/publication/361074479_Large_Deformation_Shape_Sensing_Using_a_Nonlinear_Strain_to_Displacement_Method).

The author data README and Riso–Cesnik comparison identify differential LE/TE twist and midchord displacement; they do not provide the raw calibration and export algorithm. Previously documented direct 5° midpoint measurements, estimated 7° LE/TE means, gravity assumptions and dynamic indicators remain unchanged. [Pinned author repository](https://github.com/UM-A2SRL/AePW3-LDWG/tree/396710a19a80004c65c767e9955fe60d59565c39), [Riso–Cesnik, §IV.C, author-preprint p. 18](https://www.researchgate.net/publication/366714346_Impact_of_Low-Order_Modeling_on_Aeroelastic_Predictions_for_Very_Flexible_Wings).

No new coefficient, axis, baseline or gravity correction is justified. The next source-driven diagnostic requires the raw Test 2 timestamps, marker positions, wind-speed records, calibration/root-pose transform and export procedure. A bounded saved-data check could then verify subtraction, rotation, filtering and speed resampling, including angle-before-filter versus angle-after-position-filter. The current processed files alone cannot establish that sequence. No outreach or new solve is proposed as part of this completed stage.

The literal model with transverse gravity remains distinct from a primary-property, zero-gravity experimental reconstruction. Historical ASWING influence settings remain unknown. The numerical checks here establish reduction consistency only.

The [saved-map report](isae-ae1-observables.json), [392-row CSV](isae-ae1-observables.csv),
[primary-source review](isae-ae1-observables-sources.json),
[independent arithmetic audit](isae-ae1-observables-audit.json), and
[geometry derivation](isae-ae1-observables-geometry.json) retain the evidence.
The original frozen and updated curve reports remain unchanged. The evidence
archive for the accompanying AE-2 pilot retains the saved-only driver, plans,
source excerpts and preparation history. No production source, default,
experimental acceptance band or family classification changes follow.
