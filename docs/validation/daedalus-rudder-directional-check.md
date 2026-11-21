# Daedalus rudder-to-yaw: directional derivative check

All **12 comparisons passed** at the saved 16-panel-request loaded state. The largest derivative discrepancy was **8.7406906e-10**, using **4.3703%** of its allowed tolerance. This supports the assembled derivative in six tested directions. It does not establish every matrix entry, mesh convergence, or agreement with the unidentified operating point of Drela's published curve.

The case keeps the existing **30 ft/s, PG Mach 0.1, free-frame** steady trim and native F3 command. It uses the exact saved dynamic base, 108 frozen source modules and original coordinate scales: 117 nodes, 112 elements and 2,215 descriptor coordinates. No new trim, full linearization, harmonic solve or production edit was made. The selected **8.90352386262554 Hz** response came from the largest observed complex mesh change in the completed sweep; that diagnostic selection occurred after the sweep.

The check compares the complete physical residual with `A = R_z`, `M = -R_zdot` and `B = R_u`. Real and imaginary state/rate response directions are normalized independently. State and native-control widths are `1e-5` and `5e-6`; rate widths are those values multiplied by `W = 0.527658212781417` per input second. Each width uses the four-point centered stencil. Every row must satisfy `abs(error) <= 2e-8 + 2e-8*abs(prediction)` at both widths; no width is selected after seeing its result.

| Direction | Largest absolute difference | Largest fraction of allowance | Widths passed |
|---|---:|---:|---:|
| State: real response | 8.39279e-10 | 4.196% | 2/2 |
| State: imaginary response | 8.74069e-10 | 4.37% | 2/2 |
| Rate: real response | 1.37548e-11 | 0.06877% | 2/2 |
| Rate: imaginary response | 1.04827e-11 | 0.05241% | 2/2 |
| Native rudder F3 | 6.66443e-12 | 0.03273% | 2/2 |
| Primitive body yaw rate | 7.15476e-12 | 0.03331% | 2/2 |

The fresh full residual was **1.2335211e-13**, below the unchanged `1e-8` gate. Actual work was **49 complete residual evaluations** (one base plus 48 probes), four signed and four absolute saved-matrix products, and **961 original local 3×3 solve calls** (one constructor Euler map plus 960 probe calls, some batched). There were no full-system factorizations, equilibrium solves or harmonic solves. Child time was **14.5767 s**, supervisor time **15.3226 s**, and peak RSS **117,260 KiB**; these are single observations, not performance claims.

The independent saved-output audit passed **648/648 checks**. It recomputed all 12 stencils from the 48 raw vectors, checked every error, mask and row-block summary, and separately accumulated the stencil numerators with scalar `fsum`. That accumulation changed a derivative by at most **5.55112e-17**; all 12 still passed. The audit made zero physical calls, matrix products, factorizations or solves. It verified that the captured A/M products were used unchanged, and independently extracted the native B vector and primitive yaw column from the original saved arrays; it deliberately did not repeat the four A/M products.

The archive retains the **unexecuted prelaunch accounting draft** that incorrectly expected only one local solve. Its correction allowed and recorded the source's existing small rotation-interpolation solves before launch; it was not a failed numerical experiment. The reviewer's retained Path/string metadata-check failure is also separate from the physical result.

Passing these selected directions does not explain or remove the remaining mesh changes, prove stability, or identify the published reference point. Primary-source research identifies a Daedalus design cruise condition but does not establish the speed or trim of `rudder-bode.pdf` operating point 1. The 30 ft/s comparison is retained without fitting it to the curve. No primary PDFs are redistributed.

[JSON summary](daedalus-rudder-directional-check.json) · [Raw evidence](daedalus-rudder-directional-check-20261024-evidence.zip). The source, A/M/B and loaded base are referenced from the previously published [mesh evidence](daedalus-rudder-mesh-20261024-evidence.zip), and the selected response from the previously published [sweep evidence](daedalus-rudder-sweep-20261024-evidence.zip). Their exact hashes and member references are recorded in the archive dependency map.
