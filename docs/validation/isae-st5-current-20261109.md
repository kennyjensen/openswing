# ST-5 current mechanics comparison

The subsequent [complete static replay](isae-st5-family-current-20261109.md)
now covers all 16 original snapshots and 32 current-code states. This two-state
pilot remains its preserved starting evidence; the later report includes the
direct comparison with Figures 28–29 and the remaining convergence checks.

ST-5 is the active focus at the user's request. Two fresh, bounded serial jobs
replayed the original rigid-joint `JW_1_20lb_80_20` snapshot with the current
production source-discrete structural operator and segmented spline. No load,
stiffness, geometry, joint law or production equation changed.

| Grid, forward/rear intervals | Structural values within 5% plus printed rounding | Strict printed matches | Solve time |
|---|---:|---:|---:|
| Original printed stations with exact known anchors: 38 / 32 | 1,120 / 1,120 | 403 / 1,120 | 0.85 s |
| Midpoint subdivision: 76 / 64 | 1,073 / 1,120 | 129 / 1,120 | 1.06 s |

These are two evaluations of the **same 1,120 observations**, not independent
targets to add together. They are a supplementary pilot, not a replacement
for the sixteen-case family ledger. All 80 source rows and all 27 outputs
remain in the saved comparison. The 14 computed structural fields are reported
separately from prescribed static zeros, input echoes and the unresolved
`f_reac` scalar display. Zero and very small values retain their original
printed half-last-place allowance; no new near-zero floor was introduced.

The printed-station result reproduces the earlier close finite-grid agreement
with **current production code**. Its forward/rear tip deflection errors are
0.00084% / 0.00856%; tip twist errors are 0.01349% / 0.01281%.
This supports the implementation of the discrete structural equations. It does
not recover unrounded historical nodes or identify the original executable.

On the subdivided grid, median errors for vertical deflection, twist and
chordwise bending moment are **0.306%, 0.595% and 0.761%**. There are 47 failed
structural values: one twist, eight chordwise moments, ten torsional moments,
six normal-axis moments, four normal forces, eight strain values and ten
shear-stress values. Small denominators make some pointwise percentages large;
all values and dimensional errors are retained in the assessment. Forward tip
twist differs by 2.551%, so mesh sensitivity is not solely a rounding issue.

Both states pass fresh equilibrium, support force/moment balance, root clamp
and rigid offset-joint checks. This first refinement pair passes **0 of 14**
of the existing **0.1%** mesh gates: changes range from 0.116% to 2.079% of the
deformation/force envelopes. Earlier finer-grid studies are preserved, but are
not relabeled as fresh current-code solves. No new accepted family passes are
claimed from this two-grid pilot.

## Authoritative setup distinction

[Jan, Part III](../../reference/aswing-authoritative-20261108/isae-part-3-structure.pdf),
§4.5, pp. 40–44, defines **ST-5.A** as the rigid joint and **ST-5.B** as an
in-plane link. Page 42 specifies that the latter matches z translation and
x/y rotations while releasing x/y translations and z rotation. It explicitly
requires an ASWING modification. Figures 28–29 compare body-x bending moments
against experiments; the ASWING curves are the validation targets here.

The archived `Link_Joint` models instead specify literal `KJtype=2`, which
[Drela's public guide](../../reference/aswing_doc.txt) defines as matched
rotation with free translation. The existing archive comparisons implement
that literal roller law. Their close matches must not be presented as proof
of the paper's modified in-plane link. Keep original archived outputs,
modified-ASWING paper curves and experimental curves distinct.

Next, refresh the remaining rigid, elliptical, forward-only and literal roller
snapshots in small serial jobs; establish a transparent 5% mechanics ledger
without multiplying votes by mesh repeats or prescribed zeros. Check the
paper's body-x moment curves and their generating scripts separately, especially
the modified link. Preserve historical exporter/reaction-display limitations
and the unavailable modal reference described in the
[source review](isae-st5-source-review-20261104.md).

## Evidence and reproduction

The [saved-only assessment](../../artifacts/isae/st5-current-20261109/rigid-20lb-80-20/assessment.json)
rechecks original row identity, decoded values, printed precision, differences,
all 27 field counts, tip errors and mesh changes without importing the solver.
Inputs, all 141 production Python files, source reports and generated verifier
are checksummed. Each numerical child is capped at 512 MiB address space,
15 CPU seconds and 25 wall seconds with one BLAS thread. Both exited normally
and were reaped; complete jobs took 13.47 and 11.92 seconds, including imports,
restoration, auditing and evidence writes. Maximum peak RSS was 110,936 KiB.
No solver remains running. Browser/build checks remain held.

```sh
.venv/bin/python scripts/verify_st5_current.py prepare --output NEW_DIRECTORY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/verify_st5_current.py run --output NEW_DIRECTORY --level 0
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/verify_st5_current.py run --output NEW_DIRECTORY --level 1
.venv/bin/python scripts/assess_st5_current.py --output NEW_DIRECTORY
```

The initial preparation stopped before importing production code because the
old `.reference` pin path resolved to the visible `reference/` directory. The
bytes and SHA-256 were unchanged. The path check now resolves that symlink
while retaining exact size/hash checks; the diagnosis is preserved. No failed
numerical solve or retry is hidden by this correction.

ST-4 was stopped when focus changed. Its recurring paper replay completed
16 of 24 configurations; the interrupted next job and terminal receipt are
preserved. The earlier complete **66/72** paper and separate **31/31** native
results remain unchanged. See the [ST-4 runner record](isae-st4-recurring-20261109.md).
