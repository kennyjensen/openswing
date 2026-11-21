# ST-1 cross-ply modal comparison

**Follow-up:** the [thin-blade study](isae-st1-thin-modal-20261109.md) adds nine
further modal matches; current modal coverage is **20/22**. The cross-ply
increment below retains its original results and acceptance history.

All four published cross-ply frequencies match within **1.10%** on both
meshes. This raises the primary modal comparison from **7/22 to 11/22**.
Static comparisons remain **201/201**, giving **212/223** primary matches.
The original **9/200 archive inventory** remains unchanged.

These four matches use the explicitly documented physical-property
reconstruction from the [material-source review](isae-st1-material-source-review-20261109.md).
They establish agreement with the report's mechanical specimen; they do not
establish that the altered archived input generated the report's results.

| Mode | ASWING, Hz | OpenSwing, N40 | OpenSwing, N80 | Fine-grid error | Mesh change |
|---|---:|---:|---:|---:|---:|
| 1B | 5.74 | 5.743114 | 5.742619 | 0.0456% | 0.0086% |
| 2B | 36 | 36.073505 | 35.997677 | 0.0065% | 0.211% |
| 3B | 101 | 101.485092 | 100.894369 | 0.105% | 0.585% |
| 1T | 78 | 78.863887 | 78.854801 | 1.096% | 0.0115% |

Targets are unchanged ASW rows from ISAE Part III Table 3, p. 35. No
experimental value, mesh repeat, or alternative material setting adds to
the denominator. The fifth low-frequency positive mode is in-plane bending
near 115.44 Hz, outside this layout's four named table targets.

## Setup and numerical evidence

The original raw properties are retained. The derived scale row restores
GKn=290,000 N, converts the stated chord-axis mass inertia to weight inertia,
and removes an extra unnamed scale. An `End` terminates the empty Engine
block. Mass per length remains 0.0683 kg/m, consistent with the original file
and Minguet's thesis. Other report/property conflicts remain explicit in the
source review. No material parameter was selected from a frequency match.

The physical setup is the clamped blade under its own weight, zero tip mass
and zero root twist, followed by fixed-frame vacuum linearization. The
nominal 40/80 cosine meshes have 41/81 nodes. Bending modes have zero, one
and two internal normal-displacement zeros; the torsional mode has no internal
twist zero. Classification uses the same predeclared shape rule as the
[earlier modal study](isae-st1-modal-mechanics-20261109.md).

All four coarse/fine shape correlations exceed **0.9999938**. An independent
replay of the saved sparse A/M matrices verifies 48 left/right eigen-equations,
with maximum action-relative residual **7.44×10⁻¹⁴**. Both nonlinear base
states converge and have tip sag 11.6465 mm. That sag is a diagnostic, not an
additional accepted table entry; Table 3's printed deflection units have a
separate ambiguity.

Solves took **2.44 s** and **3.55 s** after imports, using one BLAS thread,
512 MiB address-space, 15 s CPU and 25 s wall limits. Peak RSS was about
107/254 MiB. All 141 production modules are unchanged.

The previous attempt's exit 142 is preserved. A fresh import-only check
completed in 3.05 s; the retry used identical input bytes, solver settings
and resource limits in a new output directory. The original timeout's exact
startup cause remains unknown, and it was not a measured modal solve timeout.

## Acceptance record

The execution plan deliberately left promotion to a separate review. The
[acceptance record](../../artifacts/isae/st1-cross-modal-reconstruction-20261109/retry/acceptance.json)
accepts these four existing targets after checking source justification,
both meshes, mode identity and matrix residuals. It preserves the original
targets and archive denominator. Ten thin-blade targets remain pending, and
the coupled blade's 95 Hz mode-label correspondence remains unresolved.

[Runner](../../scripts/verify_st1_cross_modal.py) ·
[plan](../../artifacts/isae/st1-cross-modal-reconstruction-20261109/retry/plan.json) ·
[summary](../../artifacts/isae/st1-cross-modal-reconstruction-20261109/retry/summary.json) ·
[startup check](../../artifacts/isae/st1-cross-modal-reconstruction-20261109/startup-check.json).
