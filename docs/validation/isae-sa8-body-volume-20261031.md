# SA-8 body interference isolated

2026-10-31. The full-aircraft negative-incidence difference is largely isolated
to body-induced flow. Suppressing that velocity contribution in a diagnostic
process raises the fixed-strength-20 comparison from **220/252 to 244/252**,
with 24 gained checks and no losses. All 36 states complete. Body geometry,
body forces, current vortex geometry, section properties and the 3% policy
remain unchanged.

This is an ablation of the published physics, not a production correction.
An independent exact integral verifies that OpenSwing implements the body
velocity correctly for this geometry. The evidence points toward different
body-interference treatment in the producing setup or native implementation;
it does not authenticate which option or algorithm produced the archive.
The original registered SA-8 baseline remains 373/504.

**2026-11-01 source follow-up:** the authors report a constant-cross-section
body-doublet issue in their SA-14 discussion. This is consistent with the SA-8
geometry and the ablation below, although it does not authenticate the producing
executable. See the [source and saved-comparison audit](isae-sa8-native-body-report-20261101.md).

![Isolated body-flow comparison](../../artifacts/isae/sa8-body-volume-20261031/body-flow-comparison.svg)

## Independent equation check

The archived full model has a longitudinal, constant-radius body at
y=0, z=−0.0645 m, from x=−0.1 to 0.95 m, with radius R=0.0645 m.
Those constants are verified directly from the input text, independently
of the OpenSwing parser. With incompressible flow at incidence alpha,
equation (162) gives zero source density and doublet density

`nu = 2 pi R² sin(alpha) ez`.

The regularized velocity in equation (163), with core R/2, has a closed-form
integral along this straight segment. A standard-library implementation
checks **41,760 captured original velocity vectors**, including own-body
exclusions. Its maximum difference from production quadrature is
**1.83e−16 times freestream speed**. Six independent composite-Simpson
calculations also check the closed form. The oracle does not call the
production pair kernel or quadrature.

The same mathematical check is now a permanent regression test in
[tests/test_volume.py](../../tests/test_volume.py). Three incidence cases
cover negative, zero and positive body crossflow, including points near the
regularized core and body ends. Those tests and the existing body-quadrature
test pass: **4 passed, 11 deselected**. Existing quadrature integration used
the production pair kernel; the new test supplies an independent check of
that kernel as well.

## Remaining comparisons

After the velocity ablation, all remaining failures on both registered
meshes occur at −4°. On the fine mesh:

| Output | Archived ASWING | Volume-off diagnostic | Absolute percentage error |
|---|---:|---:|---:|
| Lift | −1.93238 | −1.826044 | 5.50% |
| CL | −0.00643162 | −0.006077699 | 5.50% |
| CDi | 0.00000151247 | 0.000001355236 | 10.40% |
| CM | 0.0175089 | 0.01615319 | 7.74% |

The eight failed scalar checks are these four outputs on two meshes.
The small lift difference near zero lift produces a larger relative change
in induced drag. Total drag and efficiency pass at every angle in this
diagnostic. The maximum circulation residual is 4.80e−14, and complete
force/moment reconstruction also passes.

A further complete 18-angle run uses 40 OpenSwing intervals, motivated by
the report's stated 40 circulation nodes. It passes **121/126**, versus
122/126 on the corresponding 128-interval scope. The −4° errors remain:
CL 5.02%, CDi 9.66%, CM 6.47%. It also loses the −6° efficiency check,
3.08% high. The exact native station array and node-versus-interval
interpretation remain unrecorded. Mesh size does not resolve this difference.

## Implication for implementation

The report's statement that airframe influence was neglected is consistent
with the direction of this diagnostic, while the archived model still
contains the body. Omitting its induced velocity while retaining its force
contribution is not an authenticated native setting. Strength 20 likewise
remains an unconfirmed native parameter.

Production retains the published volume influence equations. No artificial
correction or selective physics switch was added. The isolated fore-wing
drag discrepancy remains separate: that input contains no body, so this
mechanism cannot explain it. The SA-6 derivative, SA-7 low-lift efficiency
and SA-10 moment/tip-flow work remain within the active SA-6–SA-10 focus.

Artifacts:

- [Complete body-volume ablation and integral audit](../../artifacts/isae/sa8-body-volume-20261031/report.md)
- [40-interval follow-up](../../artifacts/isae/sa8-body-volume40-20261031/report.md)
- [Targeted regression-test output](../../artifacts/isae/sa8-body-volume-20261031/pytest.log)

This turn completes 54 new physical solves and the four targeted tests.
All solver workers terminate successfully. The broader goal remains incomplete.
