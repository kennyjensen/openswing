# SA-3: accurate material arc and ASWING comparison

The fixed arc table had a confirmed numerical defect near SA-3's curved tip.
It is replaced for new meshes by spline-derivative quadrature. **The archived
ASWING mismatch remains:** all 66 new states converge, but no finest-mesh output
matches its archive token to half the last printed unit. Experimental agreement
is not required. The original model and commanded conditions are unchanged.

## Geometry defect and correction

The original 2049-point polygonal arc gives a full axis length of
2.085742123527414 m; independent integration gives 2.0857709828106326 m.
That is a small total error, −0.001384%, but two mirrored short tip intervals
have a −9.91186% length error. With the same retained 401 node parameters (400 intervals),
accurate integration moves a control point by up to 0.143713 mm. Merely adding
the original spline knots to the polygonal table still leaves a 6.65% local
interval error. An independent Decimal natural spline and fixed GL64/128
integration confirm the adaptive-integral result within 8.88×10⁻¹⁶ m.

New meshes identify their construction as `accurate-arc-v2`. Vectorized 8/16-point
Gauss rules integrate the norm of each piecewise cubic axis derivative. Adaptive
integration cells split axis spline knots, reflected knots and rigid position
jumps; ordinary spline knots do not become additional computational nodes.
Bracketed inversion maps material arc back to the original input parameter.
Short interval lengths use direct local integrals and sums, avoiding cancellation
of cumulative arcs. A signature of the actual axis inputs controls cache reuse.
The Gauss-rule difference estimates numerical error; it is not a rigorous bound.

The independent final geometry check passes 280 checks: maximum interval-length
difference from the GL128 reference is 3.93×10⁻¹⁶ m, and control-point difference
is 1.17×10⁻¹⁴ m. Cold map construction takes 3.39 ms versus 1.19 ms for the old
polygonal map on this machine; cache lookup averages 0.0244 ms. This changes
geometry integration accuracy, with no aerodynamic equation or convergence
tolerance adjustment and no model-property fitting.

Saved `physical-breaks-v1` and `all-breaks-v0` equilibria and accepted time steps
retain their exact old mesh construction. A warm start retains either historical
recipe only when the requested mesh settings match. The six frozen fixture files
are unchanged. New tests cover analytic curves, nonlinear parameterization,
reflection, extrapolation, jumps, cache invalidation and saved-state replay.
Early candidate checks exposed short-interval cancellation, tiny-target inversion
and a Daedalus representable-endpoint termination problem; all were corrected
and their unsuccessful checks remain in the evidence archive.

## Full original polar rerun

The repeat uses the same 22 exact incidence commands, 89.4 m/s, density
1.2256 kg/m³, updated influences and fixed PG Mach zero as the
[previous source-pinned study](isae-sa3-reference.md). Each of the 100/200/400
cosine-interval meshes receives 22 independent cold solves and fresh prescribed
circulation residual checks. The maximum fresh residual is
9.15e-15. Public native solves total 20.491 s;
the sequential batch takes 45.623 s. Timings are observations,
not a controlled before/after solver benchmark.

At 400 intervals, differences from the archived outputs are:

| Output | Prior RMSE | Corrected-arc RMSE | Corrected maximum absolute difference |
|---|---:|---:|---:|
| Lift | 1.00375741 | 1.00430766 | 1.38549404 |
| Drag | 1.01471776 | 1.01921354 | 2.22335239 |
| CL | 0.00034334467 | 0.000343533189 | 0.000474651612 |
| CD | 0.000347298759 | 0.000348837616 | 0.000761074941 |
| CDi | 3.91035241e-07 | 3.92084889e-07 | 6.64464872e-07 |
| CM | 1.37646391e-05 | 1.37752243e-05 | 2.28976976e-05 |
| efficiency | 0.00220525609 | 0.00220736198 | 0.00232455951 |

Lift and drag are in N; the other outputs are dimensionless. All 154 checks from
200 to 400 intervals pass the unchanged 1% successive-mesh criterion. From
100 to 200, the 22 pitching-moment checks fail; the other 132 pass. Overall,
286/308 mesh checks pass. No complete row or individual finest-mesh output
matches the strict printed-precision diagnostic. That diagnostic and the mesh
criterion are separate; neither is a fitted tolerance for reference agreement.

At the final incidence, CD is 0.044801274941, versus archived 0.0440402,
a difference of 0.000761074941. The earlier difference was
0.000758382. Correcting the arc does not explain the drag gap. The maximum
local normal Mach remains 0.982469; the
zero-chord tip and its mesh-sensitive local flow still qualify interpretation.

The original ASWING command requests 100 nodes, whereas these runs use explicitly
reported interval counts. Original node placement, startup K/F, PG/ambient history,
and spline endpoint conventions remain unresolved. The source review found no
supported change to the documented force or vortex placement formulas. Do not
remove bound induction or change wake-core/model properties to fit the archive.

The independent saved-data audit passes 10,818 checks. It reconstructs all
seven output channels, strip force/moment sums, residual maxima, reference-token
differences and mesh comparisons, and checks all retained material mesh arrays.
It imports no production code and performs no further physical solves.

## Regression and compatibility checks

All 674 selected regression tests pass: 575 core geometry, circulation, inertia,
network and saved-state cases; 93 focused arc/mesh-recipe cases; and six retained
Daedalus cases. The core batch initially passed 340 cases before a test attempted
to restore an old fixture onto the new default mesh. That test now reconstructs
the fixture's recorded recipe and passes, with its fixture and numerical gates
unchanged. The other 234 planned cases pass in two separate groups. No production
code changed after the final native and browser source freeze. This is targeted
regression coverage, not a claim that the entire repository test suite ran.

## Browser and compatibility

The selected 400-interval final-incidence solve passes 355 browser checks,
offline after startup. It agrees with the native result across
20,941 numerical values under the unchanged 2×10⁻⁸ absolute/relative
gate; maximum absolute difference is 4.02e-11. Solve time is
8.72 s, separately from 27.73 s runtime startup.
The downloaded project restores its result byte-exactly without another solve.
The independent WebAssembly replay of both frozen historical mesh formats passes
71 checks, including retained accepted time-step equations. Six additional
Daedalus saved-state regressions pass with their literal `physical-breaks-v1`
identity unchanged.

[Browser report](isae-sa3-accurate-arc-browser.json) ·
[Importable project](../../examples/isae-sa3-accurate-arc-project.json)

[Full comparison](isae-sa3-accurate-arc-comparison.json) ·
[All values](isae-sa3-accurate-arc-comparison.csv) ·
[Summary](isae-sa3-accurate-arc-summary.json) ·
[Raw evidence](isae-sa3-accurate-arc-20261025-evidence.zip)

The full OpenSwing goal remains active and incomplete.
