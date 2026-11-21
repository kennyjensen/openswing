# Conditional CASEI metric and force follow-up

The literal CASEI file removes several uncertainties left open by the first SCN audit. Its geometry has **y=t, z=0, zero twist**, and an in-plane curved axis with `x≈−chord/4`. The 81 geometry records are at `CASEI.asw:40–121`; the largest `|x+chord/4|` from their decimal values is about 1.5e-7 m. Mass and additional mass are zero. The zero stiffness inputs denote rigidity under the manual's explicit convention (`aswing_doc.txt:1200–1204`). `Cdf=Cdp=Cm=0`, zero-lift angle is zero, and the largest displayed cl in the three tables is 0.9172, below the literal 1.5202 upper limit. Prescribed profile drag, weight and large twist corrections therefore are not free explanations, conditional on this model producing these outputs. Smooth stall leakage is not claimed identically zero.

The model-to-output pairing remains conditional. The retained `SCN_ellip.sh` names CASEI and these output filenames, and their names/reference quantities agree, but there is no saved execution receipt binding those exact bytes to the tables.

## Geometry metric check

The manual explicitly defines t as an arbitrary parameter (`aswing_doc.txt:1061–1062`). Here it equals **jig y**, not arc length. Theory p.45 derives arc length from the Cartesian input coordinates (`asw_theory.txt:2257–2261`). Since x varies, even the unloaded arc length is greater than delta-t. Native y also differs from jig y near the tips.

The independent diagnostic evaluates the documented box geometry rule, `delta-r=(s_i+s_(i+1))*delta-s0/2`, from the center ground point. It uses a natural cubic spline through the literal x(t) records, y=t, and arc quadrature split at every original knot. Natural endpoint conditions are **declared**, not recovered historical settings. No aerodynamic influence or equilibrium solve is involved.

| Saved resolution | Native positive tip y | Box-rule tip y | Maximum absolute y error over positive half | Rows within 0.00005 m using central printed t |
|---|---:|---:|---:|---:|
| N6 | 0.9452 | 0.9497468941 | 0.0045468941 | 1/3 |
| N12 | 1.0092 | 1.0111481572 | 0.0019481572 | 3/6 |
| N96 | 1.0268 | 1.0267844480 | 0.0000987077 | 44/48 |

The computed half-arc is 1.0406829384 m, versus input tip t=1.0277. The box rule explains much of the coarse geometric contraction but does **not** reproduce all saved coordinates at printed precision. Exact unprinted nodes and historical spline endpoint conditions remain unresolved. The counts above use central t tokens; they are not a rigorous propagation of t rounding. Every interval and coordinate error is retained in `metric-report.json`.

## What the force fields establish

Conditional planarity and zero twist make the local normal the body z direction. Consequently a freestream lift-axis projection is not automatically needed for the manual's stated wing-normal `f_aero`. The header's distinct freestream-normal Lift is consistent with `Fz*cos(alpha)−Fx*sin(alpha)`; this does not establish that every `f_aero` entry is that lift-axis magnitude.

There is a stronger rejection than simply using the wrong parameter metric. For N6's first positive interval (`ellip_A8_N6.txt:38–39`), the printed `Fn` decrement divided by `f_aero` implies an effective interval length in **[0.40068600, 0.40072369] m**, including both columns' printed rounding. Yet the minimum possible printed delta-y is **0.40290 m**. Every physical arc must be at least its y displacement. Thus **no arc-length correction can make a single product `f_aero_i*delta-s_i` equal this normal-force increment** under those stated interpretations. The same lower-bound rejection holds for 2/3, 4/6 and 14/48 positive-half intervals at N6/N12/N96. This argument does not depend on the natural spline boundary conditions.

For completeness, using the diagnostic natural-spline arc gives integrated `f_aero*ds` values 82.7766862, 89.2828364 and 91.4414827 N, versus saved Fz 82.15, 88.69 and 90.85 N. Applying the particular alternative factor cos(8 degrees) gives 81.9711092, 88.4139420 and 90.5515805 N. Neither is identified as the native transfer rule. A local flow angle cannot be replaced by freestream alpha: Eq.67 uses the local bound-vortex velocity.

The displayed cl does not independently close that missing local-velocity information. If `f_aero` were a lift **magnitude**, Eqs.67 and 202 would give `V_perp^2=2*f_aero/(rho*c*cl)`. If it is the documented normal **component**, they instead give `f_aero=(rho*c*cl/2)*V_perp*V_c`. These are different relations. Neither reconstructs the unprinted velocity direction or proves that the reported samples are the exact densities used by structural quadrature. Selecting one from proximity to the desired force would be unjustified.

This follow-up narrows the boundary to the exact native diagnostic projection/sample recovery, internal discrete load transfer, and historical geometry interpolation. It removes arbitrary-t, prescribed profile drag, mass and twist as interchangeable explanations under the conditional CASEI model. It establishes no production defect and changes no SA1 acceptance result.

`metric-analysis.py` is stdlib-only. Linear-spline derivative, scalar quadrature and unit-tangent checks passed; the report also retains the arc quadrature refinement difference between 1e-11 and 1e-13 tolerances, plus hashes of the script, model, driver, three native tables and primary documents.
