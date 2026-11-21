# Current ISAE regression suite

Priority: compare **every ISAE family with archived ASWING output**. Experimental agreement is not required. The full suite is not yet reproduced.

This run accounts for **41 families** and finishes **16/16 registered jobs**. A job is a declared curve, polar row, static snapshot or unsupported comparison; it is not a family pass.

| Family | Original models | Output candidates | Jobs computed / planned | Matching jobs | Current result |
|---|---:|---:|---:|---:|---|
| SA-1 | 1 | 7 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-10 | 6 | 17 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-11 | 5 | 38 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-12 | 2 | 18 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-13 | 0 | 4 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-14 | 4 | 41 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-15 | 7 | 78 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-2 | 1 | 6 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-3 | 1 | 6 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-4 | 1 | 8 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-5 | 1 | 4 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-6 | 7 | 59 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-7 | 2 | 15 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| SA-8 | 2 | 7 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| UA-1 | 0 | 36 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| UA-2 | 0 | 33 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AP-1 | 2 | 17 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AP-2 | 2 | 16 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-1 | 0 | 3 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-2 | 0 | 8 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-3 | 0 | 3 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-4 | 0 | 4 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| P-5 | 0 | 4 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-1 | 10 | 61 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-2 | 6 | 112 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-3 | 9 | 74 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-4 | 33 | 24 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-5 | 38 | 124 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| ST-6 | 0 | 18 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-1 | 1 | 61 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-2 | 5 | 76 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-3 | 6 | 28 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-4 | 5 | 238 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-5 | 2 | 81 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-6 | 33 | 30 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| AE-7 | 6 | 115 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-1 | 5 | 70 | 5 / 16 | 0 | NUMERICAL_OR_INPUT_FAILURES |
| FFWT-2 | 53 | 76 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-3 | 6 | 32 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-4 | 9 | 59 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |
| FFWT-5 | 7 | 17 | 0 / 0 | 0 | NO_CURRENT_COMPARISON_ADAPTER |

Output candidates are identified archive artifacts, not automatically proven model/output pairs. Missing adapters remain visible work. The catalog separately records every original model's hash and import result, the supplemental model outside case folders, and absent SA-9.

Each registered adapter declares its original inputs, complete target rows and required outputs. Failures and timeouts remain in the denominator. Other variants and all unregistered families still need reviewed, executable archived-output comparisons.

Run `npm run test:isae -- --output-dir PATH` for a fresh complete registered batch. Add `--plan-only` to inspect all inputs/jobs; `--resume` reuses only completed jobs from the identical pinned plan. Each job has an independent timeout, and the runner continues after a failed comparison.
