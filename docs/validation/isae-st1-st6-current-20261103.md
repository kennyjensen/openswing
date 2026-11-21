# Current ST-1 through ST-6 test results

This report retains the initial registered comparison. The later [ST-5 refinement study](isae-st5-mesh-extension-20261103.md) resolves its four mesh-convergence failures on finer grids and adds one browser check, without changing the strict baseline score or establishing archived-ASWING agreement.

The requested structural rerun follows the [UA-2 assessment](isae-ua2-current-assessment-20261103.md).
All **101 registered jobs** have terminal records. This does not establish full-family validation.
A job may be a numerical case or an explicit unsupported record; pass counts below refer to individual archived scalar comparisons.
These structural comparisons run in CPython. UA-2 browser verification is reported separately; identical delivered solver files do not constitute ST-specific browser validation.
Original accuracy and physical-validity gates are unchanged. Jobs run serially with one BLAS thread. Original 45-second attempts are retained; selected timeout retries use a 180-second cap on the identical numerical problem.
Timeouts are resource-limited attempts without an accuracy verdict; unsupported comparisons remain in the denominator.

| Test | Strict scalar matches | Execution | Typical error in computed values |
|---|---:|---|---|
| ST-1 | 2/200 | 35 unsupported, 2 computed | X: 0.003148% median; Y: 0.0009601% median; Z: 0.007086% median. |
| ST-2 | 0/490 | 8 computed, 9 unsupported | Frequency median 0.2018%; maximum 1.228%. |
| ST-3 | 930/1,080 | 1 computed | Z: 0.1072% median; twist: 0.1228% median; bending moment: 0.1578% median. |
| ST-4 | 0/3,749 | 37 unsupported, 5 computed; 5 mesh checks fail | 64-panel frequency median 0.07515%, maximum 0.5673%; coarse maximum 4.127%. |
| ST-5 | 13,833/25,920 | 4 computed; 4 mesh checks fail | Z: 0.139% median; twist: 0.1704% median; bending moment: 0.3592% median. |
| ST-6 | No native target | 19 original files rechecked; no numerical comparison | Not applicable. |

Percentages use nonzero reference values with magnitude greater than 1e-8; near-zero fields retain their strict absolute comparison.
The table covers the registered scopes, not every unpaired plot or original variant. Full output accounting is in the machine report.

ST-1 retains 194 unavailable scalar comparisons and the unresolved grammar/modal setup of the other original models.
ST-2 now registers 490 slots, including the eight modal jobs; the older completed 406-slot batch and interrupted five-job modal study remain historical evidence. Invalid static attachments and unpaired workbook cells remain unavailable.
ST-3 covers one static snapshot on three meshes; its mesh checks pass. ST-4 covers five runnable vacuum variants plus unsupported airflow/model/aggregate records. ST-5 covers four rigid-joint snapshots on three meshes each; all four fine-mesh checks fail. Reaction display and other original configurations remain unresolved.
The largest relative moment differences occur at small reference values: ST-3 has 13.48% error at -8.52e-5 N m (absolute error 1.149e-5 N m); ST-5 has 140.17% at 5e-5 N m (absolute error 7.009e-5 N m). They remain strict failures. Unless a mesh is named, median percentages cover all computed nonzero values across the declared meshes, so they differ from earlier single-mesh summaries.
ST-6 contains analytical Euler curves and experimental measurements, without an attributable ASWING model/driver/output. Its analytical data are not counted as native validation.

The initial full-inventory planning attempt hit its 45-second cap before any numerical job. The smaller runner reuses the existing suite planners, upstream source verification, worker and strict result accounting; no physical comparison was changed.
ST-2 completes the identical eight modal requests under the longer cap. ST-4 reuses its five verified 16-panel outputs and finishes ten 32/64-panel requests in separate serial children, using the original numerical and mesh verifiers. The prepared whole-case ST-4 180-second retry plan was not executed. No completed coarse solve was repeated for this recovery.

[Machine report](isae-st1-st6-current-20261103.json). Requests, results, source hashes and any incomplete artifacts are retained under `artifacts/isae/st1-st6-current-20261103/`.
