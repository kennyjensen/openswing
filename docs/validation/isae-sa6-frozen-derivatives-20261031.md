# SA-6: testing the fixed setting hypothesis against derivatives

The later [receiver decomposition](isae-sa6-rate-receiver-split-20261101.md)
separates the two parts of the rejected both-receivers hypothesis below.
The control-point part improves the pilot to 267/288 state and 38/48 pitch-rate
checks, but has one loss; the force-point part loses 14 checks. Neither is
extended or adopted. The complete comparison below remains unchanged.

The complete comparison passes **528/528 F1 derivatives** and **2,780/3,168
state derivatives** at the existing 3% tolerance, under the fixed frozen-influence/
strength-20 hypothesis. All 44 paired archived operating points and both meshes
are covered. The same hypothesis already passes all 528 static comparisons.

| Scope | Registered-setting counterpart | Fixed hypothesis |
|---|---:|---:|
| Static coefficients | 290/528 | 528/528 |
| F1 control derivatives | 194/528 | 528/528 |
| State derivatives | 1,039/3,168 | 2,780/3,168 |

The [complete derivative report](../../artifacts/isae/sa6-frozen-derivatives-20261031/full/report.md)
records 2,080 gains and five losses versus the registered settings. The losses
are roll-moment/pitch-rate checks, about 3.1–3.3% from the reference. These
outputs were not used to choose the coefficient. The native setting remains
unconfirmed; production defaults and registered acceptance remain unchanged.

The [pilot report](../../artifacts/isae/sa6-frozen-derivatives-20261031/report.md)
covers all four paired chordwise variants, controls 4° and 44°, and the finer
128-interval request: 48/48 F1 and 253/288 state checks, versus 18/48 and 92/288.
All 16 analytic calls converge. Each state call shares
one circulation factorization across six input columns. Scalar readers
independently reconstruct the tangent residual, circulation response, wrench
response, fixed-base axis transformation and normalization. Every base also
reproduces the corresponding retained static result within 2e−10.

The [full plan](../../artifacts/isae/sa6-frozen-derivatives-20261031/full/plan.json)
completes both scopes at all 44 archived conditions and both declared meshes:
176 valid analytic outcomes, comprising 160 new calls and 16 exact pilot reuses.
All processes exit successfully and are reaped. The independent scalar replay
verifies every retained tangent and wrench: maximum normalized linear residual
5.13e−14, wrench discrepancy 9.61e−16, and coefficient discrepancy 6.37e−16.

## Remaining differences

All speed, sideslip and yaw-rate derivative checks pass. Incidence and roll
rate each pass 457/528; pitch rate passes 282/528. Of the 388 remaining failures,
246 involve pitch rate. CXq and Cnq fail at every archived condition on both
meshes. Median errors among failed fine-mesh checks are 20.81% for CXq,
18.84% for Cnq, 3.84% for CLq, and 3.96% for Cmq.

The [mesh review](../../artifacts/isae/sa6-frozen-derivatives-20261031/full/mesh-review.md)
finds maximum 64/128 changes of 0.242% of the native reference for CXq and 1.404%
for Cnq, smaller than their typical discrepancies. CLq and Cmq change by at
most 0.114% and 0.123%. Some incidence/roll-rate channels with small references
are more sensitive. These two meshes characterize sensitivity, not asymptotic
convergence or the original producing mesh.

The [complete pitch-rate plot](../../artifacts/isae/sa6-frozen-derivatives-20261031/full/pitch-rate-comparison.svg)
shows all 44 finest-mesh states and the 3% reference bands.

Pitch-rate responses account for most of the remaining failures. At the
15%-chord model's 4° control setting, for example:

| Derivative | Archived ASWING | OpenSwing, fixed hypothesis | Relative difference |
|---|---:|---:|---:|
| CXq | −0.009690 | −0.0311253 | 221.2% in magnitude |
| CLq | 1.99878 | 2.0919463 | +4.661% |
| Cmq | −0.46228 | −0.4854706 | 5.017% in magnitude |
| Cnq | −0.000670 | −0.00192258 | 187.0% in magnitude |

The large axial/yaw percentages have small denominators, but remain genuine
failed comparisons under the unchanged criterion. The complete report
retains other incidence and roll-rate failures, including their error sizes.
No channel or native zero is dropped.

## Independent nonlinear checks

At the 15%-chord/4° and 35%-chord/44° endpoints, fresh cold nonlinear solves
check fractional speed, incidence, sideslip, the three normalized stability-axis
rates, and F1. Both centered step sizes, 2e−5 and 1e−5 in their declared units,
are used: **56 solves and 28 derivative comparisons**. All pass.

The [independent saved-stencil replay](../../artifacts/isae/sa6-frozen-derivatives-20261031/fd-verification.json)
checks physical perturbations, fixed base axes and dynamic pressure, the
coefficient and circulation stencils, and all source/result hashes. Maximum
coefficient-derivative error is 3.46e−8; maximum circulation-derivative error
is 2.32e−7. The gates retain the existing derivative tests' absolute-plus-relative
form: 3e−8 + 5e−6 times coefficient magnitude, and 2e−6 + 5e−6 times
circulation-derivative magnitude. These checks establish consistency with the
nonlinear model, not historical ASWING identity.

The first finite-difference harness attempt stopped while reading an input
path, before any aerodynamic call. Its source, plan, traceback and zero-call
receipt are preserved in `fd-startup-failure`; the corrected run changes only
that path construction. Both processes have been reaped.

## Rejected receiver-location hypothesis

The [saved-matrix diagnostic](../../artifacts/isae/sa6-frozen-derivatives-20261031/receiver-analysis.json)
checks one interpretation of freezing only induced coefficients: sample
rotational velocity at current-wind force/control points from equations
(155–156), while retaining jig-geometry induction. An independent reader
differentiates equations (64), (67), (70), (72), (203) and (204) for the changed
direct velocity, then solves the captured circulation Jacobian for that forcing.
At zero base rates it preserves the static and F1 results and the non-rate
columns. Maximum linear residual is 2.89e−15.

The state result worsens from **253/288 to 247/288**, with six gains and twelve
losses. It therefore supplies no general correction. This is a linear
postprocessing diagnostic on retained base fields, not a modified nonlinear
solver or authenticated native geometry. Production sampling is unchanged.

The native stall coefficient, original discretization and exporter conventions
remain unverified. Production defaults, aerodynamic equations and registered
acceptance counts remain unchanged. SA-6 is not yet a complete validated family.

The later [matrix-precision audit](isae-sa6-matrix-conditioning-20261101.md)
checks all 88 retained state systems. Single-precision solves and output maps
change no decisions; the saved double-precision solve error is far below the
native discrepancy. Increasing linear-solve accuracy cannot supply the missing
matches. This does not authenticate the native arithmetic or assembled model.

The later [material-point kinematics audit](isae-sa6-sa10-corner-kinematics-20261031.md)
also supplies no fix: quarter-chord-only and quarter-chord/control-point
rotational-velocity substitutions reduce the sampled state score from 253/288
to 245/288 and 247/288, respectively, with no newly passing checks.
