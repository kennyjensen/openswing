# ST-5: four original roller-joint cases

All four archived **Link_Joint** load snapshots now have completed comparisons on three nested grids: **12 cold solves and 12 fresh restored residual checks pass**. This expands original ASWING coverage beyond the four previously tested rigid-joint snapshots. No original input, physical equation, load, material property or archived-output tolerance changed.

The most useful finding is that the archive's printed-node grids reproduce the archived response much more closely than the refined grids. Median twist differences on those initial grids are **0.00012–0.00062%**, compared with **0.38–0.60%** on the finest tested grids. This supports a substantial historical discretization contribution to the discrepancy; it does not prove the exact historical mesh or executable. Matching an archived finite-grid solution and demonstrating continuum convergence are separate questions.

The unchanged files specify **KJtype=2**. The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt), Joint section, defines this as rotation matched with translation free: a roller joint. The directory name is not used to substitute a pinned joint. The four models have the same numerical inputs as their rigid-joint counterparts except for this joint type; whitespace/comments are ignored only for that source comparison. The models themselves are never rewritten.

The originals are pinned at [ISAE revision f62943d](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865/3%20-%20Structure/CASE%20-%20ST5%20Joined%20Wing/Link_Joint). Each retained script identifies its own input/output and performs one static solve. All 320 source-decoding checks pass, including root force/moment balance, rear root geometry, shell strain/stress rounding intervals and no-flow/zero-motion metadata. Per-file exponents are read afresh; the case-specific selective exporter interpretation remains qualified because the original exporter source is unavailable.

Each grid retains all **80 rows and 27 outputs**, including duplicate traces and exact known attachment coordinates. Intervals per forward/rear beam are **38/32, 76/64 and 152/128**. Interior printed centers are prospective mesh coordinates, not fitted or recovered unrounded historical nodes. The printed 2.000999 joint ordinate and literal 2.001 attachment remain separately recorded.

The error columns below are median nonzero-reference errors for **vertical deflection / twist / chordwise bending moment**, in that order. Passing counts include every required slot on all three grids.

| Original load case | Qualified matches | Initial-grid errors: Z / twist / Mc | Finest-grid errors: Z / twist / Mc | Fine mesh checks |
|---|---:|---|---|---:|
| 20lb / 80 / 20 | 3,664/6,480 | 0.002991% / 0.000618% / 0.000524% | 0.2468% / 0.4137% / 0.5161% | 5/14 |
| 20lb / 90 / 10 | 3,683/6,480 | 0.004119% / 0.000223% / 0.000227% | 0.3151% / 0.6033% / 0.2377% | 5/14 |
| 30lb / 80 / 20 | 3,731/6,480 | 0.001454% / 0.000122% / 0.000173% | 0.2598% / 0.3756% / 0.6136% | 5/14 |
| 30lb / 90 / 10 | 3,630/6,480 | 0.002650% / 0.000326% / 0.000340% | 0.3061% / 0.5996% / 0.2327% | 6/14 |

The **14,708/25,920 qualified matches** comprise 3,272/13,440 structural entries, 9,600/9,600 conditional zeros and 1,836/1,920 input echoes. Conditional zeros and echoes do not independently validate structural physics. The remaining 960 `f_reac` entries stay unresolved: 42 happen to match the scalar-weight diagnostic, giving 14,750 raw printed matches, but those 42 are excluded from the qualified score. No complete 14-channel structural row matches on the finest grids. The earlier rigid baseline score of 13,833/25,920 is retained unchanged, including its original counting convention.

Only **21/56** fine-pair mesh measures pass the unchanged **0.1%** limit. The largest changes per case are 0.205–0.211%. These failures are retained; a converged nonlinear solve is not proof of spatial convergence. Further refinement may establish the continuum limit, but should not be expected to reproduce an archived coarse-grid result more closely.

Maximum fresh residual is **8.57e-14**, total-force imbalance **2.14e-14 lb**, and total-moment imbalance **1.54e-10 lb·ft**. Each roller carries exactly zero force and equal/opposite couples; rotation continuity is exact in the saved results. Maximum free relative translations on the finest grids are **0.00461–0.01265 ft**, confirming that the unconstrained translation is actually exercised. Root clamps and all original numerical gates pass. Signed weights remain static loads, not physical negative masses for dynamics.

All numerical children ran serially with one BLAS thread, a 180-second limit and a 512 MiB address-space limit. The twelve solver calls total **47.61 s**; the largest child peak RSS is below 114 MiB. No solve was retried. The independent saved-result audit rechecks all original numeric tokens/intervals, node positions, reaction mechanics and comparison counts without production imports or another solve.

The audit initially required bit-identical dimensional reactions after saved-state restoration. Ten moment components differed by one binary64 ULP due to capture/restoration/reporting scale multiplication order. That failed audit and its diagnosis are retained. The corrected audit permits at most four ULPs only for these dimensional reaction moments; forces and identity metadata remain exact, and physical/mesh/archived-output criteria are unchanged. The observed maximum is one ULP.

The actual offline browser solves the original **20 lb, 90/10 roller case** on the 152/128 grid in **3.17 s** after **17.24 s** startup. It passes **1,205/1,205 checks** and compares **66,328 numeric values** with native output; maximum absolute difference is **1.33e-11**. The existing `2e-8 + 2e-8*abs(reference)` parity allowance is unchanged. Roller forces, couples, rotations and free translations are checked independently. The saved result and project reopen byte-for-byte with no second solve. Desktop/mobile checks pass; GPU rendering is disabled, so this is not GPU-rendering validation.

Open [isae-st5-roller-project.json](../../examples/isae-st5-roller-project.json) using **Project & saved cases → Open project**, then choose **Open solution** to inspect the saved result. **Load case → Run analysis** recomputes it. The [unchanged ASW input](../../examples/isae-st5-roller-20lb_90_10.asw) is also supplied. This browser check establishes runtime parity for one tested grid, not mesh convergence or native ASWING agreement.

The next comparison work is to resolve historical node/output definitions and cover remaining forward-only, alternate loading and modal variants. The original roller models and type-2 law are now tested; they are no longer merely unexamined candidates. No whole ST-5 family or broad project requirement is complete.

The [machine report](isae-st5-roller-20261103.json) retains all per-case/per-grid errors. Full source pins, unchanged original targets, generated-verifier diffs, raw results, fresh fields, the failed audit and browser evidence are under `artifacts/isae/st5-roller-20261103/`.

To reproduce, first populate the pinned `.reference/isae-validation` archive and the cached user guide as described by the repository's validation setup. Use a new stage:

```sh
python3 scripts/verify-isae-st5-roller.py prepare --stage /tmp/st5-roller
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-isae-st5-roller.py run \
  --stage /tmp/st5-roller --case 20lb_80_20 --level 0
```

Run levels 1 and 2 in order, then the other three case names listed by `--help`, one job at a time. `scripts/assess-isae-st5-roller.py --stage /tmp/st5-roller` audits the completed batch without solving again. Source, source-decoder and kernel pins are checked before and after each job; failed attempts cannot be overwritten.
