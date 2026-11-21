# ST-5 roller-joint mesh refinement

2026-11-04. All four original roller cases now pass **56/56** final mesh checks
at the unchanged 0.1% limit. The earlier **21/56** result remains recorded.
Each case was solved on 152/128 and 304/256 forward/rear intervals using the
current production kernels. The repeated 152/128 outputs are exactly identical
to their retained predecessors. No equation, original input or acceptance rule changed.

| Original case | Final mesh checks | Largest mesh change | Native median errors: Z / twist / Mc |
|---|---:|---:|---|
| 20lb_80_20 | 14/14 | 0.05272% | 0.2591% / 0.4343% / 0.5419% |
| 20lb_90_10 | 14/14 | 0.05173% | 0.3311% / 0.6335% / 0.2496% |
| 30lb_80_20 | 14/14 | 0.05197% | 0.2728% / 0.3944% / 0.6443% |
| 30lb_90_10 | 14/14 | 0.05138% | 0.3213% / 0.6297% / 0.2443% |

Eight cold solves and eight fresh restored residual checks pass; total solver
time is **56.40 seconds**. Maximum fresh residual is
8.07e-13, force imbalance
7.11e-14 lb, and moment imbalance
7.56e-10 lb·ft. Type-2 joints retain
zero force, equal/opposite couples and matched rotations while allowing
translation. All jobs ran serially with one BLAS thread and a 512 MiB cap.

The independent saved-result assessment recounts every original printed token,
half-last-place interval and match flag on both grids, verifies joint reaction
mechanics, and recomputes all mesh measures without importing the solver.
All four baseline replays match the retained output values exactly.

The four added fine grids have **4,164/8,640 qualified printed matches**,
separate from the unchanged registered **14,708/25,920** three-grid result.
The supplemental count includes conditional zeros and input echoes; unresolved
`f_reac` entries remain in the denominator but excluded from the pass count.
No complete structural row matches at the finest grids. Refinement establishes
spatial stability within the declared gate, while the strict archived-output
differences persist. It does not authenticate the original node array or exporter.

The [remaining-source review](isae-st5-source-review-20261104.md) identifies
three additional unpaired static exports and no usable native modal target.
Forward-only mesh convergence (38/56), historical setup, reaction display and
native modal evidence remain open. No whole ST-5 family or broad requirement
is declared complete. Production code and the previously verified application
are unchanged; this evidence-only update does not require an application rebuild.

[Portable results](isae-st5-roller-refinement-20261104.json). Complete plans,
verifiers, logs and saved states are in
`artifacts/isae/st5-roller-refinement-20261104/`.
