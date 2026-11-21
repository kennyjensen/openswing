# Expanded ISAE comparisons — 2026-10-26

Comprehensive comparison against the archived ASWING results is the priority.
The default registry now has **nine adapters, 3,099 jobs and 39,785 scalar output
slots across selected scopes in 19 of the 41 families**. All 279 original models
remain inventoried; 22 families still need adapters. Registration is not a pass.

The new SA-11/SA-12 batch is terminal: **1,676 jobs**, with every one of its
8,672 required scalar targets retained. Its original inputs, declared meshes,
physical checks and printed-precision reference gates are unchanged.

| Family | Finished jobs | Computed | Failed | Blocked | Valid scalar outputs / required | Strict scalar matches |
|---|---:|---:|---:|---:|---:|---:|
| SA-11 | 656 | 47 | 281 | 328 | 329 / 4592 | 0 |
| SA-12 | 1020 | 1020 | 0 | 0 | 4080 / 4080 | 52 |

SA-12 covers all six original tables: 510 rows, four raw coefficients and two
meshes. Ground flag, normal, height, attitude, force/moment reconstruction and
residuals are independently checked from saved data. All
51,307 audit checks and
535,500 checks of the saved physical
quantities pass; the [audit summary](isae-suite-expanded-20261026/sa12-saved-audit-summary.json)
retains their exact scope. This verifies the
comparison evidence; it does not mean the archived values match. Pitch=alpha
remains an explicit conditional reconstruction of the missing historical pose.

SA-11 covers all eight baseline/extension tables, 328 rows and seven outputs on
two meshes. All 281 solver failures activate the local section-normal Mach
guard. The finer grid fails much more often; source circulation and geometry
sampling near the tips need investigation. Guard activation does not by itself
establish physical transonic flow. Four tables retain 328 blocked jobs because
their archived force/coefficient normalization conflicts with the literal model.
Other winglet variants and historical PG/startup settings remain unresolved.
The [saved-result review](isae-suite-expanded-20261026/sa11-saved-review.md)
records each failure, table/grid counts and exact tip-sample locations.

The [batch summary](isae-suite-expanded-20261026/batch-summary.md) supplies
per-table errors and mesh differences. Its 39 families outside this selected
batch must not be confused with the **22 missing adapters in the default
registry**. Results are kept separate from the older
[2,443-job broad baseline](isae-suite-current.md); no entire family is declared
fully validated, and scalar match fractions are not a completion percentage.

The suite integration has **158 passing focused tests**. A separate ST-2 reader
fix has **21 passing tests** and restores two previously omitted static rows.
The [saved-data reduction](isae-suite-expanded-20261026/st2-restored-rows.json)
now retains all 46 rows on three historical grids, leaving the original 44
predictions and tip differences unchanged. Those historical states used modified
inputs; the correction does not add an unchanged-input ST-2 pass.

The [ST-2 readiness audit](isae-suite-expanded-20261026/st2-readiness.md) identifies
396 native scalar targets and the out-of-domain Weight anchors blocking literal
replay. The [AP-1 audit](isae-suite-expanded-20261026/ap1-readiness.md) identifies
six paired states and 900 span rows, with engine/resultant recovery and literal
zero-lift-slope semantics still unresolved. Both remain on the
[complete family backlog](isae-suite-backlog.md).

The [P-2 readiness audit](isae-suite-expanded-20261026/p2-readiness.md) identifies
312 candidate model values across 24 curves. Original power and CdA inputs still
need recovery; experimental series and duplicate graphics remain separately
preserved. The existing component API supports forward flow, but this does not
yet supply a complete archived comparison.

The batch was interrupted after 1,423 completed results. All retained results
are byte-identical, four partial attempts are preserved, and only 253 unfinished
jobs were resumed. The resumed owner exited and was reaped; the interrupted
historical owner's exit was not observed. These facts are recorded separately
in the [execution receipt](isae-suite-expanded-20261026/batch-owner-receipt.json).

The [evidence archive](isae-suite-expanded-20261026-evidence.zip) contains the
requests, results, logs, frozen code, references and independent audits. Every
archived payload was reopened and hash-verified. The
[machine report](isae-suite-expanded-20261026.json) records the registry and
batch counts separately. Numerical algorithms and the browser bundle did not
change in this expansion.
