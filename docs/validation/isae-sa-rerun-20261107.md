# Fresh steady-aerodynamic comparison at 5%

The broader rerun is deferred after the user selected **SA-6** as the priority.
See the [SA-6 follow-up](isae-sa6-focus-20261107.md). The complete plan has **2,883 serial jobs**, one BLAS
thread per job and a 60-second worker timeout. The first 372 jobs used a
512 MiB address-space limit; the remaining jobs use 768 MiB because the
largest SA-10 mesh also exceeded 512 MiB with ordinary Python startup.
SA-9 is absent upstream. All original meshes, archived values, numerical
validity checks and near-zero absolute rules are retained.

The first five families are complete: **184 jobs, 178 computed and six solver
failures**. An independent summary verifies **1,206/1,288** native comparisons
passing in these families. All code hashes remained unchanged. The next 188 jobs complete SA-7 and SA-8
with no new numerical failures: **372 jobs, 366 computed and six failures**
in total. Independent auditing verifies **2,034/2,604** matches in the seven
completed families. The other seven families remain required.
These are fresh physical calculations, not just a rescore of saved predictions.

| Family | Finished jobs / required | Native matches at 5% | Remaining issue |
| --- | ---: | --- | --- |
| SA-1 | 22/22 | **154/154 pass** | Historical setup and continuum accuracy remain qualified. |
| SA-2 | 10/10 | **50/70 pass** | Drag/CD errors 5.23–10.79%; median failed CD error 9.25%. |
| SA-3 | 44/44 | **308/308 pass** | Historical setup and continuum accuracy remain qualified. |
| SA-4 | 84/84 | **528/588 pass** | Six circulation failures leave 42 values unavailable; 18 computed comparisons fail. |
| SA-5 | 24/24 | **166/168 pass** | Coarse-mesh drag/CD at the last incidence are 5.27% low; all fine-mesh values pass. |
| SA-6 | Separate complete follow-up | **470/528 pass** | [Default adoption](isae-sa6-focus-20261107.md): all 88 registered states rerun with frozen influences and strength 40; three unpaired models retained. Former current-wake 346/528 stays separate. |
| SA-7 | 116/116 | **406/812 pass** | Full aircraft 406/406; mismatched current fore-only model 0/406. |
| SA-8 | 72/72 | **422/504 pass** | Full 228/252; fore-only 194/252. Failed fore-only CD median 12.69%, range 6.03–15.26%. |
| SA-10 | 85/324 | Partial; not promoted | 84 computed, one timeout; 54/54 Louvered jobs give 277/378 matches. |
| SA-11 | 0/656 | Pending | — |
| SA-12 | 0/1,020 | Pending | — |
| SA-13 | 0/8 | Pending | Original source-pairing blockers remain in the plan. |
| SA-14 | 0/360 | Pending | — |
| SA-15 | 0/52 | Pending | Historical and declared-setup scopes remain separate. |

Counts are scalar outputs, including repeats on two meshes. SA-15's 52 jobs
include 26 historical blocked jobs and 26 declared-setup jobs; the two scopes
must not be added as independent native targets. The status dashboard tracks
the declared setup as before. Passing a selected scope is not whole-family
physical validation.

SA-1, SA-2, SA-3 and SA-4 retain their existing pass counts. SA-2's ten solves
pass all numerical checks, but drag and CD miss the archive on every tested
row/mesh. SA-4 reproduces its earlier six unresolved-circulation failures;
there are no timeouts. Its separate drag table passes all 294 comparisons.
SA-5 increases from 158/168 at 3% to 166/168 at 5%; this is an allowance change,
not a solver improvement. Its two remaining coarse-mesh errors are 5.2736%.
SA-7 and SA-8 gain 11 and 49 accepted comparisons respectively. Rescoring
the fresh predictions at 3% reproduces their earlier 395/812 and 373/504
counts, so these gains also come from the allowance. SA-7 fore-only errors
are dominated by the known source mismatch; they are not evidence for tuning
the complete-aircraft solver. No physics or settings change has been made
during this baseline rerun.

After completion, rank primary scopes by pass fraction while retaining
numerical failures in their denominators. List fully source-blocked scopes
separately, then investigate the worst executable family. Relative errors
for near-zero outputs are not a useful physical severity ranking; preserve
their absolute discrepancies and original acceptance rules.

- [Complete frozen plan](../../artifacts/isae/sa-rerun-20261107/plan.json)
- [First 100-job report](../../artifacts/isae/sa-rerun-20261107/batch-0100/report.md)
- [First batch execution receipt](../../artifacts/isae/sa-rerun-20261107/batch-0100/execution.json)
- [Completed SA-1–SA-5 batch](../../artifacts/isae/sa-rerun-20261107/batch-0184/report.md)
- [Independent SA-1–SA-5 summary](../../artifacts/isae/sa-rerun-20261107/batch-0184/analysis/summary.md)
- [Completed SA-7/SA-8 batch](../../artifacts/isae/sa-rerun-20261107/batch-0372/report.md)
- [Independent seven-family summary](../../artifacts/isae/sa-rerun-20261107/batch-0372/analysis/summary.md)
- [Failed fine-grid error percentages](../../artifacts/isae/sa-rerun-20261107/batch-0372/analysis/failed-error-percentages.json)
- [Latest runner report](../../artifacts/isae/sa-rerun-20261107/report.md)

The runner deliberately exits 1 while comparisons remain open. Individual
worker exit codes and numerical outcomes are retained independently. Fresh
complete family rows replace the historical rows in `ISAE_STATUS.md`; pending
families retain their previous counts and explicitly labeled thresholds.

The [runner study](isae-sa-import-reuse-20261107.md) retains a direct-fork
speedup, its later resource failure, ordinary-launch controls, and an isolated
import-server comparison. The latter passes accuracy but misses its speed
gate, so the accepted rerun continues with **ordinary worker launches**.
Streamed atomic report writing avoids duplicate full-report strings; all
19 process/report regression tests pass. The interrupted 69-job attempt is
retained separately and is being rerun as a whole, without selecting
predictions by agreement. Benchmark repeats add no native passes.

On 2026-11-07, the user redirected work to SA-6. The active SA-10 worker
was stopped with SIGINT; its supervisor exited 130 and no worker remained.
The [stop receipt](../../artifacts/isae/sa-rerun-20261107/stopped-for-sa6-at-0457/receipt.json)
retains 457 completed outcomes and the incomplete job directory. Seven family
rows remain complete; partial SA-10 results do not replace its primary count.
