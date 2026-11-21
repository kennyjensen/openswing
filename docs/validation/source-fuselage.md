# Source-equation fuselage beams

Update 2026-10-31: the subsequent [still-air body extension](body-still-air.md)
removes the body-fluid exclusion recorded in this original increment. Its own
tests and runtime evidence are tracked separately.

2026-10-30. The source structural operators now select the fuselage rotation
sequence for nonlifting body beams. Beams aligned with the aircraft x axis
can use source static equilibrium, fixed/moving vacuum dynamics, and moving
airflow modes, frequency response and time integration. Lifting surfaces
retain their existing equations. This is a feature increment; the full
ASWING implementation and archived-reference validation remain incomplete.

## Published equations and implementation

The steady Technical Description, section 1.2, Eqs.10–12, changes the rotation
order to avoid the surface chart's x-span pole. The local-to-body matrix is
`Rz(psi) Rx(phi) Ry(theta)`. Its curvature matrix is

```text
K = [ cos(theta)  0  -cos(phi)*sin(theta)
      0           1   sin(phi)
      sin(theta)  0   cos(phi)*cos(theta) ].
```

`source_fuselage.py` implements this matrix, the inverse angle extraction,
its exact directional derivative, and unsteady Eq.4's body angular-velocity
to Euler-rate map. Source endpoint constitutive laws select the appropriate
K at each beam. The damping law differentiates both endpoint K matrices and
the endpoint angle difference, retaining all terms of unsteady Eq.62.

Accepted time states retain physical material Euler histories. Surface
histories lift phi/theta; fuselage histories lift theta/psi. The current
rate map is evaluated at the accepted orientation for BDF1/BDF2, including
unequal steps. Existing saved-state model identities distinguish surface and
body inputs, so this extension does not change temporal policy identifiers.

The existing distributed slender-body aerodynamic wrench uses the same
conservative endpoint transfer as other source aerodynamic loads. Radius
shoulders are concentrated loads at their actual positions; their force and
attachment-arm moment are added once. Moving airflow includes the existing
body apparent-inertia loads without adding another fluid mass matrix.

## Independent checks

The source regression suite passes **630/630** tests, including 23 new
fuselage tests. Six additional rotation/rank/scope invariants pass, for
**636 distinct native tests**. A strengthened nodal fluid-wrench assertion
also passes in a separate rerun of one of those tests. All **205 JavaScript
tests** pass. The seven WASM requests pass **5,806 physical scalar comparisons**
with maximum absolute native/WASM difference 4.94e-13; the final offline
browser scenario passes as well.

The native tests cover:

* Rotation products and their differentiated generators at general angles
  and both x-axis directions, including mixed surface/body meshes.
* The complete differentiated curvature law, general sections, damping,
  moving-frame inertia and sparse/dense/full-residual derivative agreement.
* Axial extension, finite bending and torsion, with independent endpoint
  integration; fixed and free two-mass spring modes and harmonic responses.
* Closed/open radius-shoulder force and moment, a cylinder pressure-integral
  apparent wrench, and a body/wing aircraft joined by a rigid joint.
* Multiple-turn Euler histories, noncommuting unequal-step BDF1/BDF2 motion,
  checkpoint continuation, and the unchanged still-air body rejection.
* An independent rigid-body balance matrix and its numerical rank. The
  analytic certificate retains its exact-orthonormal-frame scope; ordinary
  trigonometric roundoff still invokes the numerical fallback.

The powered transient has a massless axial spring of stiffness 100, a root
mass of 2 and a tip mass of 3, in input units. With a unit force step on the
tip and free-frame motion, the exact relative tip displacement is
`(1 - cos(sqrt(250/3)*tau))/250`, where tau is time since the step. Halving
the BDF2 step from 0.005 to 0.0025 reduces the maximum normalized combined
displacement/velocity error from **0.161923% to 0.040586%**. The normalization
uses the exact response amplitudes, not division by a near-zero instantaneous
response. Resuming a checkpoint reproduces the uninterrupted discrete history.

Seven public-API requests cover prescribed/free harmonic response, flowing-air
and vacuum modes, the transient, axial static equilibrium, and body shoulders.
The WASM harness compares physical outputs to native results and repeats the
independent spring and body-wrench checks. The offline browser scenario adds
frequency samples using reused matrices, continues a checkpoint, saves and
reopens frequency/time/modal solutions, and checks the mobile layout.
Completed run counts, source hashes and bundle verification are recorded in
the [machine-readable evidence](source-fuselage.json).

## Limits retained

The fuselage chart remains singular for vertical spans, and the surface chart
for x-directed spans. Spatial Euler branch cuts, stepped axes, and shared-node
orientation breaks in source time integration remain unsupported. The separate
fixed still-air fluid operator still supports lifting surfaces only. Feedback
and inverse actuator/history targets remain outside the source airflow scope.
The default numerical policy is unchanged.

Historical ASWING finite-difference sampling conventions and full-aircraft
reference equivalence are unverified. These tests establish the stated
equations and runtime behavior; they do not add an ISAE pass or resolve the
SA-1/4/5 aerodynamic differences. `ISAE_STATUS.md` is unchanged.

Sources: [steady Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
[unsteady Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
