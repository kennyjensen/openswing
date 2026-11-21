# Independent inclined straight-wing heave reference

This extends the [straight-wing reference](isae-straight-wing-heave-reference.md)
to nonzero mean incidence, using the same analytic horseshoe integrals. It
implements the specialization of Drela's equations; it imports no production
mesh, vortex, residual, force or time-integration routine. The reconstructed
rigid wing has AR10, unit chord, zero profile coefficients, zero Mach and stall
disabled. Its historical native UA-2 geometry and run setup remain unverified.

In chord/span/normal coordinates, define mean flow and plunge directions

`e = (cos(alpha), 0, sin(alpha))`,

`H = (-sin(alpha), 0, cos(alpha))`.

Peak-to-peak displacement is A. With `z=(A/2)cos(omega*t)`, velocity `w=dz/dt`
and acceleration `a=dw/dt`, the incident velocity is `u=V*e-w*H`. Write
`u=(u_x,0,u_z)`, `U0=sqrt(V^2+w^2)` and `e_x=u_x/U0`, `e_z=u_z/U0`.
For this straight span, the bound/control scalar influence matrices H_b and C
remain the [previously integrated matrices](isae-straight-wing-heave-reference.md).
Their vector direction is `(e_z,0,-e_x)`, which changes with the instantaneous wind.
This is a geometric reduction, not a frozen-influence approximation.

Let `D=H_b*Gamma`. The bound-point velocity and its span-normal magnitude are

`v_bound=(u_x+e_z*D, 0, u_z-e_x*D)`,

`U=sqrt(U0^2+D^2)`.

Steady Eqs.155–160 place the control point half a chord downstream along the
incident wind. Unsteady Eqs.31–35 use the bound-point velocity in the loads;
Eq.49 supplies the local shed-wake lag with coefficient `2/pi`. Thus

`T=u_z-e_x*C*Gamma`,

`Gamma_dot=(pi/2)*U*T`.

The products are pointwise. Bound-induced speed is retained. At zero motion,
the exact finite-grid attached steady circulation solves

`C*Gamma_steady=V*tan(alpha)*ones`.

It is nonzero at nonzero incidence and is used for the independent cold-start
reference. The production time simulation starts from its own steady solve.

For sensitivity and implicit reference integration, the analytic Jacobian is

`J=(pi/2)*[diag(D*T/U)*H_b-e_x*diag(U)*C]`.

Complex-step differentiation independently checks this Jacobian, including
nonuniform spanwise circulation and positive/negative mean incidence.

Per unit span, the circulatory and circulation-rate forces are

`f= rho*(Gamma+c*Gamma_dot/U)*(v_bound cross span_axis)`.

Unsteady Eq.43 gives the apparent force
`f_added=(0,0,-pi*rho*c^2*a*cos(alpha)/4)`. Projecting the integrated forces
onto fixed H produces measured lift; projecting onto e produces the streamwise
force. Coefficients use the fixed mean dynamic pressure and geometric area.
The apparent-mass lift therefore includes `cos(alpha)^2`. The tangency-squared
force in steady Eq.70 is retained for deliberately off-solution rate tests.

Two reference integrators, DOP853 and Radau, evolve the same independently
derived ODE. Their periodic initial states are found separately by iterating
the one-period map to closure; neither is supplied to production. Agreement
is checked per strip for circulation/rate and separately for total vector
force and fixed-axis lift. A strict 1e-8 relative agreement gate is retained.

At steady startup, an automatic initial-step estimate can sample exactly one
forcing period and see nearly zero derivatives at both ends. An observed
DOP853 trial then spanned the entire period and overflowed internally. The
reference now bounds its first trial by both the forcing period and the local
Jacobian scale, with adaptive error control retained. A 40-strip tip-rate
comparison also required tighter reference tolerances, from 1e-11/1e-13 to
1e-13/1e-15. These changes affect the independent reference integration only;
the failed attempts and their frozen source are retained.

Evidence and measured results are in the [inclined UA-2 report](isae-ua2-incidence-20261101.md).
Implementations: [equations](../../scripts/isae_ua_wing_incidence.py),
[tighter reference integration](../../scripts/isae_ua_wing_incidence_refined.py),
[coordinate-frame production probes](../../scripts/isae_ua_wing_incidence_production.py),
and [focused tests](../../tests/test_isae_ua_wing_incidence.py).

This specialization does not establish swept/deformed-wing accuracy, stall,
compressibility, arbitrary wakes, native ASWING parity, or browser/WASM behavior.
