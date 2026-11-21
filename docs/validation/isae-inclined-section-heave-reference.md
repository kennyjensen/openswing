# Independent section reference at nonzero mean incidence

The [primary UA-1 paper](https://purehost.bath.ac.uk/ws/files/152831878/aiaa_2017_Nicola_Chiereghin_BathUni_full_paper.pdf),
Sections II and II.B (PDF pages 3–4), specifies plunge normal to the fixed
freestream and measures lift in that same direction. The
[source record](../../artifacts/isae/ua1-incidence-20261101/source-review.json)
preserves that binding. At nonzero incidence, this direction differs from the
section normal. This reference keeps both directions explicit.

It specializes the [steady description](../../.reference/asw_theory.txt),
Eqs. 155–157, and the [unsteady description](../../.reference/asw_uns_theory.txt),
Eqs. 34–35, 43 and 49. It imports no production geometry, vortex, load,
residual or time-integration routine. The model is an infinite straight
section with slope 2π, no stall, Mach zero and no profile-drag coefficients.
It does not recover a native ASWING deck or a measured unsteady polar.

Take chord/span/normal axes along x/y/z. With constant geometric incidence α,
define the fixed mean-flow and plunge directions

`e = (cos α, 0, sin α)`,

`H = (−sin α, 0, cos α)`.

Displacement is `z(t) H`, with `z(t)=(A/2) cos(ωt)`, `w=z_dot`,
`a=z_ddot`, and `ω=2Vk/c`. A is peak-to-peak displacement. Relative incident
flow is

`v = V e − w H = (V cos α + w sin α, 0, V sin α − w cos α)`.

Write its chordwise and normal components as `v_x` and `v_z`. Its magnitude
is `U=sqrt(V²+w²)`, and the effective incidence is `α−atan(w/V)`.
For this infinite-span specialization, bound-line self-induced velocity
vanishes. Steady Eqs. 155–157 place the control point `c/2` downstream along
the instantaneous incident wind. Integrating the infinite spanwise bound
vortex gives normal induced velocity `−Γ v_x/(π c U)` there.

The unsteady tangency equation therefore becomes

`v_z − Γ v_x/(π c U) − 2 Γ_dot/(π U) = 0`,

or

`Γ_dot + [v_x(t)/(2c)] Γ = (π/2) U(t) v_z(t)`.

The finite-motion equation is linear in circulation but has time-dependent
coefficients and nonlinear dependence on the prescribed motion. The local
wind direction is updated throughout the motion. A constant small-signal
coefficient matrix would be a different approximation.

An independent integrating-factor primitive is

`Λ(t) = [V cos α t + sin α (z(t)−z(0))]/(2c)`.

For initial circulation `Γ0`, quadrature evaluates

`Γ(t) = exp(−Λ(t)) Γ0 + integral_0^t exp(Λ(s)−Λ(t)) (π/2) U(s) v_z(s) ds`.

For the pre-motion attached steady state, `Γ0=π c V tan α`. Thus a nonzero
mean-incidence startup does not start from zero circulation. For a periodic
state of period T, the integral contribution at T is divided by
`1−exp(−V cos α T/(2c))` to obtain the periodic initial circulation. Adaptive
DOP853 and Radau integrations separately calculate that one-period contribution
and then evolve the solution. No production trajectory initializes the reference.

The circulatory and circulation-rate force per unit span is

`f_circ+rate = ρ (Γ+c Γ_dot/U) (−v_z,0,v_x)`.

With no rotation, Eq. 43 gives

`f_apparent = −(π/4) ρ c² a cos α (0,0,1)`.

Projecting onto the fixed plunge direction and normalizing by `ρ V² c/2`
gives

`CL = 2 Γ/(V c) + 2 Γ_dot/(V U) − π c a cos² α/(2V²)`.

Both factors of cosine matter in the apparent-mass term: acceleration is
first projected onto the section normal, then force onto the measurement
direction. The implementation also retains all three force components and
the coefficient reported in instantaneous wind axes. That instantaneous
coefficient uses a different direction and dynamic pressure; it is not the
fixed-axis lift used for this comparison. The tangency-squared profile term
vanishes on the differential solution and is retained for arbitrary supplied
circulation-rate checks.

Checks cover the earlier zero-incidence limit, the steady `CL=2π tan α`
limit, periodic closure, agreement of three integration methods, and the
sign-reversal/half-cycle symmetry. Production instantaneous checks evaluate
both a flat section with inclined incident flow and the equivalent rotated
section with horizontal mean flow; force vectors are transformed back before
comparison. Circulation, circulation-rate and apparent-mass contributions
are checked separately.

Implementation: [independent reference](../../scripts/isae_ua_incidence_reference.py),
[production probes](../../scripts/isae_ua_incidence_production.py),
[focused tests](../../tests/test_isae_ua_incidence_reference.py), and
[results](isae-ua1-incidence-20261101.md).
Finite-span effects, stall, compressibility, pitching motion and production
time-integration accuracy are separate requirements.
