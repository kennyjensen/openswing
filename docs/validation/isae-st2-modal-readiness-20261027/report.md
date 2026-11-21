# ST-2 modal readiness, 2026-10-27

The two original modal models are candidates for **unchanged-file source modal execution**. Their old attachment blocker is obsolete: both out-of-domain Weight rows have exactly zero physical coefficients. Current null-object handling preserves the original records while omitting their identically zero loads and inertia. Both sensor triads are already valid; the recent partial-sensor change is not needed for ST-2. This review ran no production imports, parses, meshes, residuals or solves.

The [machine report](report.json) pins all **66 files in the two modal trees**, verifies their archive-manifest hashes, and retains **14 complex roots / 28 required native scalar components**. There are no modal shell/MATLAB drivers, saved operating states or native eigenvectors in those trees. Ten ASWING-labelled workbook frequencies remain separate, qualified summaries. GFEM/UM-NAST files and experimental data are not native acceptance targets.

| Recoverable fact | Exact source |
|---|---|
| Vertical “undeformed” and horizontal “deformed on its own weight”; forty structural nodes | Structure report §4.2, PDF p34, cached text lines3061–3077 |
| Upright span is +z; horizontal span is +y; clamp t=.0001; property break .52; tip .55 | Each original Pazy_wing.asw lines38,44–49 |
| Two valid sensor triads at .55; two null Weight rows at .558 | Each model lines18–19,24–28 |
| g=9.81, rho_SL=1.23; full original mass/rotary inertia, coupling and −.005m section offsets | Each model lines14,45–54 |
| Seven original complex roots, operating point1, with all tiny nonzero real components retained | Each Pazy_wing.e00 lines4–10 |
| MODE uses a prior OPER state, otherwise unloaded zero-lift geometry; count and shift select the spectrum | ASWING guide lines3508–3552 |

“Undeformed” does **not** establish gravity off. In the vertical model gravity primarily compresses the span, whereas the horizontal model bends under its own weight. A prospective comparison can use literal g=9.81 and explicit body gravity [0,0,−9.81], zero attitude/rates/accelerations and a stationary loaded equilibrium for both. Exact historical OPER/pose/override settings remain unrecorded. Do not force the horizontal jig geometry or silently disable upright gravity.

`drela-fixed-vacuum-v1` supports these literal model fields, including general-section offsets/coupling, the .52 stiffness jump, nonnegative mass/rotary inertia and zero default damping. The source Euler chart admits both y- and z-aligned spans; its excluded orientation is x-aligned. `drela-fixed-still-air-v1` also applies with explicit positive density and adds only stationary thin-strip apparent inertia. The original medium is not recovered: either declare vacuum as a conditional baseline or predeclare both vacuum and rho=1.23 still-air branches. Never choose the medium by which agrees better. A moving-vacuum stationary subcase is possible, but no source evidence warrants extra free/mixed frame states or nonzero motion.

A concrete next plan is two unchanged models at prospective **40/80 cosine intervals**, retaining .52 exactly: expected41/81 actual intervals and42/82 nodes. These counts are a source-reading prediction, not a mesh execution, and are not the historical “40 nodes.” Four vacuum jobs require56 scalar slots; adding the separately declared still-air branch gives eight jobs/112 slots, always only14 distinct native complex roots. Meshes and medium must be fixed before observing results.

Each worker should retain the literal source, parsed null records, cold loaded base, fresh restored residual, force/moment balances, full A/M descriptor, all computed roots and left/right original-pencil backward errors. Require all28 original real/imaginary print-precision targets, without real-part zero-snapping or conversion to frequency-only acceptance. Declare root selection before comparison and report missing/extra roots and branch ambiguities. Workbook mode-label conflicts cannot resolve native branch identity.

Remaining qualifications are precise: absent driver/base transcript, medium and actual density, exact node coordinates/settings, MODE count/shift, native eigenvectors/branch labels, and historical build/startup/discretization. They qualify a current conditional execution; they do not justify retaining the obsolete null-attachment error. Active static bench anchors remain invalid, and workbook producer pairing remains unresolved.

The older modal study deleted null rows and used the default midpoint/natural-model path with selected frequency/shape comparisons (`scripts/isae_st2.py:67–78`, `verify-isae-st2-modes.py`). Its saved results remain historical evidence and do not establish literal source-operator replay. No existing adapter, registry, report or archived evidence was changed here.
