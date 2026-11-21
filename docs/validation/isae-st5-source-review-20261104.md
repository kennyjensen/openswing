# ST-5 remaining source review

2026-11-04. The remaining archive review identifies no usable native modal
target. The 16 registered static cases already cover all 24 complete named
model/driver/output triples. Three additional unique static exports lack a
verified generating model and run; they are retained as unresolved evidence,
without adding passes or inventing comparison settings.

All 207 ST-5 files match the pinned ISAE manifest. Fresh imports using
`drela-segspl-v1` parse 36 of 38 models. The two identically hashed
`JW_1_Modal_analysis.asw` files both contain a literal `v` in a numeric chord
field on line 64 and are rejected. Neither is silently repaired.

The 36 text outputs are static span listings. All 36 MATLAB containers decode
as static beam arrays; no eigenvalue variables were identified. The 24 shell
drivers and 16 MATLAB scripts/backups contain no identified modal invocation.
The 14 PDFs and 24 EPS/SVG figures concern static loading or geometry. Section
4.5 of the supplied structural report describes ST-5 static experiments;
the preceding frequency figure belongs to ST-4.

The native PostScript plot shows joined-wing geometry and force vectors. It
is truncated, so its line-only preview is qualified rather than treated as a
complete rendering. Its footer says ASWING 5.98, while driver paths name 5.92;
this does not authenticate a common generating executable.

| Additional static export | Unique rows | Noncoordinate values | Printed weight (lb) |
|---|---:|---:|---:|
| `JW1_FW_30lb.txt` | 58 | 464 | -58.58 |
| `JW1_test.txt` | 80 | 640 | -58.08 |
| `JW_1_FWc_30lb.txt` | 58 | 464 | -58.58 |

Each appears in four byte-identical copies. These 1,568 values are unbound
source evidence, not new registered tests. In particular, `JW_1_FWc.asw` adds
-59.922 lb of point weights relative to the registered forward model, with
the same distributed-weight tables, while the similarly named exports print
the same total weight. Filename similarity is insufficient to bind them.

The initial audit attempts are preserved: one searched encoded EPS image
bytes as text, one used a case-sensitive record key incorrectly, and the
next exposed an incorrect hand-summed expected weight. The corrected audit
excludes ASCII85 image streams, reads the parser's lowercase `weight` key,
and verifies the literal scaled sum. None of these corrections changes a
physical equation, source file or numerical acceptance gate.

This closes the planned source search, not ST-5 validation. Remaining work
includes roller/forward mesh convergence, historical discretization and
reaction-display definitions, and unavailable native modal evidence.
[Portable inventory and findings](isae-st5-source-review-20261104.json).
Full tokens, hashes and audit attempts remain under
`artifacts/isae/st5-source-review-20261104/`.
