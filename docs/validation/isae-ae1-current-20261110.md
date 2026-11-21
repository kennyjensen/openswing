# AE-1 current-code restart: Pazy steady deflection

Observed 2026-11-10T03:03:39.961694+00:00. Focus moved from ST-5 to AE-1 at the user's request.

All **72 computed sensor comparisons pass at 5%**, across six operating points on nominal meshes 40/80. The selected scope is **72/96**, retaining 24 unavailable outputs from two unknown startup states on both meshes. These mesh repeats represent 36 distinct computed native cells. The complete registered family still requires 1,200 comparisons: 1,104 positive-state outputs have not been rerun in this refresh. Whole-family validation is not claimed.

| Root incidence | Commanded IAS / assigned TAS (m/s) | Passing outputs on both meshes | Maximum absolute relative error |
|---|---:|---:|---:|
| 5° | 1 | 12/12 | 0.153531% |
| 5° | 28 | 12/12 | 0.330423% |
| 5° | 56 | 12/12 | 0.274786% |
| 7° | 1 | 12/12 | 0.144305% |
| 7° | 21 | 12/12 | 0.368507% |
| 7° | 42 | 12/12 | 0.181309% |

Median absolute relative error is 0.047639%. All 348 physical checks pass. Maximum relative change between the two meshes is 0.033971%; this is a sensitivity result, not a new acceptance gate. The unchanged printed-precision comparisons give 9/96 strict matches. No AE-1 production equation or fitted property changed.

## Setup and authoritative sources

Reviewed [Jan Part IV, section 3.1, pages 8–9 and Figure 1](../../reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf), its [checksummed catalog entry](../../reference/aswing-authoritative-20261108/isae-part-4.json), the original Pazy model, both shell drivers, and `Static_Aeroelastic.m`. The report defines tip deflection and twist at root incidences 5° and 7°. The MATLAB plot subtracts the first archived Z value for displacement; this comparison instead retains all six original absolute sensor channels, matching the existing literal-input adapter. Experimental and UM/NAST curves are not acceptance targets.

The literal model and both inactive zero-weight records remain unchanged. Settings remain the reviewed mounted reconstruction: density 1.23 kg/m³, PG Mach zero, body gravity [0,0,−9.81], wall image normal [0,1,0], frozen influence matrices, and the source coupled structural operator. The 0.52 m property break is retained. Each positive-state job starts cold and independently restores the final state for one fresh residual and sensor/load audit.

The [original manual](../../reference/aswing_doc.txt), “Fast,Slow Vortex-Lattice Model”, documents fixed jig-geometry influence matrices at zero wind angles. This is also the current OpenSwing default, following the user’s earlier direction. Structural geometry, circulation and loads still solve. Neither original shell driver explicitly selects K/F; the missing historical `.set` file and node arrays remain unresolved. Matching under frozen influences does not prove the original setting.

The historical updated-influence baseline remains **98/1,200 strict matches**, separate from this conditional scope. The earlier [24/48 endpoint comparison](isae-ae1-frozen-scope-20261105.md) is superseded only as the selected frozen pilot by 72/96; it is not added. The older full 60/120 sweep used removed zero-weight records and baseline-subtracted displacement, so it is not silently substituted for the current literal-input absolute-channel replay.

## Execution and remaining work

Twelve serial physical jobs completed in 5.94–9.04 seconds each, including source checks, a cold solve and a fresh residual. Peak reported RSS was 97.3 MiB. Each process used one BLAS thread and limits of 512 MiB address space, 15 CPU seconds and 25 wall seconds. Four unknown-start records required no solve. No job timed out or remained running.

A saved-data audit rechecked source/kernel/artifact hashes, the shared adapter contracts, all physical checks, raw sensor values and mesh pairs without importing production modules. The first two worker receipts lacked common-runner aggregate accounting in their policy views; the saved strict results were intact. The final audit applies the common contract to every record, preserves those earlier files and performs no physical rerun.

Next: replay the remaining 92 positive speed coordinates at both meshes in small serial batches, then report the full default-frozen scope separately from the historical updated-influence baseline. Keep both unknown starts required. Check errors near the gravity-to-lift crossover before changing any model equations. Browser/build execution remains held; this batch makes no browser performance claim.

ST-5 remains deferred with its last accepted mechanics score unchanged. Its unfinished gravity-reporting feature and verification limits are recorded [here](isae-st5-static-gravity-pending-20261110.md).

Evidence: [plan](../../artifacts/isae/ae1-current-20261110/plan.json), [low/mid-speed plan](../../artifacts/isae/ae1-current-20261110/interior-plan.json), [full saved-data audit and values](../../artifacts/isae/ae1-current-20261110/summary.json). Reproduction helpers: `scripts/replay_isae_ae1_bounded.py` (one predeclared job), `scripts/summarize_isae_ae1_current.py` (saved evidence only).
