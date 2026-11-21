# ST-1 static mechanics: four layouts and nine root conditions

OpenSwing matches **201/201 archived ASWING displacement coordinates at 5%**,
covering every static load curve in the ST-1 postprocessor: four blade layouts,
nine root conditions and 67 load states. The largest nonzero relative error is
**0.762%**. No production equation or material property was changed to obtain
these results. This is strong evidence for the tested nonlinear static mechanics;
the identified bending and torsional frequencies still need validation.

![All nine static comparisons](../../artifacts/isae/st1-static-curves-20261109/comparison.png)

[SVG](../../artifacts/isae/st1-static-curves-20261109/comparison.svg) ·
[CSV](../../artifacts/isae/st1-static-curves-20261109/comparison.csv).

| Blade layout | Reported root angle | Coordinate matches | Largest nonzero error |
|---|---:|---:|---:|
| `[0/90]3s` | 0° | 24/24 | 0.102% |
| `[0/90]3s` | 45° | 18/18 | 0.762% |
| `[20/−70/−70/20]2a` | 0° | 24/24 | 0.132% |
| `[20/−70/−70/20]2a` | 45° | 30/30 | 0.114% |
| `[45/0]3s` | −45° | 21/21 | 0.0920% |
| `[45/0]3s` | 0° | 21/21 | 0.112% |
| `[45/0]3s` | 45° | 21/21 | 0.00744% |
| `[45/0]3a`, naturally twisted | 0° | 21/21 | 0.173% |
| `[45/0]3a`, naturally twisted | 45° | 21/21 | 0.474% |

The three coupled-blade curves reuse the authenticated
[earlier results](isae-st1-coupled-orientations-20261109.md). This extension adds
46 nominal-100 equilibrium states and six nominal-200 loaded refinements,
yielding 138 new reference comparisons. The count is coordinates, not 201
independent experiments: it includes unloaded baselines and zero components.

## What this establishes

ISAE Part III §4.1, pp. 28–34 and Figures 19–22 use these layouts to examine
large bending, spanwise shortening, bending–torsion coupling, root orientation
and natural geometric twist. OpenSwing reproduces their changing load response,
including the asymmetric response of the coupled blade. The comparisons use
ASWING curves, not experimental markers. Magnitude-only reference curves do
not independently determine displacement signs or the full internal strain field.

Every state converges and passes independent distributed-plus-point-weight
force/moment assembly and clamp checks. The largest new residual is 5.39e−13;
the largest normalized moment imbalance is 1.34e−11. Doubling the nominal mesh
at the maximum load changes the six new sensor positions by 6.88–14.28 µm,
or 0.00336–0.00874% of the coarse loaded-minus-unloaded displacement magnitude.
These loaded-position checks establish small mesh sensitivity at those states;
they do not establish a convergence order or refine every point of each curve.

The reference is the magnitude of the loaded sensor position minus its own
orientation's unloaded, self-weight-only position, following `Post_analysis.m`
and the report on p. 28. Zero distributed mass in `[45/0]3a` is retained.
The original scripts request nominal 100 nodes; the report describes 40 cosine
nodes. The exact historical grids remain unavailable. Current jobs use cosine
spacing and insert the original sensor station exactly, giving N+2 nodes.

## Input and reference qualifications

Original files remain untouched. Derived inputs reproduce only the original
`change_mass`/`change_mass2` mass and twist operations. For example, the
angle-ply reported 45° case retains the script's **46° literal ASW twist**:
one degree in its table plus the 45° adder. All named material properties,
loads, geometry and sensor coordinates are preserved. No parameter is fitted.

The empty trailing Engine blocks receive an explicit `End`. The `[0/90]3s`
distribution also has 16 scale values for 15 named columns. The derived copy
removes only its final, unnamed zero. All 15 named scales remain, including
`mg=9.81`, `mgcc=1` and `mgnn=0`; GKc remains the file's 8.7e6. This static
comparison does not justify altering rotary inertia for future modal tests.
Each job records the complete scale mapping and its derived input.

Reference values come from original EPS vector paths calibrated against their
own numeric axis ticks, with graphic precision and tick-rounding uncertainty
retained. The straight zero-X path in the flat cross-ply plot is represented
by two endpoints; the script's eight load stations sample that same flat line.
The worst percentage difference is only 2.11 µm on a 0.277 mm Y displacement,
within that EPS extraction's 2.36 µm absolute uncertainty. All 138 new extracted
values and acceptance decisions were independently replayed with Decimal.

The standalone angle-ply PDFs are inconsistent with their EPS counterparts.
In particular, the PDF labelled root 0° shows nonzero sideways displacement
and extends to 0.7 kg, whereas its EPS and the original 0° producer loop are
flat-root runs ending at 0.5 kg. **Part III Figure 20(a), p. 32 agrees with
the flat-root EPS.** Figure 20(b)'s final plotted coordinates also agree with
the 45° EPS, including Z≈0.15334 m at 0.7 kg; the standalone PDF has a different
curve. PDF renders and a report-page render are retained beside the results.
The inconsistent PDFs are not silently combined with the EPS targets.

An initial checker typo expected angle-ply GKn=1.2e6 instead of the original
1.2e5 and rejected that case before solving. The corrected checker preserves
the model's actual value. `plan.json`, the first 14 successful reports and the
initial checker remain intact; `plan-v2.json` records the correction and unchanged
cases/targets. No numerical result was edited to pass.

## Remaining work and scope

Static curves are now substantially validated for these four ASWING layouts.
Next are the report's physically identified bending/torsional frequencies,
matched equilibrium, mass properties and mode identities. Full ST-1 validation
also remains qualified by its unresolved archived snapshots and modal exports.

The original archive inventory stays **9/200**, with three mismatching raw
`[45/0]3s` position values and 188 unavailable slots. The raw mismatch is
12.85–35.85% despite the matching load curves; its generating setup remains
unknown. These overlapping curve coordinates and refinement meshes are a
separate mechanics scope, not extra passes added to the archive denominator.
That inventory should not be interpreted as 191 demonstrated mechanics failures.

All 52 new processes used one BLAS thread, 512 MiB address-space, 15 s CPU and
25 s wall caps. Peak RSS stayed below 248 MiB; solves after imports took
0.32–3.58 s. All 141 production modules remain unchanged. Browser/build work
remains held.

[Runner](../../scripts/verify_st1_static_curves.py) ·
[plot/replay script](../../scripts/plot_st1_static_curves.py) ·
[source/case plan](../../artifacts/isae/st1-static-curves-20261109/plan-v2.json) ·
[machine summary](../../artifacts/isae/st1-static-curves-20261109/summary.json).
Run each `run --index N` separately under the one-thread environment; use
`prepare`, indices 0–51 and `summary` with `--output` naming a fresh directory
to reproduce the new comparisons. Reference versions and checksums are in the
[authoritative index](aswing-authoritative-references.md).
