# Daedalus: curvature discretization has a small direct Bode effect

The alternative matrix curvature form has now been tested in complete coupled
harmonic solves on both saved aircraft meshes. At the reference dip frequency,
**1.157378 Hz**, it changes yaw amplitude by **+0.00360%** on the original mesh
and **+0.000882%** on the refined mesh. It does not explain the native Bode
discrepancy. OpenSwing retains Drela's preferred Euler-angle formulation.

These are controlled **fixed-equilibrium** diagnostics. A constant residual
offset preserves each original equilibrium while the curvature derivative
changes. They are not retrimmed alternate aircraft or native ASWING passes.
No production code, physical input, or ISAE completion fraction changed.

Both saved aircraft use the explicitly selected **`drela-moving-airflow-v1`**
equations and **`drela-segspl-v1`** interpolation. This does not establish the
same result for an ordinary browser launch: the absent-policy default in
[numerical-policy.js](../../web/numerical-policy.js) remains `midpoint-v1` with
`natural-v1` interpolation. The older physical-mesh project supplies source
text and settings to the diagnostic driver, which explicitly reconstructs the
source-equation network; that project alone does not select this policy.

![Curvature-form response changes](../../artifacts/daedalus-curvature-form-20261114/report/curvature-response.png)

Lines connect only the three sampled frequencies; no continuous frequency
sweep or spectral completeness is claimed.

## Why this comparison was made

The [original independent structural audit](daedalus-source-strain-20261114.md)
already checked the full coarse compatibility Jacobian. The present work
reuses its independent rotation/material construction and extends the
rotation-row check to the refined aircraft. It then measures an actual
coupled-response effect of a discrete-form choice, rather than repeating the
coarse derivative audit alone.

Drela's [steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
**printed page 13, Eqs. 52–54**, gives matrix and Euler-angle curvature
forms. It states that their discrete versions agree to second order and
prefers the Euler form near large changes of section orientation. The
[authoritative catalog](aswing-authoritative-sources.json) identifies the
retained PDF; pages 5 and 13 were visually inspected again.

There is a pre-existing normalization inconsistency in the printed tensor
cross-dot definition, also recorded in the [ST-5 source review](isae-st5-source-discrete.md).
For a unit rotation about one axis, literal Eqs. 6–7 give a curvature component
of two, whereas Eqs. 5 and 8 give one. This diagnostic uses the matrix
curvature **normalized to Eqs. 5/8**, equivalently half the literal Eq. 7
cross-dot. It does not assume that a factor-of-two bending law is native
ASWING behavior. The three Cartesian generator checks retain this distinction
in the assembly results.

## Independent derivatives and retained coupling

For local-to-body endpoint frames `Ra` and `Rb`, the normalized discrete
matrix curvature integral is

```text
k52 = axial(Ra.T @ Rb),
axial(X) = [X32-X23, X13-X31, X21-X12] / 2.
```

Its spatial-rotation derivative is

```text
dk52 = axial(Ra.T @ (skew(theta_b)-skew(theta_a)) @ Rb).
```

The current Euler form uses the endpoint-average curvature map and angle
difference. The independent construction forms those maps by differentiating
the printed rotation products, rather than using production angle/map code.
Its derivative includes the change of the average map as well as the angle
difference. Loaded internal moments contribute through the derivative of
their average section-frame transformation; that constitutive contribution
is retained in both variants.

| Check | Original mesh | Refined mesh |
| --- | ---: | ---: |
| Complete descriptor coordinates | 2,044 | 3,980 |
| Independently checked rotation rows | 309 | 618 |
| Maximum current matrix-entry discrepancy | 1.365e−11 | 2.233e−10 |
| Maximum alternative derivative difference at two widths | 8.660e−14 | 8.383e−14 |
| Maximum Euler response to a superposed unit rigid rotation | 9.450e−6 | 1.793e−6 |
| Matrix-form response to that rigid rotation | 0 | 0 |

The last two rows refer to integrated curvature kinematics, not aircraft
response or physical strain energy. They expose a small finite-grid frame
dependence of the Euler discretization; they do not establish a production
implementation error. The alternative derivative is checked with fourth-order
centered rotations at **1e−3 and 5e−4**. The complete current rotation-row
comparison includes zero dependencies and all internal-moment columns.

Only endpoint angular columns in curvature rows change. Constitutive terms,
all force balances, aerodynamic coupling, circulation, inertia, constraints,
input maps and output maps are retained. The largest required constant
curvature residual offset is **1.872e−5** on the original mesh and **3.559e−6**
on the refined mesh. Those nonzero offsets are why this is not presented as
a physically retrimmed solution.

## Full coupled responses

The modified operator is `Aalt = A + D`, where `D` is the independently
constructed curvature-kinematic difference. At each frequency, solve the
complete modified pencil. A second right-hand side checks

```text
(i*omega*M - Aalt) * (zalt-zoriginal) = D*zoriginal.
```

Thus the reported result includes all repeated linear feedback from the
changed curvature equations. No mode or structural state is dropped. Exact
existing beam/velocity elimination factors **748 / 1,448** coordinates and
recovers all **2,044 / 3,980** coordinates.

At **1.157378 Hz**, signed amplitude changes from the current Euler form are:

| Output | Original mesh | Refined mesh |
| --- | ---: | ---: |
| Yaw rate | +0.003601% | +0.000882% |
| Roll rate | −0.029940% | −0.008065% |
| Sideslip | +0.002998% | +0.000751% |
| Bank | −0.035285% | −0.009239% |

Original-mesh yaw changes from **0.07421777 to 0.07422045 deg/s/F3**. The
published drawing remains **0.03398619 deg/s/F3** there. Refined-mesh yaw
changes from **0.07405681 to 0.07405746**. The reference discrepancy is
essentially unchanged and slightly worsens in both fixed-base diagnostics.

Across all four outputs at **0.1, 1.157378 and 1.5 Hz**, the largest amplitude
change is **0.04038%**; the largest complex response change relative to the
original amplitude is **0.08950%**. At 1.5 Hz, original-mesh roll amplitude
changes −0.04038%, compared with −15.915% from the earlier full mesh refinement
and retrim. The alternative curvature form is a small direct contribution
under these conditions. This does not bound an uncomputed physical retrim.

The minimum modified full-pencil reciprocal-condition estimate is
**6.153e−9**. Maximum full harmonic residual is **9.420e−17**; the exact
correction identity closes within **2.006e−16**. Existing condition,
backward-error and scaled-residual gates are unchanged.

## Consequence and evidence

Both [position compatibility](daedalus-position-compatibility-20261114.md)
and rotation/constitutive derivatives now agree independently on both meshes.
The tested curvature-form choice has very little direct effect on the
published dip. No evidence here supports changing stiffness or changing the
preferred Euler formulation to fit the drawing.

The next useful distinction is how distributed aerodynamic loads are sampled
and averaged before they enter the structural equations. Conservation of the
transferred wrench and correct differentiation of the chosen quadrature are
already checked; those facts alone do not establish historical ASWING's
sampling convention. Audit that convention against the references before
constructing any alternate model. The native operating setup remains unknown.

The [bounded driver](../../scripts/check_daedalus_curvature_form.py),
[combined results](../../artifacts/daedalus-curvature-form-20261114/report/result.json),
[response CSV](../../artifacts/daedalus-curvature-form-20261114/report/curvature-response.csv)
and [verification receipt](../../artifacts/daedalus-curvature-form-20261114/verification.json)
retain the evidence. All **11 numerical jobs succeeded and were reaped**.
There are six modified full-state responses and six correction solves,
sharing one exact factorization per frequency. A separate bounded utility
rendered the two source pages for visual inspection.

Each numerical child used one BLAS thread and limits of **512 MiB address
space, 15 CPU seconds and 25 wall seconds**. Maximum recorded numerical use
was **2.700 CPU seconds, 4.603 wall seconds and 234.141 MiB resident memory**.
The plot was visually checked. Browser/build jobs remain held; ISAE fractions
and scopes are unchanged, so no progress event is added.
