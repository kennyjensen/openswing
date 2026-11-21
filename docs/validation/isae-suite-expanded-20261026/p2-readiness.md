# P-2 source readiness

Historical audit retained below. The [2026-11-05 input recovery](../isae-p2-recovery-20261105.md)
now identifies all primary CP rows and establishes a declared measurement-based
CdA reconstruction; 312/312 archived comparisons pass at 5%. The exact historical
fit and driver remain unavailable.

No complete original-input component route is established from the cached sources. The eight FIG files contain four CT/eta pairs (2/4 blades, 2000/4000 RPM), with 8/18/8/18 coordinates. After removing duplicate graphics in the 2B/2000 pair, there are **312 candidate model scalars across 24 curves**, plus 104 separate experimental values.

The report calls P-2 data-only (cached text lines 790–796), supplies nominal 9-inch geometry and measured CP as the driving input (857–869), and attributes the CT/eta curves to ASWING (1013–1019). It explains that the polynomial CdA curves are calibrated from experimental data (909–938). The FIG axes confirm J=V/(nD); the eta legends identify Exp and three CdA alternatives. CT series themselves are unlabeled.

For all 48 nonzero-J coordinates, the experimental CT/eta pair permits **derived CP=J*CT/eta**, independently of model predictions. Every corresponding model pair implies the same CP within floating arithmetic. The four J=0 CP values cannot be recovered this way. This is a useful source-recovery lead, not a replacement for original table provenance.

The precise blockers are the original CP rows (especially J=0), exact quadratic CdA coefficients and constant endpoint CdA values, and recorded CT-to-eta curve attribution. Legends print only two significant digits for the coefficients. No P2 MATLAB driver or model is retained. Existing cached P1 static CP tables have no established identity to these advance-flow runs. Opaque MCOS figure payloads were not exhaustively decoded.

The existing actuator_disk API supports forward flow and windmilling (openswing/propulsion.py:34–68), so this audit demonstrates no new missing kernel. P1 evaluate is hover-only (scripts/verify-isae-p1.py:29–38). A future dedicated worker can supply V=J*n*D and evaluate eta=T*V/P once inputs are pinned. First recover the four primary CP tables and exact CdA inputs; begin with one constant-CdA curve at nonzero J. Do not infer CdA from the model CT targets or treat calibrated polynomial agreement as an independent experiment pass.

All eight FIG and eight extracted-JSON hashes verify against the existing inventory. Source pins, curve locations, derived CP values and line references are in report.json. No production imports, physics calls, upstream-script runs, or repository edits occurred.
