# Daedalus: principal bending axes and zero-lift orientation

The literal aircraft's structural twist, bending coupling and aerodynamic
zero-lift orientation pass this independent check. No omitted or duplicated
principal-axis rotation was found. This adds evidence about the existing
implementation; it does **not** improve or validate the unmatched rudder Bode
curve, and no production property or equation was changed.

## Sources and convention reconciliation

The [authoritative index](aswing-authoritative-references.md), source catalog
and [1989 paper record](isae-st4-node-placement-sources-20261109.json) were
consulted. Original pages are rendered in the
[inspection](../../artifacts/daedalus-section-axes-20261114/inspect/) and
[relation](../../artifacts/daedalus-section-axes-20261114/relations/) directories.

| Source | Relevant definitions |
| --- | --- |
| Drela 1989 wing-load paper, PDF pp. 2–3 / printed pp. 323–324 | Figures 2–3, Eq. 1 and Eqs. 9–14: fore/aft slope, principal axes and rotated bending coefficients |
| Steady Technical Description, pp. 6–11 | Eq. 13: moment signs; Eqs. 24–26: stress integrals; Figure 5 and Eqs. 30–45: alternative section representations |
| Steady Technical Description, pp. 32–33 | Eq. 154: Glauert midpoint position; Eqs. 158–159: zero-lift normal and control offset |
| [Official user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt), Distribution Block table | `twist` is unloaded structural twist; `alpha` is the zero-lift-line offset relative to the section c axis; omitted `EIcn` is zero |

Near the root, `dae.asw` supplies **twist = 8.2°**, **alpha = 1.4°**,
**EIcc = 50,300**, **EInn = 1,650,000**, **GJ = 40,800 lb ft²**, with no
cross-stiffness entry. Its c,n axes therefore coincide with its declared
principal bending axes. The unloaded zero-lift line has **9.6° incidence**
relative to the aircraft x axis. This does not identify the physical airfoil's
geometric chord incidence independently of its zero-lift angle.

For the straight unloaded root, c points aft/down:
`c = (cos(theta), 0, -sin(theta))`. Expressing the principal bending stiffnesses
in the aircraft x,z axes gives the following physical moment/curvature matrix:

```
[ Mx ]   [   82,842.717   225,830.814 ] [ kappa_x ]
[ Mz ] = [  225,830.814 1,617,457.283 ] [ kappa_z ]
```

The positive off-diagonal value does not contradict the negative coefficient
in the older paper's Eq. 13. Its positive fore/aft slope is
`phi = du/ds` (Eq. 1), so near a straight beam `kappa_z = -phi'` and the
conjugate generalized moment is the negative of physical Mz. Applying this
sign change to both moment and curvature produces the older matrix with
off-diagonal **-225,830.814**. It agrees with Eqs. 12–14 to **5.83e-11 lb ft²**.
Mixing these two conventions would introduce an erroneous sign reversal.

## Modern Eq. 43: inverse rotation versus twist increment

The rendered modern p. 11 confirms the printed expression
`theta_bend = 0.5 atan(-2 EIcn / (EInn - EIcc))`.
For a section with the above principal properties and an 8.2° principal-axis
tilt relative to a reference frame, the stress-integral tensor has positive
EIcn. The printed expression gives **-8.2°**.

This angle diagonalizes the tensor when used in the **inverse/passive**
transformation `R(theta) E R(theta)^T`. If instead it is added to the physical
twist as in Eq. 30, the necessary tensor transformation is
`R(theta)^T E R(theta)`; the same -8.2° leaves a cross term of **433,285.312
lb ft²**, rather than zero. Using +8.2° gives the original principal values.
The eigenvalue relations in Eqs. 44–45 are unaffected.

This records a signed-angle conflict between the printed conversion and the
twist convention when those formulas are applied together. It does not prove
how any native ASWING utility interprets the angle. OpenSwing takes the file's
stiffness entries and twist directly; it does not apply Eq. 43 to `dae.asw`.
There is no basis here for reversing the input twist or cross-stiffness sign.

## Independent calculation on the actual aircraft

The check constructs four symmetric, weighted axial fibers whose stress
integrals reproduce each section's specified bending stiffnesses. Their
strain is `epsilon = kappa dot (r cross span)`, and their integrated moment is
`sum(EA * epsilon * (r cross span))`. A separate GJ term supplies torsion.
These fictitious fibers are an independent constitutive oracle, not a claim
about actual spar shape, mass or axial stiffness. No production stiffness
inverse or local compliance function is used to construct this oracle.

Five finite section orientations also check the production compliance law
with explicitly nonzero cross-stiffness. The maximum compliance difference
from the independent tensor is **3.22e-20** in the corresponding input units.

On the original physical 6.7 m/s trim, the check covers **all 28 wing
intervals**. Endpoint-averaged material properties follow the declared
source-discrete quadrature. Endpoint frames are independently reconstructed
from the literal 8.2° jig frame and current rotations. Global section moments
are applied to the independent fiber tensors, then transformed to material
curvatures and averaged. Those curvatures are compared with the actual
source residual's constitutive values.

The same comparison is repeated at positive/negative perturbations along both
real and imaginary parts of the retained full **2,044-state** rudder response
at 1.157378 Hz, including its velocity, rate and control perturbations.

| Comparison | Maximum error |
| --- | ---: |
| Material curvature, five states | 8.14e-18 absolute; 5.16e-16 relative norm |
| Material curvature directional derivative | 2.52e-10 relative norm |
| Wing zero-lift normal, five states | 5.56e-16 per component |
| Zero-lift normal directional derivative | 2.23e-13 per component |
| Deliberately omitted jig twist, negative control | **13.76% curvature error** |

The aerodynamic comparison captures the normal actually used by the physical
circulation residual. Its independent construction rotates the combined jig
twist/zero-lift offset using SciPy's rotation interpolation, rather than the
production rotation exponential/logarithm. This verifies the implemented
orientation and sign handling. It does **not** establish that native ASWING
uses the same interpolation between nodes; the documented Glauert-position
rule and the choice of angular/rate interpolation remain separate questions.

## Evidence and scope

Driver: [check_daedalus_section_axes.py](../../scripts/check_daedalus_section_axes.py).
Results: [audit JSON](../../artifacts/daedalus-section-axes-20261114/audit/result.json),
[arrays](../../artifacts/daedalus-section-axes-20261114/audit/arrays.npz),
[verification receipt](../../artifacts/daedalus-section-axes-20261114/verification.json).
All three bounded serial jobs succeeded and were reaped. The numerical audit
records five detailed full source-residual probes, in addition to setup.
Limits remain one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall
seconds. No new aircraft model, frequency sweep, Bode pass count, ISAE fraction
or production change is claimed.
