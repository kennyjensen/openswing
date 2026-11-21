# Independent straight-wing heave reference

This reference specializes Drela's documented equations to the UA-2 rigid,
rectangular AR10 reconstruction. It imports no OpenSwing mesh, vortex kernel,
residual, force routine or time integrator. Its purpose is to check the spatial
implementation and time integration independently. It is not a recovered
native ASWING model or an alternative aerodynamic theory.

The [steady description](../../.reference/asw_theory.txt), Eqs. 155–160, places
the bound vortex at quarter-chord and the control point downstream along the
instantaneous incident wind. With section slope 2π, the offset is `h=c/2`.
The [unsteady description](../../.reference/asw_uns_theory.txt), Eqs. 34–35,
43 and 48–49, supplies circulation/rate lift, apparent mass and local shed-wake
lag. In this model the chord is one, mean incidence and Mach are zero, stall
is disabled, and the straight span axis is +y. There are no bodies, jets,
ground images or profile-drag coefficients. The `.asw` Ground record anchors
the beam; it does not enable aerodynamic ground images.

For full span b and N strips, independently constructed cosine nodes and
Glauert midpoint samples are

`y_j = -(b/2) cos(pi*j/N)`,

`y_i* = -(b/2) cos(pi*(i+1/2)/N)`.

Strip widths are `Delta_y_j = y_(j+1)-y_j`. Define pairwise distances
`s_a = y_i* - y_j` and `s_b = y_i* - y_(j+1)`. Integrating the finite bound
segment and its two semi-infinite trailing legs gives two scalar matrices:

`H_ij = (1/s_a - 1/s_b)/(4*pi)`,

`C_ij = [(h+sqrt(h^2+s_a^2))/s_a - (h+sqrt(h^2+s_b^2))/s_b]/(4*pi*h)`.

H gives the induced velocity at the bound line; collinear bound segments
contribute zero there. C includes the finite bound segment and both trailing
legs at the control point. The physical beam uses zero vortex core, as in the
declared production convention. The scalar integrals are checked separately
against numerical Biot–Savart line integration, including adjacent strips.

For body heave velocity w, the incident vector is `(V,0,-w)`, its magnitude is
`U_inf=sqrt(V^2+w^2)`, and its unit vector is `(e_x,0,e_z)`. Both induced fields
point along `(e_z,0,-e_x)`. Therefore the scalar C/H matrices remain constant
for this particular geometry while their physical directions rotate with the
wind. This reuses the integrals without invoking the frozen-influence K/F
approximation.

Writing `D=H Gamma`, the bound-point relative velocity is

`v_bound = (V+e_z D, 0, -w-e_x D)`,

`U_perp = sqrt(U_inf^2 + D^2)`.

The control-point tangency velocity and differential circulation equation are

`T = -w - e_x C Gamma`,

`Gamma_dot = (pi/2) U_perp T`.

Products involving U_perp are pointwise. The local speed includes induced
bound-vortex flow. Replacing it by incident speed would change the nonlinear
equations. No constant small-signal matrix is substituted for this dependence.

With heave acceleration a, fixed-direction vertical lift is

`CL = 2/(V^2*b*c) sum_i Delta_y_i * [(Gamma_i+c*Gamma_dot_i/U_perp_i)*v_bound,x,i - pi*c^2*a/4]`.

The terms are circulatory lift, circulation-rate lift and apparent mass. The
tangency-squared profile term vanishes on this ODE solution. The implementation
also retains it for off-solution residual/load identity tests.

At zero motion and circulation, the normalized residual linearizes to
`K=-C/V` and `M=-2/(pi*V^2) I`. These are checked against the previously saved
production matrices. Additional tests verify production node/sample positions
and nonlinear residuals and loads at finite positive/negative heave velocities.
The independent reference uses DOP853 and Radau and checks their agreement.

The finite circulation samples approximate a continuous elliptical distribution;
they do not reproduce its continuous downwash exactly at a finite N. The test
requires mesh convergence to that limit and applies no empirical correction.

Implementation: [independent equations](../../scripts/isae_ua_wing_nonlinear.py),
[quadrature, geometry and load tests](../../tests/test_isae_ua_wing_nonlinear.py),
and [two-method reference builder](../../scripts/verify-isae-ua2-nonlinear-reference.py).
This specialization does not establish correctness for swept/deformed wings,
stall, compressibility, engines, moving wakes beyond Drela's stated approximation,
or the unresolved historical UA-2 native setup.
