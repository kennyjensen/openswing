# SA-15: first complete declared forward-wing polar

Follow-up: the [shared-runner registration and drag breakdown](isae-sa15-suite-20261105.md)
reproduce all 26 cases, retain the 84/182 result, and resolve the registration
item listed below. The historical setup and remaining output differences stay open.

**84/182 conditional scalar comparisons pass at 5%.** All 26 cold solves (13 archived angles × 64/128 nominal intervals) converge and pass 286 force, moment, source and normalization checks. These are new current-source results. No whole-family validation or exact reproduction of the historical startup is claimed.

The unchanged original `JW-1_FW_Only_Body.asw`, original shell angles at full precision, original 380 ft/s speed and all seven original output columns are retained. The density is the literal sea-level value. Declared choices are Drela spline interpolation, default cosine nodes, pointwise circulation, Mach zero, zero controls, current influences and existing stall/core defaults. The file itself says its section properties include Mach 0.35 effects. No property or tolerance was fitted.

The old adapter blocked all outputs pending force-axis review and `.set` decoding. This probe explicitly reconstructs the full force and moment from distributed loads, uses conventional stability axes and moments about the declared Reference, and tests the normalization independently. The exact historical OPER coefficient selector and startup remain unverified; this declared scope does not silently replace the blocked native registration.

| Output | Passes across both meshes | Median error, all non-tiny values | Maximum error |
|---|---:|---:|---:|
| CD | 10/26 | 7.033% | 16.63% |
| CY | 0/26 | Near-zero values; percentage is misleading | 2.61e-08 absolute |
| CL | 24/26 | 1.607% | 8.813% |
| Cl | 0/26 | Near-zero values; percentage is misleading | 6.96e-08 absolute |
| Cm | 26/26 | 1.075% | 1.7% |
| Cn | 0/26 | Near-zero values; percentage is misleading | 1.37e-08 absolute |
| efficiency | 24/26 | 0.3542% | 13.4% |

The 78 lateral-force/roll/yaw comparisons fail against small archived residuals (roughly 1e-10–1e-7); the symmetric zero-control model produces values essentially at roundoff. These are retained failures. No zero floor was changed to manufacture matches.

Fine-grid drag is 7.06% low at 0.227° and 16.63% high at 12.338°. The median/max 64→128 drag change is 0.559%/0.832%, substantially smaller than the discrepancy. At the highest angle most drag is profile drag; at moderate incidence induced-force drag matters. Substituting Trefftz drag plus profile drag makes these two comparisons worse (9.35% and 26.04% high), so that substitution is not adopted.

A separate documented F-toggle diagnostic at three predetermined angles keeps the same 128-node request and properties. Freezing influences changes the drag errors at 0.227°, 5.350° and 12.338° from 7.06%, 7.02%, 16.63% to 7.07%, 8.28%, 1.94%. It helps the high-angle point but does not resolve the moderate-angle discrepancy. The default and original 26-case scope remain unchanged.

Drela’s cached FAQ (`.reference/aswing_faq.txt`, lines 387–402) identifies `.set` as an undocumented memory-block dump whose layout depends on version and compile-time array sizes. All original bytes are pinned, but the numeric fields and flags have not been assigned guessed meanings.

Reproduce a small serial anchor with `.venv/bin/python scripts/verify-isae-sa15-anchor.py NEW_FOLDER --row 4 --panels 128`; add `--frozen-influences` only for the separately declared diagnostic. Original reference cache is required. [Machine results](isae-sa15-declared-setup-20261105.json) retain every comparison and source pin. Remaining work: historical settings/output identity, drag physics/setup, near-zero reference acceptance and shared-runner registration.
