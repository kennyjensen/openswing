# AE-1 full current frozen-influence sweep

Observed 2026-11-10T04:51:56.287723+00:00. The user-selected focus remains AE-1.

The current scope is **1,170/1,200 passing at 5% (97.5%)**. All 100 original rows, six absolute sensor channels and both nominal 40/80 meshes remain required. The complete positive-speed sweep contains 196 physical states and 1,176 computed values: 1,170 pass and six fail. No positive-speed values remain unrun. The 24 outputs belonging to the two unknown startup states on both meshes remain in the denominator. Computed values represent 588 distinct native cells, with no extra votes for retained pilot results.

This explicitly makes the complete default-frozen scope the primary progress measure, replacing the historical updated-influence 98/1,200 strict baseline as primary. That baseline remains visible and unchanged. The user previously requested frozen influences as the default; this scope uses that setting and the existing 5% policy. It does not establish the archived K/F setting, change an equation, fit a property or declare AE-1 fully validated. The former 72/96 frozen pilot remains preserved [here](isae-ae1-current-20261110.md), and is included once in this full scope.

**Both positive-speed sweeps are complete**: every commanded speed from 1 through 56 m/s at 5°, and 1 through 42 m/s at 7°, on both meshes. All 504 computed 7° comparisons pass. This extension adds 78 physical states and 468 passing values without a new numerical failure or retry.

| Incidence | Passing / full required scope | Positive operating points checked | Remaining |
|---|---:|---:|---|
| 5° | 666/684 | 56/56 on both meshes | Six near-zero Z failures and twelve unknown-start outputs |
| 7° | 504/516 | 42/42 on both meshes | Twelve unknown-start outputs |

## Current agreement and the six failures

Median absolute relative error over all 1,176 computed values is **0.14299%**. The 1,170 passing values have maximum error 3.891%. All **5,684 physical checks pass**, with maximum fresh residual 9.76e-13. One worker reached its elapsed timer after both numerical states and all physical checks were saved. Its metadata was [finalized separately](isae-ae1-saved-finalization-20261110.md), preserving the timeout and requiring no additional solve or residual evaluation. Seven regression checks verify that incomplete or detached evidence is rejected.

All six native failures are the Z positions at **5° and 17 m/s**, on both meshes. Typical failed error is **14.00% median**, ranging **7.88–46.12%**; absolute errors are only **31.43–35.05 µm**. These remain failures under the unchanged pointwise criterion.

| Channel | Native Z (µm) | Mesh 40 error (µm / %) | Mesh 80 error (µm / %) |
|---|---:|---:|---:|
| Sensor 1 | -76.009 | 35.052 / 46.116% | 31.935 / 42.015% |
| Sensor 2 | -398.827 | 34.552 / 8.663% | 31.431 / 7.881% |
| Sensor 3 | -237.418 | 34.802 / 14.659% | 31.683 / 13.345% |

A saved-data diagnostic compares the response increment from **1 to 17 m/s**, both known operating points. At 1 m/s, Z errors are below 0.16 µm. The response-increment errors are 0.185–0.205%, so a constant gravity-sag offset does not explain the crossover miss. This suggests a small aerodynamic loading or discretization discrepancy; it does not identify the cause. No inferred baseline correction is applied and the diagnostic adds no acceptance votes. [Values and original-result hashes](../../artifacts/isae/ae1-full-current-20261110/crossover-analysis.json).

The largest pointwise mesh change is 7.073% at sensor 1 at the same crossover. Its dimensional change is about 3.12 µm. This is a cancellation-sensitive coordinate; do not describe it as having passed a relative mesh-convergence gate. The existing adapter keeps mesh sensitivity descriptive. Original NODE I40 arrays and startup atmosphere remain unknown.

A [source review](../../artifacts/isae/ae1-full-current-20261110/crossover-source-review.json) rules out tuning the core ratio in this calculation: force and circulation receivers pass the same physical-beam identity, giving zero self-core, and image terms inherit that radius. This agrees with the manual's single-surface statement. The six comparison outputs are geometric sensor quantities, unaffected by external sensor-flow sampling. The original node grid remains a more relevant unresolved setup issue; the doubled stiffness station and version-specific spacing rules do not establish a unique native grid.

The subsequent [source-based spacing probes](isae-ae1-spacing-current-20261110.md)
show 11–74 µm changes at 17 m/s but less than 0.25 µm at the known 1 m/s control.
All eight alternative-grid states pass physical checks. This supports a
load-dependent discretization explanation, while neither mapping recovers the
native grid or resolves all three Z channels on both meshes. These unscored
probes leave the completed primary sweep, its six failures and its defaults unchanged.

## Dimensional curve errors

These are descriptive errors for absolute sensor-3 Earth Z and elevation over every known positive speed. They do not subtract an inferred startup baseline or add acceptance votes. Part IV Figure 1 presents deflection and twist; the archived MATLAB deflection subtracts its initial row, whose operating condition is unknown here. Absolute coordinates therefore remain the primary comparison.

| Incidence | Nominal mesh | Positive speeds | Tip Z RMS error (mm) | Tip Z max error (mm) | Elevation RMS error (deg) | Elevation max error (deg) |
|---|---:|---:|---:|---:|---:|---:|
| 5° | 40 | 56 | 0.244112 | 0.611759 | 0.00144026 | 0.00273891 |
| 5° | 80 | 56 | 0.240319 | 0.626582 | 0.00154074 | 0.00310968 |
| 7° | 40 | 42 | 0.131275 | 0.267807 | 0.00075163 | 0.00123517 |
| 7° | 80 | 42 | 0.121957 | 0.253054 | 0.00077640 | 0.00128777 |

On the finer mesh, maximum Z error is 0.2545% and 0.1528% of the corresponding native curve's positive-speed range at 5° and 7°. These curve-scale figures explain why the overlays agree closely despite the six large pointwise percentages near zero; they do not replace the original pointwise criterion. [Complete dimensional metrics and source-summary hash](../../artifacts/isae/ae1-full-current-20261110/dimensional-metrics-0184.json).

## Setup and execution

The authoritative [reference index](aswing-authoritative-references.md), [Part IV catalog](../../reference/aswing-authoritative-20261108/isae-part-4.json), and [Part IV §3.1, pp.8–9, Figure 1](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf) were reviewed. The model, shell drivers, output tokens and MATLAB channel conventions are unchanged. The same literal Pazy input includes both inactive zero-weight records. The script requests NODE I40 but supplies no original node arrays or `.set` file.

The declared reconstruction remains mounted, density 1.23 kg/m³, IAS assigned as TAS, PG Mach zero, gravity [0,0,−9.81], ground image normal [0,1,0], source coupled structural equations, and frozen jig-geometry influences. The original manual documents the fast K/F option; neither driver explicitly selects it. Experimental and UM/NAST curves are separate from the native acceptance targets.

The full sweep launched **184 new cold states**, reusing exactly the twelve current-code states and four unknown-start records from the prior pilot. Their canonical jobs and source/kernel hashes match. Every new state has one fresh restored residual and independent load/sensor checks. The frozen plan includes all 200 records before execution; seven original batch receipts and 70 continuation receipts are retained. **All 196 positive-speed physical states are computed**.

Each numerical process has one BLAS thread, 512 MiB address-space and 15 CPU-second limits, a 25-second elapsed timer and a 30-second supervisor timeout. Peak reported RSS is 98.1 MiB. The available worker timers record 2.95–21.91 seconds. The interrupted job did not save timing/RSS, so those entries remain unavailable; metadata-audit time is not reported as numerical runtime. Later UTC elapsed times diverged sharply from process elapsed timers: batch 5 spans about 740 UTC seconds versus 126.5 timer seconds. The cause is not established; these are not interchangeable timing measurements. The explicit continuation uses two-job serial batches and refuses any unreviewed failure. All launched children are reaped; no background solver remains.

The independent saved-data audit imports no production solver and checks every source/kernel/artifact hash, adapter contract, physical requirement, raw sensor value and available mesh pair. All 1,176 positive-speed outputs are checked; the 24 unknown-start outputs remain explicit unavailable records, never silently omitted. The original first two pilot policy-view accounting omissions remain documented; the common contract is reapplied to their saved strict results without another solve.

## Curves and remaining work

![Absolute sensor curves; every known positive-speed point is computed](../../artifacts/isae/ae1-full-current-20261110/complete-0184-sensor-curves.png)

![Fine-mesh native errors](../../artifacts/isae/ae1-full-current-20261110/complete-0184-sensor-errors.png)

The positive-speed sweep is finished, and no additional failures appear at 7°. Remaining work is to resolve the six near-zero comparisons with source-supported discretization/operating-setting evidence and recover the native startup conditions. The archived node arrays, atmosphere and K/F selection remain unknown; the current choices are disclosed reconstructions. Keep the six failures and 24 unknown-start values required. No property fitting, baseline correction, tolerance change or claim of recovered historical settings is justified. Browser/Node/build testing remains held. ST-5 stays deferred.

Evidence: [full frozen plan](../../artifacts/isae/ae1-full-current-20261110/plan.json), [current 1,200-slot audit](../../artifacts/isae/ae1-full-current-20261110/complete-0184.json), and per-job raw results/terminal receipts under `artifacts/isae/ae1-full-current-20261110/`. Execution used `scripts/continue_isae_ae1_sweep.py batch --output artifacts/isae/ae1-full-current-20261110 --plan continuation-plan-0001.json` with one BLAS thread. All planned records are now terminal; the batch command has no remaining work. The saved-data audit is `scripts/summarize_isae_ae1_sweep.py artifacts/isae/ae1-full-current-20261110 --output-name <new-name>.json`; use a new output name and the same resource limits for each observation.

This observation adds 78 physical states since the previous status, all completed normally. The previous [702/1,200 observation](../../artifacts/isae/ae1-full-current-20261110/partial-0106.json), earlier [306/1,200 observation](../../artifacts/isae/ae1-full-current-20261110/partial-0040.json), and their report snapshots remain retained. No production module, model, native token, acceptance threshold or comparison scope changed in this extension.
