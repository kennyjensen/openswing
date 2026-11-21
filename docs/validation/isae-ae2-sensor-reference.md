# AE-2 sensor field diagnostic

The independent field calculation reproduces the current frozen-geometry sensor result, but moving the receiver alone does not resolve the archived ASWING difference. It makes both selected flow observables farther from the archive.

| Nominal mesh | Receiver | Speed (m/s) | Sensor beta (deg) |
|---:|---|---:|---:|
| 80 | Jig | 10.0090761954 | 6.14177475067 |
| 80 | Current | 10.1202091641 | 5.95586696353 |
| 160 | Jig | 10.0090767549 | 6.14183163154 |
| 160 | Current | 10.1202114303 | 5.95590644131 |
| — | Archived ASWING | 10.0115 | 6.27943 |

For the fine state, current-receiver sampling changes the induced body-frame velocity from `[0, −0.09861257521, 0]` to `[0.11068800707, −0.05757337604, −0.31212135890]` m/s. The moved receiver is off the frozen source plane; the strong additional out-of-plane velocity is mostly the physical trailing-vortex contribution. The complete bound/wake and physical/image decomposition is retained in the JSON and CSV. Applying the same current sensor triad and documented Eq107 transformation then increases the beta discrepancy from −0.13759837° to −0.32352356°, and the speed discrepancy from −0.00242325 to +0.10871143 m/s.

Exactly eight complete field products used the two saved frozen-PG0 meshes, two receiver locations, and Gauss orders 64/128. Sources, saved circulation, 0.035 m core, solid-wall images, imposed flow and current sensor axes were unchanged. The implementation directly integrates the regularized Biot–Savart formula in Drela steady Eq161; it imports no production code. All 130 fixed checks passed. The largest baseline induced-component discrepancy was 9.29e−15 m/s; the largest quadrature field-component difference was 7.11e−15 m/s, within the declared componentwise 2e−10 absolute plus relative gate.

This is a finite field diagnostic at saved states, not a new equilibrium or proof of the historical ASWING sensor policy. There were zero equilibrium solves, circulation solves or residual calls. The one capped process completed successfully in 1.196 s including imports (0.319 s for input checks and the field loop); owner session 81237 exited 0 and was reaped. No retry occurred.

The earlier source review already verified the scalar speed/beta convention and identified the jig sensor exactly on its own tip trailing filament. A zero-core substitution is singular and is neither tested nor proposed. Current-position sampling is not supported as a correction by these results. The remaining archived local-flow discrepancy requires evidence about the historical sensor/core or circulation/discretization policy; no defaults or physical properties were changed.

Primary equation and source locators are retained in `protocol.md` and `review.json`. `field-plan.json` records the prospective gates and all frozen input pins; `field-report.json`, `field-products.jsonl`, `field-comparison.csv` and `field-execution.json` retain results and execution accounting.

A separate saved-data audit passes 711 checks without additional field products.

[Field results](isae-ae2-sensor-reference.json) ·
[CSV](isae-ae2-sensor-reference.csv) ·
[Saved-data audit](isae-ae2-sensor-reference-audit.json) ·
[Raw evidence including original source paths](isae-sa3-reference-20261025-evidence.zip)
