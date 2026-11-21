# SA-6 pitch-rate decomposition and Fourier follow-up

2026-10-31. SA-6 through SA-10 remain the active focus. This follow-up does
not resolve SA-6 or change production physics, input models, archived targets,
the provisional 3% comparison rule, or numerical validity checks.

The complete prior frozen-influence / stall-strength-20 diagnostic still
passes **528/528 static**, **528/528 F1**, and **2,780/3,168 state** checks.
Pitch rate accounts for 246 of its 388 state failures. The native settings
remain unverified, so those results are separate from registered acceptance.

## Pitch-rate convention and force audit

All 88 saved states are covered: four paired aileron models, eleven control
settings, and both declared meshes. The 44 native export headers explicitly
use `q c/(2V)`, stability axes with x forward and z down, incidence 12 degrees,
speed 20 m/s, and reference chord 0.254 m. Those quantities are parsed and
checked directly from every header.

A separate calculation, without OpenSwing imports, reconstructs the exact
straight-wing horseshoe operators and differentiates the published lift,
ordinary profile drag, stall drag, and moments. It verifies 8,624 strips:

| Independent reconstruction | Maximum discrepancy |
|---|---:|
| Static local velocity / flight speed | 4.76e-14 |
| All six pitch-rate coefficients | 2.23e-15 |
| Local pitch-rate tangency derivative residual | 7.54e-14 |
| Quarter-chord pitch-moment identity | 6.67e-16 |

This verifies the retained implementation of these equations; agreement
between implementations does not establish agreement with the native solver.
The native pitch-rate comparison remains **282/528**.

Two simple convention hypotheses are ruled out individually:

- A positive scale applied to the entire pitch-rate column cannot pass all
  six outputs at any of the 88 saved states. Exact intersections of the
  admissible scale intervals are empty in every case.
- A translation of the velocity-reference point in x/z, with the force and
  moment origins fixed, also cannot pass all six outputs at any state.
  Each result has an exact rational infeasibility certificate using three
  comparison inequalities. This tests the published affine transformation
  of the saved velocity derivatives, not changes to the moment origin or
  a combined scale-and-origin hypothesis.

Even allowing a different correction at every state, the best maximum
error is at least 2.986 times the tolerance for scaling or 2.946 times the
tolerance for translation. These optimization results are diagnostic lower
bounds; no fitted setting is used for scoring or production.

The force decomposition also explains why small axial derivatives amplify
the discrepancy. For the 15%-chord aileron at 4 degrees on the finer mesh:

| Contribution to CXq | OpenSwing |
|---|---:|
| Direct rotational-velocity lift | +0.58492431 |
| Circulation-response lift | -0.30765602 |
| Direct ordinary profile drag | -0.00233100 |
| Circulation-response ordinary profile drag | +0.00072153 |
| Direct stall drag | -0.36334173 |
| Circulation-response stall drag | +0.05655762 |
| Total | **-0.03112531** |
| Archived ASWING total | **-0.00969000** |

Substantial cancellation occurs between contributions. The discrepancy is
not confined to the small total: on the finest-mesh states, the normal
circulation-force pitch response differs by a median 2.365%, maximum 5.017%,
and the inferred normal profile-force response by 5.922%, maximum 10.592%.
These two native components are inferred from its total forces and moment,
using the literal straight-wing geometry and the published quarter-chord
moment relation; they are not separately printed native quantities.

## Published Fourier closure

Sixteen cold bases and analytic state responses test 20 and 40 sine modes
at the same eight previously declared pilot states: four models, control
settings 4 and 44 degrees, and 128 requested intervals. Frozen influences,
stall strength 20, all section data, references, and gates stay fixed.

| Circulation representation | Static | All state derivatives | Pitch-rate subset |
|---|---:|---:|---:|
| Saved pointwise control | 48/48 | 253/288 | 24/48 |
| 20 Fourier modes | 46/48 | 253/288 | 24/48 |
| 40 Fourier modes | 48/48 | 257/288 | 24/48 |

Twenty modes give seven derivative gains and seven losses, plus two static
axial-force losses. Forty modes give five derivative gains and one loss,
with unchanged static results. Neither gains a pitch-rate check. F1 was
not rerun in this pilot. This sample is not a replacement for the complete
comparison and does not authenticate the native mode count.

Independent straight-wing calculations reconstruct the sine test functions,
weighted equations, complete circulation Jacobian, six input columns,
force/moment partials, and the resulting coefficients. The largest matrix
discrepancy is 2.23e-15 and the largest coefficient discrepancy is 7.11e-15.
The maximum weighted nonlinear residual is 5.93e-15. The maximum **local**
residual is 0.3665: the truncated Fourier formulation converges its weighted
equations and does not enforce pointwise tangency. These measures are kept
distinct.

All 16 physical calls terminate successfully. No new physical solve is used
for the rate decomposition or its exact convention certificates. The
remaining question is the native local aerodynamic/rate response, including
the stall leakage and force contributions; neither a simple rate convention
nor these two Fourier truncations resolves it.

## Retained evidence

- [Rate decomposition and exact certificates](../../artifacts/isae/sa6-rate-decomposition-20261031/receipt.json),
  [per-state analysis](../../artifacts/isae/sa6-rate-decomposition-20261031/analysis.json),
  [verification script](../../artifacts/isae/sa6-rate-decomposition-20261031/verify.py).
- [Fourier result summary](../../artifacts/isae/sa6-frozen-fourier-20261031/report.md),
  [analysis](../../artifacts/isae/sa6-frozen-fourier-20261031/analysis.json),
  [receipt](../../artifacts/isae/sa6-frozen-fourier-20261031/receipt.json).
- Published theory: equations 63, 150 and 201 for Fourier closure; 67, 70
  and 72 for section loads and moments; 203–204 for stall leakage; 220–229
  for integrated loads and normalized stability derivatives. The retained
  theory and inputs are hashed in the diagnostic plans.
