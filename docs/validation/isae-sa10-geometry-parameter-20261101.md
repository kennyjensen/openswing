# SA-10 exact geometry and parameter audit

2026-11-01. The retained Louvered mesh and source points agree with an
independent exact piecewise-line construction. Replacing the arbitrary input
parameter with material arc length preserves the physical geometry to
roundoff. A `t`-versus-arc-length mix-up does not explain the sampled drag
discrepancy. No production change or new reference pass follows.

The [input deck](../../.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/1%20-%20Aerodynamics/SA%20-%20Steady%20Aerodynamics%20Cases/SA%20-%2010%20-%20Winglet%20and%20Tip%20Sails%20-%20Lift%20and%20Drag/Aswing_Simulations/Louvered.asw)
uses `t = y` on its supplied right half. The outer segment also rises in z,
so its material length exceeds its parameter increment:

`s(t) = min(t, 0.559) + sqrt(2) × max(t − 0.559, 0)` for `t ≥ 0`.

The tip parameter is 0.7025, but the material semispan is
**0.7619396462005391 m**. The symmetric image gives a total material length
of 1.5238792924010782 m. The specified reference span remains 1.118 m;
it is a separate coefficient-normalization input, not the arc length.

## Independent construction and invariant

The [guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
defines `t` as an arbitrary distribution parameter and preserves doubled
geometry breaks. The [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
equations (150)–(156) define angular sampling in material span, interpolation
of the section position, and the force/control-point offsets.

The independent construction uses the literal straight center section and
45° tips, exact arc lengths, cosine nodes with the two required bends and
root, and the published angular-midpoint formula. It checks section positions,
span/normal frames, strip lengths, bound endpoints, force receivers and
control points against both current production geometry and six saved states:
5°/15°/25°, each at the requested 100/200 counts (102/202 actual strips).

A second model changes only the two tip-parameter entries in the original
beam distribution blocks from 0.7025 to 0.76193964620053911. Geometry values,
section properties, multipliers, duplicated corner, symmetry, references and
ground remain intact. Since each side of the corner is a straight segment
with constant properties, this piecewise affine parameter change describes
exactly the same physical model. The original file is untouched; the
[rewritten diagnostic deck](../../artifacts/isae/sa10-geometry-parameter-20261101/Louvered-material-parameter.asw)
is retained separately.

| Check | Maximum absolute difference |
|---|---:|
| Exact positions/source points versus saved/current geometry | 7.22e−16 m |
| Exact strip lengths versus current geometry | 4.98e−16 m |
| Exact span and normal directions versus current geometry | 2.23e−16 |
| Original versus reparameterized physical source geometry | 3.34e−16 m |

Both parsed models also reproduce the literal chord, axis fraction, zero
twist/incidence, profile coefficients, lift slope and maximum section CL.
The saved parameter arrays are checked separately against those constants.
The work evaluates geometry only; it does not re-solve circulation or change
the reference acceptance policy. The numerical loop takes 0.333 seconds
after imports, in one process with one BLAS thread.

## Consequence for the drag investigation

The [pair decomposition](isae-sa10-drag-pairs-20261101.md) identifies strong
central-wing/tip sensitivity to the relative wind-parallel quarter-chord
offsets. This audit confirms those offsets come from the implemented
one-sided construction on the intended geometry, rather than a parameter,
symmetry, unit, arc-length or angular-sampling error in these six states.

It does not prove native ASWING uses the identical endpoint construction at
doubled corner nodes. Equation (155) explicitly specifies the midpoint;
the source endpoint extension and force quadrature remain the source-level
questions. The prior zero-length-horseshoe cancellation and refined local-Mach
rejections remain in force. Registered SA-10 is still 1,256/2,268, and the
separate strength-20 physical comparison is still 1,088/1,134.

- [Plan and source hashes](../../artifacts/isae/sa10-geometry-parameter-20261101/plan.json)
- [All six geometry comparisons](../../artifacts/isae/sa10-geometry-parameter-20261101/analysis.json)
- [Final verification receipt](../../artifacts/isae/sa10-geometry-parameter-20261101/receipt.json)
