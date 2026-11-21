# SA-6: all published roll/yaw series compared with current equations

All **616/616** comparisons pass the existing 3% gate under the explicit input
hypotheses below. They cover all 14 author-tabulated ASWING roll/yaw series:
seven configurations, level flight and post-stall, eleven control deflections,
two coefficients, and both requested meshes. The maximum error is **1.927%**.

This completes the qualified roll/yaw table comparison. It does not authenticate
the producing ASWING settings or complete SA-6. Its post-stall state derivatives
remain at 2,780/3,168, including 282/528 pitch-rate checks, in the separate
retained comparison. Production defaults and registered acceptance are unchanged.

| Configuration | Level-flight matches | Median / maximum error | Post-stall matches | Median / maximum error |
|---|---:|---:|---:|---:|
| 10b_25c, explicit span reconstruction | 44/44 | 0.874% / 1.927% | 44/44 | 0.254% / 0.789% |
| 15b_25c | 44/44 | 0.205% / 0.547% | 44/44 | 0.200% / 0.833% |
| 20b_15c | 44/44 | 0.355% / 0.818% | 44/44 | 0.463% / 0.941% |
| 20b_20c | 44/44 | 0.342% / 0.480% | 44/44 | 0.462% / 0.945% |
| 20b_25c | 44/44 | 0.342% / 0.642% | 44/44 | 0.437% / 0.944% |
| 20b_30c | 44/44 | 0.340% / 0.547% | 44/44 | 0.418% / 0.943% |
| 20b_35c | 44/44 | 0.345% / 0.884% | 44/44 | 0.317% / 0.942% |
| Total | 308/308 | Maximum 1.927% | 308/308 | Maximum 0.946% |

Each cell covers `Cl` and `Cn`, physical deflections 4°–44° in 4° increments,
and requested meshes of 64/128 intervals, producing 66/130 strips after the
required control breaks. Errors above summarize both meshes. There are 308
distinct native scalars, each compared on both meshes; they are not 616
independent native observations. Of the 308 references, 88 have exact raw
`.fmat` witnesses and 220 are author transcriptions without retained run headers.
The [source catalogue](isae-sa6-native-tables-20261101.md) excludes experimental
columns and artificial zero rows.

All comparisons use speed 20 m/s, density 1.2256 kg/m³, PG Mach zero, zero
sideslip, stall strength 20, transition width 0.05 and core ratio 0.25.
Level-flight body incidence is 0° with current influences. Its gain magnitudes
are 0.040/0.045/0.055/0.070 for the 15/20/30/35%-chord variants and 0.060
for all three 25%-chord span variants. These follow the conditional
[printed-response gain identities](isae-sa6-native-tables-20261101.md), anchored
to the supplied 15%-chord value and extended to the same section on other spans.
The hypothesis changes the requested F1 value, retaining the source sign and
the original `.asw` files. It was not fitted by searching the new comparisons.

The post-stall comparison uses the literal deck gains, body incidence 12° and
frozen influences. For the span variants, the competing 8° body-incidence
interpretation is retained in full. It passes only **4/132** canonical span
checks, versus **132/132** at 12°. This supports the latter interpretation but
does not recover missing native run headers. The source's wing/body incidence
ambiguity remains a qualification. Strength 20 and frozen influences also
remain hypotheses supported by the earlier paired chord comparisons.

The original `10b_25c` and `15b_25c` decks are byte-identical, with SHA-256
`be6dc1bd0e989524193cdfec87b2e6138d86f8a6de23fc7c00da786d66c5a975`.
Both put the inner control boundaries at ±0.381 m, giving 15-inch control spans.
The separate [10-inch reconstruction](../../artifacts/isae/sa6-span-native-20261101/inputs/Straight_Wing_10b_25c_reconstructed.asw)
moves only those boundaries to ±0.508 m; the ±0.762 m tips, control gains,
moment gains and remaining model fields are unchanged. An independent rational
arithmetic check verifies this transformation. The supplied deck is also scored
against the 10-inch targets and continues to fail.

| Span comparison | Matches | Median / maximum error among failures |
|---|---:|---:|
| Level 10b, literal geometry, literal gain 0.055 | 0/44 | 34.07% / 43.07% |
| Level 10b, literal geometry, shared gain 0.060 | 0/44 | 46.75% / 56.09% |
| Level 10b, reconstructed geometry, literal gain 0.055 | 0/44 | 7.18% / 9.77% |
| Level 15b, literal gain 0.055 | 1/44 | 8.05% / 8.80% |
| Level 20b, literal gain 0.055 | 4/44 | 7.83% / 8.88% |
| Post-stall 10b, literal geometry, 8° | 0/44 | 54.34% / 92.42% |
| Post-stall 10b, literal geometry, 12° | 0/44 | 41.92% / 56.28% |
| Post-stall 10b, reconstructed geometry, 8° | 0/44 | 22.40% / 32.75% |
| Post-stall 15b, 8° | 2/44 | 21.31% / 44.33% |
| Post-stall 20b, 8° | 2/44 | 22.00% / 56.45% |

The span study completes 220 new cold calls and 44 exact prior-result reuses.
Both predeclared pilots pass 24/24 canonical checks, allowing their full
extensions; the alternative input/geometry branches remain in the results.
The worker timing is 44.00 seconds. The combined table also uses the four
chord variants from the [previous level-flight study](isae-sa6-level-input-comparison-20261101.md).
Production source hashes and reused request settings are checked for identity.

For the four post-stall chord variants, all 88 saved circulation vectors are
re-evaluated with the current aerodynamic equations. This makes **no new
nonlinear solves**: each vector is prescribed, remains bitwise unchanged,
and must independently satisfy the residual and local-Mach gates. All 176
native moment checks pass. The field replay takes 4.26 seconds in its worker
timing scope. The prior solve's successful terminal status is required for
each saved vector. All numerical processes run serially with one BLAS thread.

Independent straight-wing equations reconstruct section normals, bound/wake
velocities, stall leakage, nonlinear residuals, strip forces and moments.
Across the combined results, the largest velocity discrepancy is 4.76e−14 of
freestream speed, residual is 8.51e−13, normalized wrench discrepancy is
1.33e−15 and coefficient discrepancy is 6.67e−16. These checks verify equation
implementation; agreement with the same published equations does not establish
the missing historical ASWING inputs.

The final standard-library audit verifies all **1,056 scalar decisions**,
including the failed alternatives, against the original MATLAB tokens using
decimal arithmetic. It checks all 14 series and all 616 expected comparison
keys, source hashes, the geometry reconstruction, summed strip wrenches and
the unchanged 42 registered status rows. It imports no solver and performs no
aircraft evaluation. Browser/WASM verification and refreshed bundles remain
pending under the current host-stability limits.

Evidence: [span plan](../../artifacts/isae/sa6-span-native-20261101/plan.json),
[all span branches](../../artifacts/isae/sa6-span-native-20261101/analysis.json),
[post-stall chord replay](../../artifacts/isae/sa6-span-native-20261101/chord-replay/analysis.json),
[complete independent audit](../../artifacts/isae/sa6-span-native-20261101/combined-verification.json),
[comparison CSV](../../artifacts/isae/sa6-span-native-20261101/combined-comparison.csv),
[audit source](../../artifacts/isae/sa6-span-native-20261101/audit.py),
[field checker](../../artifacts/isae/sa6-span-native-20261101/verify.py).

The saved-result audit can be repeated without rerunning the aircraft cases:

```sh
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  artifacts/isae/sa6-span-native-20261101/audit.py
```

The next unresolved SA-6 target is the post-stall state derivative comparison,
particularly pitch rate. Static roll/yaw table agreement supplies no basis to
alter its force derivatives or to adopt the inferred inputs as production defaults.
