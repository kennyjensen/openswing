# Legacy mesh/settings evidence for SA1

**No numeric ASWING startup node count, Fourier count, or spacing-blend formula was authenticated by this bounded search.** The original SA1 folder has no `.set`; unrelated companion files cannot establish its settings. No solves, residuals, matrices or production imports were performed.

There is one new, concrete correlation. At pinned WingLoop revision `23b3a685bbfd282cda1996011b6a94aad020311a`, `.set` line 103 contains `48 16 12 25`. The [public saved output](https://raw.githubusercontent.com/LeonardoAVONI/WingLoop/23b3a685bbfd282cda1996011b6a94aad020311a/WingLoop_Library/wingloop_testrun/aswing_geometry/output) contains four corresponding beam tables with exactly those row counts. This strongly corroborates the per-beam computational-station count vector for that run; it does not identify the preceding global values.

| Retained tokens | Evidence | Remaining qualification |
|---|---|---|
| `40 19` | Present at line 101 in both WingLoop files and four original ISAE JW companions | Plausible global/default node and Fourier counts, but no primary field names or startup transcript proves that interpretation. |
| `0.600000024 0.600000024` | Same line 102 values in those six examples | Meaning and spacing/blend formula remain unknown. No coordinate fitting was used. |
| `48 16 12 25` | WingLoop line 103 matches the same run's four output-table counts | Supports this per-beam count vector only. |
| `-1 -1 -1 0` | WingLoop line 104 aligns with three lifting surfaces and one body | Default-mode sentinel interpretation remains a hypothesis. JW companions instead retain `50` for their lifting beams. |

The [author's FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt) says `.set` and `.pnt` layouts depend on both code version and compiled array dimensions, and that their memory-dump format is deliberately undocumented. Cached `Aswing.py` writes interactive operating commands but neither decodes `.set` nor selects NODE/Fourier/spacing settings. WingLoop simply delegates `.set` loading to `SGET`.

The independently pinned public-repository extended manual adds no spacing formula: it repeats an example with 180 nodes and Fourier modes 1–19. The [v5.67 notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt) establish that NODE `i` requests nodes and enforces a breakpoint minimum. They do not establish whether `I200` changes K, how the nodes are spaced, or exact requested-versus-actual counts. The earlier v5.60 note records a circulation-default fix without giving its values.

The next decisive evidence is a matching source definition/writer (`ASWING.INC` plus NODE and settings routines), or a versioned startup/NODE/settings transcript. Repeated unrelated saved values must remain hypotheses until then. [JSON evidence](legacy-mesh-settings-review.json) pins the primary downloads, exact tail records, wrapper Git blobs, table counts and source lines. Downloads and PDF extraction are terminal; no reference executable was run.
