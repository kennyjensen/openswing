# ST-5 forward-only mesh refinement

2026-11-04. All four original forward-only cases now pass **56/56** final
mesh checks at the unchanged 0.1% limit, up from the retained **38/56** result.
All 16 registered ST-5 static cases therefore have passing final mesh pairs:
rigid cosine, rigid elliptical, roller and forward-only each pass 56/56.
This is spatial-convergence evidence, not complete native-ASWING validation.

| Original case | Final intervals | Mesh checks | Largest mesh change | Failed native medians: Z / twist / Mc |
|---|---:|---:|---:|---|
| cosine_20lb | 304→608 | 14/14 | 0.02993% | 0.2991% / 0.6258% / 0.6056% |
| cosine_30lb | 152→304 | 14/14 | 0.06309% | 0.2861% / 0.6133% / 0.5881% |
| elliptical_20lb | 304→608 | 14/14 | 0.02559% | 0.1892% / 0.0835% / 0.2931% |
| elliptical_30lb | 152→304 | 14/14 | 0.05173% | 0.1879% / 0.0787% / 0.2847% |

The 20 lb cosine and elliptical cases retain their 152→304 failures: the
chordwise displacement changes by 0.11974% and 0.10222%, respectively.
Each receives one additional 608-interval solve. The 30 lb cases already
pass at 304 intervals and are not run again. Every original output row,
duplicate trace, source load and printed-precision acceptance rule is retained.

All **10 cold solves and 10 fresh restored residual checks** pass; total solver
time is **45.99 seconds**. The four repeated 152-interval
outputs are exactly identical to the retained earlier results. Maximum fresh
residual is 8.34e-13; force/moment
imbalances are 6.39e-14 lb /
1.47e-08 lb·ft. Jobs remained serial,
one BLAS thread, with 90-second and 512 MiB limits.

The independent saved-result audit rechecks the original numeric tokens and
printing intervals, recounts match flags, verifies root-force balance and the
absence of joints, and recomputes the mesh differences without solver imports.
All models retain their 16 null point-weight records and original distributed loads.

The four final grids have **2,942/6,264 qualified printed matches**.
These supplement the unchanged original **10,670/18,792** three-grid result.
Conditional zeros and input echoes are included and are not independent
physical validations. Unresolved `f_reac` entries remain in the denominator
and are excluded from the pass count. The table reports medians restricted
to failed nonzero-reference scalar checks; complete errors remain in the JSON.

Refinement moves these solutions farther from the archived coarse-grid values.
Historical node coordinates, exporter definitions and native modal evidence
remain unresolved. No production equation, application code or tolerance was
changed. No complete ISAE family or broad requirement is declared validated.

Next comparison work is the remaining ST-3 model/output coverage, including
the separate `test.txt` snapshot and its load-state binding. The ST-5 historical
setup and reaction-display discrepancies remain recorded for later investigation.

[Portable evidence](isae-st5-forward-refinement-20261104.json). Complete plans,
original targets, verifiers, logs and states remain under
`artifacts/isae/st5-forward-refinement-20261104/`.
