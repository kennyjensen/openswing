# Proposed unloaded source-tree rank proof

This is a proposed extension of the existing grounded rigid-tree argument to
finite-compliance source beams. It is **not enabled in production**. It aims
to avoid a dense startup SVD by proving a trivial mechanical nullspace from
the documented equations. It does not estimate numerical conditioning,
certify a loaded equilibrium, or replace the circulation rank check.

## Scope

The current candidate requires zero homotopy load, zero mechanical state and
frame rates, no operating unknowns, no struts, identity endpoint section
frames, positive material interval lengths, zero jig curvature, and no stepped beam axes. Source compliance and
section-offset arrays must be finite. Perfectly rigid directions are allowed
through zero compliance; finite flexibility is also allowed.

Beam intervals and full rigid/compliant joint connections must form a forest,
with exactly one full Ground per component. Compliant joints retain the
existing checks for an isolated parent endpoint, coincident attachment
points, zero cold intercept, smooth finite slope and positive effective
stiffness. Released joints, cycles and unsupported constraints decline the
candidate and require the existing numerical checks.

## Nullspace argument

Let `p` collect node translations and infinitesimal rotations, and `w` collect
internal beam resultants and joint/Ground reactions. Nonzero force/length
normalizations are invertible and do not change rank. At zero applied load
and zero internal/reaction wrench, the mechanical first variation can be
ordered as

```text
B w         = 0       conservative nodal force and moment balance
D w + C p   = 0       source compatibility and Ground/Joint kinematics
```

The upper-right block is zero because geometry variations multiply zero
internal/reaction loads, and external loads are multiplied by zero homotopy
factor. With `n` nodes, `e` beam edges, `j` joint edges and `g` Grounds, a
forest with one Ground per component satisfies `e + j + g = n`. Both `B`
and `C` are therefore square, with order `6n`.

Root each component at its Ground. At a non-ground leaf, force balance makes
the incident edge force zero. Moment balance then makes its moment zero;
the force-dependent lever contribution has already vanished. Remove the
leaf and repeat. Every internal/joint wrench becomes zero, and balance at
the remaining ground node makes its reaction zero. Thus `B w = 0` implies
`w = 0`.

Finite source compliance maps these zero load increments to zero strain and
curvature increments. With identity frames, source equation 54 then gives
equal infinitesimal rotations across each beam interval. The finite
compliant-joint law also gives zero relative rotation when its structural
moment increment is zero. The full Ground fixes the common rotation to
zero. Source equation 48 and the joint position constraints consequently
give equal translations; Ground fixes these to zero as well. Therefore
`C p = 0` implies `p = 0`, establishing a trivial mechanical nullspace.

The actual beam chord need not equal its material interval length in this
argument. A nonzero jig translation defect remains a residual to solve; it
does not become a claim that the unloaded configuration is equilibrated.
Compliance enters `D`, which disappears from the nullspace argument after
`w = 0`; no energy-Hessian identification is required.

This reasoning uses the constitutive and conservative discretizations in
equations 18–20, 48 and 54–56, and the compliant-joint relations 194–199 of
[Drela's steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
The production cold system also contains circulation. Its block must retain
the separate 1e-10 numerical rank check, and the aerodynamic-force coupling
must be exactly zero before a mechanical-only proof can certify the full
block-triangular system.

As with the existing rigid-tree certificate, algebraic full rank is distinct
from a numerical condition bound. Actual Newton steps and their residual
acceptance checks remain necessary. A future implementation must explicitly
report which kind of certificate it used and retain the numerical fallback
whenever the proof's scope does not apply.

## Independent verification

`tests/test_source_flexible_zero_load_oracle.py` constructs the complete
mechanical first-variation matrix from literal synthetic section properties.
It does not call production constitutive or tangent helpers. Its comparisons
cover finite bending/torsion/shear/axial compliance, section-offset coupling,
flexible main wings with rigid tips, two signed compliant joints, nonzero
circulation, and a nonzero jig translation defect. Missing and duplicate
Grounds provide independent singular counterexamples. All **eight tests pass**
in the retained third invocation (`source-tree-oracle-tests-v3.xml`), with
process exit 0. The first two failed invocations are preserved. They exposed
test-fixture errors: the supported mesh minimum is four panels, and the public
constructor correctly rejects an absent Ground. The latter counterexample now
removes the decoded Ground rows and reaction unknowns after constructing a
valid network; it is used only by the oracle and candidate scope guard.

The candidate scope guard and literal 55/107/211/419-node preflight helper
are retained under `artifacts/isae/ffwt4-frozen-refinement-20261107/` as
`source-tree-candidate.py` and `preflight-source-tree.py`. A preflight only
checks the assumptions; it does not compute a large Jacobian or establish
a 419-node equilibrium.

The preflight exits successfully with three accepted synthetic configurations
and eight rejected controls: missing/duplicate Grounds, nonzero applied load,
nonzero mechanical state, nonidentity frames, nonzero jig curvature, nonfinite
compliance and a released joint. It also accepts all four literal Flare20
meshes, preserving source and kernel identities:

| Nodes | Mechanical unknowns | Total unknowns | Construction and scope check |
| ---: | ---: | ---: | ---: |
| 55 | 660 | 712 | 0.079 s |
| 107 | 1,284 | 1,388 | 0.092 s |
| 211 | 2,532 | 2,740 | 0.121 s |
| 419 | 5,028 | 5,444 | 0.179 s |

These timings exclude interpreter startup and do **not** include matrix
assembly, circulation certification or Newton steps. The literal hinge slopes
are approximately +/-1,000,016.76 rad/(N m); both signed effective stiffnesses
are positive, approximately 9.99983e-7 N m/rad. Small nonzero stiffness is
retained as supplied, not replaced by a free or rigid joint. Such a slope
also illustrates why an algebraic proof must not be described as a numerical
conditioning bound.

`source-tree-plan.json` pins the candidate, oracle, preflight, study and
archived kernel before execution. `source-tree-report.json` and
`source-tree-preflight-execution.json` retain the decisions and actual exit
status. No large Jacobian, 419-node equilibrium, native comparison or new
production rank path was computed by this preflight. Production integration,
fallback controls, conditioning policy and browser validation remain open.
