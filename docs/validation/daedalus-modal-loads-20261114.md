# Daedalus: aerodynamic effects on the two cancelling modes

The current tailboom mode's decay is most sensitive to ordinary fin lift.
The current wing mode's decay is more sensitive to the paired circulation-lag
and circulation-rate lift terms. Those two unsteady terms have opposing
effects. Independently constructed rate-load matrices and **16 small perturbed
eigensolutions** verify the corresponding first derivatives.

This is a mechanism check, not a correction or new ASWING reference pass.
The complete yaw response at 1.157378 Hz remains **0.074218 versus 0.033986
deg/s/F3**. Aircraft properties, production equations, defaults and ISAE
completion fractions are unchanged.

![Verified modal sensitivities](../../artifacts/daedalus-modal-loads-20261114/report-v2/modal-load-sensitivity.png)

## Reference and case

Drela's [unsteady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf)
defines ordinary circulation lift in Eq. 34, circulation-rate lift and its
quarter-chord moment in Eqs. 35–36, apparent inertia in Eqs. 43–44, and
shed-wake downwash in Eqs. 48–49. Eqs. 50–56 derive the paired unsteady
approximation with `b = 2/pi`. The [source catalog](aswing-authoritative-sources.json)
and [historical lag-law review](daedalus-historical-lag-sources-20261113.json)
retain the primary references. Their equations give no basis for independently
tuning the two unsteady terms to match a notch.

The two modes and physical deformation classification are from the accepted
[mode-shape comparison](daedalus-mode-shapes-20261114.md). The same literal
public `dae.asw`, source-equation/SEGSPL discretization, 6.7 m/s trim, Mach 0.1,
live influences, aerodynamic lag and plume remain in use. The current poles are:

| Mode | Pole λ, s⁻¹ | Damped frequency, Hz | Damping ratio −Re(λ)/abs(λ) |
| --- | ---: | ---: | ---: |
| Wing-dominated | −4.956795 + 7.869451i | 1.252462 | 0.532964 |
| Tailboom-dominated | −6.939570 + 8.154006i | 1.297750 | 0.648118 |

These full-flight aeroelastic damping ratios are not comparable directly to
the NASA report's approximate 20% estimate for a Light Eagle tailboom mode.
The aircraft, operating condition and model definition differ. No report
coefficient or prototype inertia is substituted into the Daedalus input.

## What was differentiated

For `A v = lambda M v` and a transpose-bilinear left vector `w`, a component's
fixed-equilibrium residual increment gives

`d(lambda)/d(epsilon) = w.T delta_R(v, lambda*v) / (w.T M v)`.

Each diagnostic multiplier preserves the loaded base through an affine offset.
It is not a retrimmed aircraft parameter change. The derivative includes the
coupled response of the full descriptor. It is not a material damping constant,
an additive modal-energy fraction or an independent Bode contribution.

All 2,044 coordinates are recovered before evaluating physical motion and
loads. Fourth-order real/imaginary directional stencils at widths 0.001 and
0.0005 evaluate the external load components. Directions have an arbitrary
one-foot maximum body-relative nodal envelope for numerical scaling; the
eigenvalue derivative is independent of that normalization. The lag term is
also constructed directly from Eq. 49, including the circulation/state scales,
and checked against the saved mass block.

The following entries are the **local first-order changes for a +1% multiplier**.
Positive decay-rate change means faster decay. The shown terms act on the wing
for the wing mode and on the fin for the tailboom mode; the complete output
also retains every other beam, point/engine load, mass/gravity term and stall
residual.

| Component | Wing decay change, s⁻¹ | Wing frequency change, Hz | Tailboom decay change, s⁻¹ | Tailboom frequency change, Hz |
| --- | ---: | ---: | ---: | ---: |
| Ordinary lift | +0.004281 | +0.010506 | +0.048274 | +0.008948 |
| Circulation-rate lift | +0.041812 | −0.005447 | +0.015734 | −0.014401 |
| Shed-wake lag | −0.053667 | +0.002765 | −0.023207 | +0.014058 |
| Apparent inertia | −0.024936 | −0.003524 | −0.032384 | −0.003134 |

For example, the fin rate-lift and lag frequency derivatives nearly cancel
when both coefficients increase together. Removing one term alone would
substantially disturb that relationship. This does not imply that increasing
both is a physically warranted change. Ordinary wing lift primarily changes
the wing mode's frequency in this accounting, despite its smaller decay-rate
sensitivity; small damping sensitivity does not make it irrelevant to the
full response minimum.

## Independent numerical checks

For wing lag, wing rate lift, fin lag and fin rate lift, the separate checker
reconstructs the corresponding mass-matrix component using the independently
evaluated section rate forces and direct endpoint/global wrench transfers.
Rate lift, profile-rate drag and lag sum to the previously checked complete
circulation-rate columns within **2.169e−19**. Profile-rate drag is preserved
in this closure and is not silently included in the rate-lift multiplier.

For each selected term, four fresh sparse eigensolutions use predetermined
changes of **−0.1%, +0.1%, −0.05%, +0.05%**. Exact elimination of the four
unobservable cyclic coordinates is retained; these load modifications have
no rows or columns in those eliminated coordinates. No mode count, shift or
multiplier is chosen by agreement with the Bode drawing.

| Check | Maximum observed value |
| --- | ---: |
| Physical load stencil change | 1.068e−13 scaled residual |
| Component derivative stencil change, normalized by `1 + abs(derivative)` | 1.865e−12 |
| Eq. 49 action versus complete saved lag block | 1.242e−16 |
| Independent rate-block versus load-derived eigenvalue derivative, same normalization | 1.237e−15 |
| Centered eigenvalue derivative error, ±0.1%, same normalization | 5.094e−6 |
| Centered eigenvalue derivative error, ±0.05%, same normalization | 1.274e−6 |
| Perturbed reduced-pencil eigen residual | 1.992e−12 relative |

The fourfold reduction in centered derivative error under step halving is
consistent with the expected second-order truncation error. Full-coordinate
baseline right/left eigen residuals are at most **1.175e−12 / 7.345e−10**.
Complete physical incremental net force/moment closure is within **1.069e−7**
in its respective native units at the arbitrary display amplitude.

## Artifacts and limits

- [Complete results](../../artifacts/daedalus-modal-loads-20261114/report-v2/result.json),
  [CSV](../../artifacts/daedalus-modal-loads-20261114/report-v2/modal-load-sensitivity.csv),
  [SVG](../../artifacts/daedalus-modal-loads-20261114/report-v2/modal-load-sensitivity.svg).
- [Load derivative driver](../../scripts/check_daedalus_modal_loads.py),
  [independent rate-block checker](../../scripts/check_daedalus_modal_rate_perturbation.py),
  [report generator](../../scripts/report_daedalus_modal_loads.py).

Eight serial jobs completed and were reaped: two mode-load evaluations, four
rate-block perturbation checks and two plot renders. The second render fixes
clipped titles/ticks; its numerical report is identical to the first. Every
child used one BLAS thread, a 512 MiB address-space limit, 15 CPU seconds and
25 wall seconds. Browser/build jobs remain held.

The checks support the implementation of the tested unsteady terms. They do
not establish native ASWING damping or identify the historical run's settings.
The next physical issue to distinguish is the ordinary fin-lift feedback and
its coupling to the wing response; treating the observed mismatch as a single
missing or excessive damping coefficient is not supported by this evidence.
