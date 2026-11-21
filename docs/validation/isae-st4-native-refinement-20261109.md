# ST-4 direct native exports: refinement complete

All **31/31 archived ASWING frequency ordinals pass** the 5% reference allowance,
0.1% refinement gate and shape correspondence checks on nominal 128/192 cosine
meshes. The five original files and their directly associated `vaccum.txt`
exports remain unchanged. This includes the seventh 7d root.

| Original model | Passing frequencies | Maximum ASWING error | Maximum mesh change | Maximum continuous-reference error |
|---|---:|---:|---:|---:|
| 7a, 17 inches | 6/6 | 0.37485% | 0.03224% | 0.02579% |
| 7c, 21 inches | 6/6 | 0.41730% | 0.03576% | 0.02844% |
| 7d, 48 inches | 7/7 | 0.81275% | 0.06841% | 0.05472% |
| 7e, 48 inches | 6/6 | 0.41995% | 0.03498% | 0.02798% |
| 7f, 48 inches | 6/6 | 0.41990% | 0.03471% | 0.02776% |

The earlier 64/128 comparison remains **20/31**: eleven higher-frequency
comparisons failed its refinement gate despite small ASWING errors. Those
old results are preserved. Five fresh 192-interval states reuse the five
verified 128-interval states; no selection of a better mesh or reference
ordinal is allowed.

## Independent accuracy checks

The refined comparison adds a **0.1% continuous-reference gate** for every
frequency. The independent six-state Rayleigh-beam specialization of Drela's
structural equations includes the original elastic-axis/CG offset, distributed
rotary inertia and full point-mass rigid arms. It propagates each uniform beam
segment continuously, with exact concentrated-mass jumps. No production
matrix assembly is used for those roots. Every root retains its bracket and
boundary singular-value check. Maximum frequency discrepancy is **0.05472%**.

The independent discrete version, including Drela's interval rotary-inertia
correction, reproduces all 31 fine-grid frequencies within **4.80e−12 relative**.
An independent parser verifies the original two-row beam tables, scales and
point weights before either reference calculation. No model property was fitted.

Re-reading both full saved matrix pencils and both eigenvectors verifies
**320 eigen-equations**, with maximum action-relative residual **1.53e−11**.
All returned positive-frequency shapes participate in the coarse/fine matching;
the 16-root complex-shift search is not necessarily sign-symmetric. Minimum
compared shape MAC is **0.99999949**, and every match is mutual. The initial
unexecuted audit declaration assumed eight positive roots; the corrected
declaration retains all returned candidates, including the pilot's ninth.
Both declarations are preserved.

The original 16-root request, shift `−0.1 + 300i`, fixed-frame vacuum, zero
gravity, interpolation, point locations and equations remain unchanged. Only
mesh resolution changes between the paired requests. Native eigenvectors and
the exact historical startup state remain unavailable. These are original-order
frequency comparisons and numerically consistent shapes, not authenticated
native mode identities or a proof of the complete spectrum.

## Resource stop and lossless evidence writing

The first 256-interval pilot terminated with **SIGKILL** after dispatch returned,
while writing its result JSON. Its 20,925,824-byte partial file is not valid
JSON, and the run never reached its final validation report. The exact kill
reason was not captured. The original 512 MiB address-space, 15 CPU-second and
25 wall-second caps were in force; they were not raised. The failed attempt
and all partial artifacts remain intact and contribute no pass.

A validation-only wrapper now saves the complete result using compact standard
JSON. It changes whitespace and the encoding path, preserving every field and
numeric value. A replay of a complete 128-interval result verifies all **547,583
scalar leaves**, including exact floating-point values and signed zero. The
original pretty encoding is byte-identical to the saved source result.

| Single saved-result measurement | Original pretty JSON | Compact JSON |
|---|---:|---:|
| Size | 25,298,969 bytes | 10,233,074 bytes |
| Write wall time | 0.716 s | 0.227 s |
| Write CPU time | 0.710 s | 0.225 s |

These are individual I/O measurements, not a numerical-solver speed estimate.
The 256 state has not been rerun successfully. The completed 192 states use
the same resource caps and additionally require the independent continuous
accuracy check above. Their complete supervised times are 13.80–15.80 seconds,
maximum child CPU time is 11.90 seconds, and peak RSS is 204,292 KiB. All five
new states and all later checks ran serially with one BLAS thread.

All 141 production modules, original inputs and physical settings retain their
planned hashes. The original numerical runner is unchanged; the wrapper replaces
only its `result.json` writer. No browser/build work was run.

## Relationship to the main status

This supplementary scope overlaps the [72-frequency paper comparison](isae-st4-mechanics-current-20261109.md)
and the older **93/3,749 archive**. It adds **no primary votes**. The primary
paper score remains **66/72**, and the original named-mode rule remains **54/72**.
All six paper failures, 3,656 unavailable archive outputs, historical airflow
issues and input/label qualifications remain required or explicitly open in
their own scopes.

The original `Effect_on_modal_response.m` explicitly describes its plotted data
as illustrative and points readers to `Eigen_data_save.csv` for rigorous
experimental comparison. Its hard-coded 7d position/frequency combination repeats
the paper's discrepancy. This helps trace the source conflict; it does not justify
discarding a paper target or silently replacing it with another configuration.

The directly paired structural exports now support the mechanics strongly.
Remaining ST-4 work includes the four paper/source correspondences, authenticated
mode identities/settings, airflow/flutter discrepancies and recurring-suite
integration. No whole-family validation is claimed.

Evidence: [refinement plan](../../artifacts/isae/st4-native-refinement-20261109/n192/plan.json),
[all 31 results](../../artifacts/isae/st4-native-refinement-20261109/n192/summary.json),
[saved-matrix/reference verifier](../../artifacts/isae/st4-native-refinement-20261109/verify_saved.py),
[corrected audit declaration](../../artifacts/isae/st4-native-refinement-20261109/n192/audit-plan-v2.json),
[failed 256 receipt](../../artifacts/isae/st4-native-refinement-20261109/execution-00.json),
[complete JSON equivalence/timing check](../../artifacts/isae/st4-native-refinement-20261109/json-io-benchmark/report.json),
[serialization wrapper](../../artifacts/isae/st4-native-refinement-20261109/compact_worker.py).
The [authoritative source catalog](aswing-authoritative-sources.json) and original
model/driver/export hashes remain verified by the plan.
