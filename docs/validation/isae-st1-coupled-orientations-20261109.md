# ST-1 coupled blade: all three static orientations

The `[45/0]3s` static load–deflection comparison now passes **63/63 coordinates
at 5%**, covering all three reported root orientations and all seven loads in
each curve. The largest nonzero relative error is **0.1117%**. This completes
the comparison with the three archived ST-1.C static curves; its modal
response and the other blade layouts remain separate work.

![Three-orientation comparison](../../artifacts/isae/st1-coupled-orientations-20261109/comparison.png)

[SVG](../../artifacts/isae/st1-coupled-orientations-20261109/comparison.svg) ·
[CSV](../../artifacts/isae/st1-coupled-orientations-20261109/comparison.csv).

| Reported root orientation | Literal ASW twist multiplier | Curve matches | Maximum nonzero error |
|---|---:|---:|---:|
| −45° | +45° | 21/21 | 0.0920% |
| 0° | 0° | 21/21 | 0.1117% |
| +45° | −45° | 21/21 | 0.00744% |

The sign mapping follows the original `Post_analysis.m` calls and plot titles.
The two new loops are lines 169–171 and 243–245, using masses 0, 0.02, 0.05,
0.1, 0.2, 0.3 and 0.4 kg. Only the mass and twist multiplier are changed,
exactly as the original `change_mass.m` does, and the empty trailing Engine
block is explicitly terminated. EIcs remains 0.102 N m², with all other
material, geometric, attachment and load settings preserved.

This compares the magnitudes of displacement relative to each orientation's
self-weight-only equilibrium, as plotted by the author. It tests the changing
bending–torsion response with root orientation, including large vertical
deflection, spanwise shortening and the small sideways response of the flat
blade. Magnitude plots alone do not independently determine component signs.
ISAE Part III §4.1 and Figure 21 (p. 33) identify these three static conditions.
Experimental markers are kept separate from the ASWING curves.

The original EPS tick labels and vector polylines supply the references without
solver-based scaling. Both companion PDFs were rendered and visually checked
for axis/legend correspondence. The largest relative discrepancy occurs at
the flat blade's smallest nonzero X deflection: 0.3476 micrometres of error
on a 0.3112 mm reference. That error is within the vector file's approximately
0.538 micrometre coordinate-rounding allowance. Original printed-coordinate
precision and the 5% allowance are both retained.

The 14 new curve states and two loaded refinements all converge and satisfy
independent distributed-plus-tip-weight force/moment checks and clamp checks.
The largest residual is 3.07e−13. Refining nominal 100 to 200 intervals changes
the maximum-load position by 9.16 micrometres at 0° and 8.41 micrometres at
+45°, or 0.00339% and 0.00387% of the corresponding coarse displacement
magnitudes. These are loaded-position mesh diagnostics; they do not replace
a full curve refinement study or claim an asymptotic convergence rate.

The earlier −45° results are reused from the
[first curve comparison](isae-st1-static-layouts-20261109.md). Its contradictory
same-name raw text snapshot remains failed. The primary archive tally stays
**9/200**, including three computed mismatches and 188 unavailable values.
The overlapping curve values and refinement states are not added to that tally.
No whole ST-1 validation or dynamic validation follows from the static result.

Every process used one BLAS thread with 512 MiB address-space, 15 s CPU and
25 s wall limits. Accepted solve times after imports were 0.63–1.61 s and
peak resident memory stayed below 241 MiB. An initial post-result console
formatting error is retained separately; it changed no physical result.
All 141 production modules are unchanged, with no browser/build job run.

[Reproduction script](../../scripts/verify_st1_coupled_orientations.py) ·
[source and case plan](../../artifacts/isae/st1-coupled-orientations-20261109/plan.json) ·
[machine summary](../../artifacts/isae/st1-coupled-orientations-20261109/summary.json).
