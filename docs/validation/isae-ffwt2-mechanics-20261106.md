# FFWT-2 independent mechanics and restart refinement

This follow-up investigates the zero-pass roll-acceleration and tip-bank
channels at the user-approved 5% native allowance. It adds an independent
mechanics reference, a source-history audit and local temporal refinement.
The native counts remain unchanged; no physical inputs were fitted.

## Independent mechanics reference

The selected FFWT10/V15/DF21 model has a rigid center wing, two rigid hinged
tips and uniform tip mass. Its literal inputs permit a three-coordinate
mechanical reference: aircraft roll and one rotation about each hinge axis.
The reference imports no production inertia, joint, geometry or motion code.

Two calculations are kept separate:

1. Completed endpoint mass products, with the finite-segment rotary term in
   steady Eq. 80 and moving-frame acceleration/transport. This reconstructs
   the source operator from its nodal state.
2. Exact rigid rods and the two center-wing point masses. Four-point Gauss
   integration is exact for the quadratic particle moments. The resulting
   3-by-3 mass matrix and centrifugal/Coriolis terms use rigid-hinge kinematics.

References are the [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
Eqs. 50, 55, 56 and 78–83, and the
[unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
Eqs. 23, 27 and 37–40. The existing moving-frame transport interpretation
includes the angular-acceleration term Ω×ω; that implementation is not changed.

The exact flat-geometry mass matrix agrees with closed-form rod integrals.
Independent differentiation of Earth-frame particle positions verifies three
rotating configurations. Three additional tests verify the kinetic-energy
power identity for the Coriolis terms. All **7 reference tests pass**.

Nine saved states cover the equilibrium-start 2.00–2.04 s window and the
jig-start/restart 2.01–2.04 s window. The reconstructed real-plus-aerodynamic
wrench agrees with the saved applied wrench to roundoff. Global roll and both
hinge balances close to at most **3.11e-10 N m**. The two signed Jangle tables
produce the same restoring spring law on their respective tips.

The extended audit covers **all 204 converged jig-start states**, .01–2.04 s,
excluding the uncomputed raw seed. Reconstructed force and moment errors are
at most **8.89e-15 N** and **3.82e-16 N m**. The largest global/hinge balance
residual is **1.69e-8 N m**. Exact rigid kinematics changes instantaneous roll
acceleration by at most 8.491 degrees/s² across that whole saved history, at
0.12 s. This still uses saved aerodynamic loads and does not bound accumulated
time-integration error.

Holding the saved aerodynamic wrenches fixed, exact rigid kinematics changes
roll acceleration by at most **0.3822 degrees/s²** in the earlier continuous
window. Across the command restart the maximum is **4.8209 degrees/s²**;
by 2.04 s it is **0.2273 degrees/s²**. These checks do not reproduce the native
acceleration. They verify mechanical bookkeeping at the saved motion, without
independently certifying the aerodynamic loads or the accumulated trajectory.

## Original source and constraint evidence

The literal model decodes to:

| Quantity | Value |
|---|---:|
| Center-wing point-mass total | 0.773 kg |
| Center-wing roll inertia | 0.01949308112 kg m² |
| Mass of each tip | 0.0499936 kg |
| Tip CG spanwise arm from the hinge intersection | 0.068 m |
| Tip centroid inertia about its chord axis | 7.7056802e-5 kg m² |
| Tip inertia about the parallel chord axis through the hinge | 3.0822721e-4 kg m² |

The last row is a chord-axis quantity, not the inertia about the flared hinge.
The two literal tip Weight records have zero mass; tip inertia instead comes
from distributed mass. ISAE report section 4.2 describes a mass-dipole
representation for the wing and tips, so its description does not fully match
this literal input. This qualifies report-to-model correspondence. It does
not establish that the archived model and output are mismatched.

Eight already cached historical repository trees, spanning both directory
names, contain identical Git blobs for the selected `.asw`, driver and `.txt`.
No alternative triple was found in those trees. This is not an exhaustive
claim about all possible private or historical files.

The [extended manual](https://web.mit.edu/drela/Public/web/aswing/ASWING_Extended_User_Manual.pdf)
figures 1.5/1.6 show column 4 as roll acceleration. With one flap and no engines,
the corresponding net-roll-moment row is 23. Its description of `freqCalc`
sets unsteady mode. These observations support the driver's `4 23` free-roll
interpretation; they do not recover the original complete constraint table.
Rendered manual pages 12 and 14 are retained with the audit.

The primary Healy journal manuscript is linked from Bristol's public record,
but direct PDF retrieval returned HTTP 403. Indexed table values were a research
lead only; they were not used to alter the model or award a native pass.

## Local temporal refinement

Every local run starts from the identical saved 2.00 s state, takes one BDF1
step for the second time command, and then uses BDF2 to 2.04 s. This preserves
the original coupled beam/aerodynamic solver. The initial two seconds are not
refined. The initial finite-step state also has small differences from exact
continuous rigid-hinge velocity constraints, so these runs include a restart
transient; they are not independent continuous initial-value certificates.

The numerical gate is 0.1% of each output's maximum fine-grid magnitude over
the common 2.00, 2.01, 2.02, 2.03 and 2.04 s rows. This is separate from the
5% native allowance. All intermediate states and duplicate joins are audited;
no output is interpolated, phase-shifted or angle-adjusted.

The initial .01/.005 s pair passes 4/5 channels; acceleration changes 10.74%
near the restart. The .005/.0025 s pair also passes 4/5: rate and all three
angles pass, while acceleration changes **6.33%**. Its acceleration difference
is only 0.12334 degrees/s² at the final time, showing that the maximum is local
to the command transient. The two new jobs take 11.47 and 17.29 seconds,
with eight and sixteen accepted steps, respectively, and no rejections.

Further grids at .00125 and .000625 s both complete. The last two adjacent
pairs each pass **5/5 local accuracy gates**. The finest comparison is:

| Output | Maximum change as percent of fine-window scale | Gate |
|---|---:|---:|
| Roll acceleration | 0.0112043% | 0.1% |
| Roll rate | 0.0001106% | 0.1% |
| Aircraft bank | 0.0000226% | 0.1% |
| Sensor 2 bank | 0.0005802% | 0.1% |
| Sensor 3 bank | 0.0011598% | 0.1% |

The last two runs take 25.78 and 43.67 seconds. Across all four new grids,
**120 steps are accepted, none rejected**, and the largest state residual is
9.85e-9. Original coarser failures remain recorded. Helper copies for the
additional grids differ only in allowed step sizes and the artifact-relative
root path; source hashes and physics are unchanged.

This establishes convergence at the common output times for this short,
fixed-start window. It does not establish accuracy at every finer intermediate
time, refine the original two-second startup or recover native initialization.

All five time grids still pass only **5/25 computed native comparisons** at
5%, or **5/4,005** across the full selected table; only roll rate passes. At
the finest step, failed median/max errors are acceleration **159.69%/199.87%**,
aircraft bank **7.38%/7.45%**, sensor 2 bank **64.52%/72.92%**, and sensor 3
bank **31.95%/32.25%**. Thus resolving this local restart transient does not
resolve a failed native channel. The earlier equilibrium-start 10/25 remains
a separate startup scope, not a combined score.

## Evidence and limits

Evidence: `artifacts/isae/ffwt2-mechanics-20261106/`. The initial checker error
counted four literal Weight records instead of two active point objects; its
failure and correction are retained. Physical predictions and tolerances did
not change. Source history, input hashes, individual run logs, saved-state
mechanics, reference tests and refinement comparisons are retained separately.

Full-history time refinement, spatial refinement, independent aerodynamic
checks and authenticated startup remain required. The selected native table
still has 3,980 unrun values in each startup scope. Production kernels, browser
bundles and native pass counts are unchanged by this follow-up.
