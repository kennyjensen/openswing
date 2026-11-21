# Daedalus: current wing/brace response to prescribed root motion

The current source-equation wing mechanics converge toward an independent
continuum calculation. Across the twelve frequency/input comparisons, the
56-interval half-wing has maximum complete-motion error **1.107%** and maximum
root-reaction error **1.296%**. Eight comparisons meet the predeclared **1%**
target for both measures; four remain open at that stricter target. All twelve
are within the user's broader 5% allowance, but no ISAE fraction is changed:
these are new mechanical diagnostics, not archived ASWING cases.

For the supplied complex wing-root motion at the drawing's yaw dip, the
conditional yaw reaction differs by **1.147% on 14 intervals / 0.145% on 28 /
0.052% on 56**. At 56 intervals its phase difference is **0.00196°**. This
weakens a large mechanical root-response phase error as an explanation for the
Bode mismatch. It does not independently validate the supplied root motion,
the aerodynamic feedback or the complete aircraft response.

![Current half-wing component convergence](../../artifacts/daedalus-wing-root-20261114/report-v2/wing-root.png)

[Vector plot](../../artifacts/daedalus-wing-root-20261114/report-v2/wing-root.svg),
[all comparisons](../../artifacts/daedalus-wing-root-20261114/report-v2/comparisons.csv)
and [complete numerical report](../../artifacts/daedalus-wing-root-20261114/report-v2/result.json).
Points are computed grids; connecting lines show their trend. Colors follow
the application's VibeLattice sequence.

## Matched mechanical problem

The [authoritative index](aswing-authoritative-references.md) and checksummed
source catalog were consulted. The governing sources are Drela's
[steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
beam compatibility/constitutive/balance equations and Eqs. 77–83, and
[unsteady extension](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
Eqs. 37–40. The older
[wing/brace comparison](daedalus-wing-brace-dynamic.md) used midpoint/natural
discretization and tip loads; its results are not substituted for this check.

The fixture is the **positive half** of the accepted source/SEGSPL aircraft at
6.7 m/s, from t=0 to 56 ft, with the actual loaded root pose. The initial grid
has 14 intervals. All original nodes survive in the 28- and 56-interval grids.
The literal mass, CG offset, stiffness, 8.2° material twist, brace anchor,
rotating brace attachment, rest length and axial stiffness are retained.
The section has rigid axial/shear directions and zero intrinsic sectional
rotary inertia, coupled stiffness terms and material damping.

The aircraft's accepted **nodal** aerodynamic/gravity forces and couples become
fixed loads in body axes at their original stations. Added nodes receive no
new dead load. The brace remains live, including pretension and its rotating
moment arm; real distributed inertia remains live. Aerodynamic derivatives,
apparent inertia, live gravity derivatives and free-flight-frame motion are
absent. Root dead loads are removed from both component formulations because
they affect only the constant support reaction. This distinction is retained
in the [fixture](../../artifacts/daedalus-wing-root-20261114/prepare/fixture.json).

Six unit root motions are imposed separately: x/y/z translation in feet and
spatial x/y/z rotation in radians. The two frequencies are **0.2 Hz** and the
already digitized **1.15737773741517 Hz** dip. No frequency, physical parameter,
load distribution or comparison tolerance was fitted.

The [comparison plan](daedalus-wing-root-20261114-plan.json) declares twelve
primary cases. For each input/frequency, complete-motion error is the maximum
absolute difference in `[u/56, theta]` over every native node, divided by the
corresponding reference maximum. Reaction error uses `[F, M/56]` similarly.
There is no denominator floor. Both errors must be below 1% for that case to
meet the stricter component target. The actual complex aircraft-root projection
is a derived diagnostic, not another independent case.

## Independent reference and source adapter

The [continuum evaluator](../../scripts/daedalus_wing_root_reference.py) imports
no OpenSwing functions. It independently constructs C2 material splines with
zero third derivative on the end intervals, using knot **second derivatives**;
production uses a first-derivative system. Mid-interval table probes agree
within **1.957e−16** relative to `max(1, abs(value))`. Input parsing remains
supplied by the fixture; this is not a separate parser validation.

The spatial rod integrates position, material frame, internal force/moment and
their tangent. Fixed nodal loads produce exact jumps; the offset brace produces
a live nonlinear jump. Four Newton corrections, each in its own bounded job,
reduce the continuum base residual from 0.4183 to **4.011e−13**, scaled by
100 lb and 5,600 lb ft. A separate tighter integration remains below 1.095e−12.
The continuum brace tension is **352.636751 lb**, versus **349.699385 lb** on
the original source grid.

On each accepted independent base, the dynamic spatial system is
`delta_y' = (A - omega² B) delta_y`. The real-mass block includes CG-offset
translation/rotation coupling. Line rotary inertia is integrated geometrically;
no second finite-segment correction is added. A six-by-six boundary solve
determines root reactions for all six prescribed motions. Tolerances 1e−9 and
1e−11 change the response metrics by at most **2.485e−11**, well inside the
unchanged 1e−6 tightening gate. Every refined node is sampled directly from
the continuous integration; no response interpolation between original nodes
is used for the comparison.

The current solver's 14-interval mechanical tangent is first extracted from
the loaded complete-aircraft equations in four small blocks. A
[compact source adapter](../../scripts/daedalus_wing_root_discrete.py), retaining
production Euler section maps and source endpoint-product real inertia, then
reproduces those six-input responses. Maximum differences are **7.370e−8** in
physical motion and **1.016e−5** in root-wrench components. The corresponding
adapter gates are 2e−6 and 2e−5, respectively. This checks the reduced adapter
before using it for refinement; it is not the independent reference.

The component adapter and continuum share the explicit axial-brace helper.
A [separate production-law comparison](../../artifacts/daedalus-wing-root-20261114/brace-verification/result.json)
checks its force, rotating-arm couple and analytic tangent against production
`strut_load` at all three source equilibria and the continuum equilibrium.
Base-wrench differences are below 1.137e−13 native units; scaled tangent and
derivative-width errors are below 3.425e−10, inside the unchanged 2e−8 gate.
This discloses and checks the shared support law; it does not establish an
unavailable historical ASWING brace implementation.

Each refined source equilibrium is solved under the same fixed loads and root
pose. Accepted scaled residuals are **1.467e−13, 1.937e−10 and 3.102e−10** for
14/28/56 intervals. The largest coordinate difference from the continuum base
decreases **0.26440 → 0.05255 → 0.01959 ft**. Fourth-order derivative widths
1e−5 and 5e−6 agree within **5.182e−11** after using the exact brace tangent.
Minimum scaled dynamic reciprocal condition is **1.155e−6** in the accepted
compact runs, above the unchanged 1e−12 gate. Harmonic residuals stay below
4.0e−13 in their scaled equations.

## Results

The entries below are the **largest error among six root inputs** at each
frequency. Full input-by-input percentages remain in the linked CSV.

| Half-wing intervals | 0.2 Hz motion | 0.2 Hz reaction | Dip-frequency motion | Dip-frequency reaction |
| --- | ---: | ---: | ---: | ---: |
| 14 | 2.536% | 11.510% | 12.212% | 9.873% |
| 28 | 0.673% | 2.624% | 2.894% | 2.844% |
| 56 | 0.183% | 0.742% | 1.107% | 1.296% |

Every individual motion and reaction metric decreases on both refinements.
At 56 intervals the four cases remaining above the 1% target are all at the
dip: root y/z translation and root z rotation have motion errors
**1.086%, 1.096%, 1.107%**; root x rotation has reaction error **1.296%**.
Two refinements do not establish an exact asymptotic order or spectral
convergence away from these frequencies.

Applying the supplied complete-aircraft complex root motion to each component
map gives the following **conditional** positive-half-wing support yaw moments,
in lb ft per native F3:

| Grid | 0.2 Hz | 1.157378 Hz |
| --- | ---: | ---: |
| Independent continuum | 0.261371 + 0.025665i | 4.984856 − 5.349876i |
| 14 intervals | 0.263186 + 0.025862i | 5.042998 − 5.410318i |
| 28 intervals | 0.261642 + 0.025696i | 4.992411 − 5.357300i |
| 56 intervals | 0.261329 + 0.025662i | 4.982464 − 5.346943i |

These are reactions exerted by the support on the isolated half-wing. They
are not the preceding full-wing-to-boom reaction decomposition: the forcing,
airloads and included motion differ. With no damping or live aerodynamics,
the six unit-input maps are real; their complex projection reflects the given
root-motion phases and mechanical mixing. It does not validate aerodynamic
damping or the phase of the supplied full-aircraft solution.

## Retained failures, resources and consequence

All **36 jobs** are terminal and reaped: **33 succeeded**, and three diagnostic
attempts rejected before producing accepted results. The first reference probe
incorrectly requested every property's spline at another property's exact
breakpoint; selecting only the probed property fixed that adapter issue.
The compact coarse fixture initially exceeded the unchanged residual threshold
after rescaling; a Newton correction of only 3.210e−10 in scaled coordinates
polished it. Finally, finite-differencing the stiff brace exceeded the derivative
width-agreement gate at 28 intervals. The exact same brace law's analytic
spatial tangent eliminated that roundoff. Original runners, the pre-change
adapter, traces and terminal receipts are retained. No tolerance was relaxed.

All jobs used one BLAS thread and limits of 512 MiB address space, 15 CPU seconds
and 25 wall seconds. Maximum observed CPU time was **4.806 s**, wall time
**16.277 s**, and peak RSS **103.333 MiB**. The first plot had overlapping minor
x-axis labels; `report-v2` fixes their formatting without changing numerical
results. See the [verification receipt](../../artifacts/daedalus-wing-root-20261114/verification.json).

No production physics, aircraft settings, ISAE fractions or browser/build
verification changed. The full Bode gap remains **0.074218 versus 0.033986
deg/s/F3**. Together with the prior
[complete-aircraft mesh refinement](daedalus-structural-resolution-20261113.md),
which changed yaw magnitude only −0.217% at the dip, this comparison weakens
a gross mechanical compliance/phase explanation. Keep the four stricter
component checks open; the next Bode investigation should independently check
the current loaded wing's circulation/rate-load phase and its aerodynamic
feedback, rather than changing stiffness to fit the drawing.
