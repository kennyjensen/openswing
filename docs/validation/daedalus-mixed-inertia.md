# Daedalus: coupling between aircraft and elastic inertia

The saved 16-panel, 6.7 m/s aircraft matrices agree with an independent
kinetic-energy calculation for both directions of real-inertia coupling.
The largest normalized matrix-entry difference is **1.40e-11**, within the
unchanged `2e-8 + 2e-8*abs(reference)` criterion. This does not explain or correct
the [near-1 Hz Bode discrepancy](daedalus-rudder-cruise-mesh.md).

The audit uses the complete five-beam configuration: 117 nodes, 112 elements
and 2,215 dynamic coordinates. It checks the 6-by-702 block connecting elastic
acceleration to aircraft force/moment, and the 702-by-6 block connecting
aircraft acceleration to nodal force/moment. Compatibility, constraint and
kinematic equations are excluded from this physical comparison. The complete
descriptor matrices are not expected to be symmetric.

## Independent calculation

At the saved stationary elastic state, the real kinetic-energy cross term is

`G_RE = sum(Jv_R.T P Jv_E + Jw_R.T I Jw_E)`.

Here `P` is a quadrature point's translational mass tensor and `I` its
centroidal rotary inertia. `R` denotes aircraft translation/rotation and `E`
the elastic nodal velocities/rates. Independent Jacobians include both endpoint
structural offsets, distributed CG offsets and point-object arms. Full material
rotation interpolation supplies real-mass kinematics. The calculation reads
literal `.asw` tables and the saved physical geometry; it imports no OpenSwing
physics or geometry functions.

Distributed properties are held at the same material midpoint as the discrete
production equations. The reference therefore checks that discretization's
inertial assembly, not its continuum accuracy. Eight-point integration matches
the production order; independent 16- and 32-point calculations check tightening.
Line inertia is integrated directly, without adding a second finite-segment
`ds^2/12` contribution. Point-object masses and inertia tensors retain their
literal file values.

The saved matrices use `A = R_z` and `M = -R_zdot`. Physical row and column
scales are restored before comparison:

```
H_RE =  S_R M[aircraft load rows, elastic velocity/rate columns] D_E^-1
H_ER = -S_E A[nodal load rows, operating acceleration columns] D_R^-1
```

In particular, operating acceleration scales differ from the velocity scales;
the saved values are used. The moment and acceleration origins coincide in this
literal case. No assumption about different origins is silently applied.

Independent apparent-acceleration blocks are subtracted from both extracted
blocks before comparing real inertia. Lifting-surface normal added mass and
pitch inertia use the half-chord point; body transverse added mass retains the
case's saved coefficient of one. Apparent-load kinematics use the deformation
rotation interpolation rather than the full material arc. Velocity-dependent
apparent loads and circulation-rate terms are outside these blocks.

The physical basis follows Drela's [steady equations](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
and [unsteady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
The separately reported [body-coefficient sensitivity](daedalus-rudder-coupling.md)
is unchanged; this audit does not change that convention.

## Results

Matrix errors below apply a congruent angular-velocity scale of `1/L` and divide
by total real mass, making the compared entries dimensionless. These are
absolute entry errors, not percentage errors in the Bode response.

| Comparison | Largest normalized entry difference |
| --- | ---: |
| Aircraft loads from elastic acceleration versus independent real inertia | 1.11e-16 |
| Nodal loads from aircraft acceleration versus independent real inertia | 1.40e-11 |
| Reciprocity of the extracted real cross blocks | 1.40e-11 |
| Independent real inertia, 16 versus 32 quadrature points | 3.47e-18 |
| Independent apparent inertia, 16 versus 32 points | 1.36e-20 |

All **816 recorded checks** pass, including geometry reconstruction, dimensions,
mass bookkeeping, rigid-motion representation, quadrature and matrix comparisons.
They describe this one saved aircraft state, not 816 independent aircraft cases.
The worst native comparison uses **0.0698% of its allowed error**. A common rigid
motion represented through elastic nodes reproduces the frame kinematics at
every integration point.

The audit takes 11.9 seconds including its supervisor on this host. It performs
no physical residual evaluation, trim, field assembly, linearization, harmonic
solve or aircraft-system factorization. It constructs 65 small property-spline
systems and evaluates the independent quadrature/Jacobian products. This is not
a browser timing measurement or a new Bode sweep.

## Retained failure and scope

The first attempt stopped before scientific operations because its independent
Weight parser mistakenly included the integer beam-number column when applying
the multiplier row. The corrected parser follows the documented format and
passes 13 literal-data checks, including hand-decoded Daedalus Weight records.
Only that parser changed; the scientific calculation and tolerances are
identical. The failed attempt, diagnosis and source reviews remain in the evidence.

No production equation, default or tolerance changed. This rules out the tested
mixed real-inertia assembly defect at this state. It does not validate the
complete aerodynamic/elastic/gravity tangent, gyroscopic response at a rotating
base, other aircraft configurations, or agreement with original ASWING.
The full-aircraft Bode dip, higher-frequency convergence and unidentified
published operating point remain open.

The [machine-readable report](daedalus-mixed-inertia.json) and
[evidence bundle](daedalus-mixed-inertia-20261025-evidence.zip) retain the checks,
source identities, operation counts and failed first attempt. Extract the bundle
and enter its `mixed-inertia` directory. The following verifies the package
without performing numerical work:

```sh
python3 -I -B replay.py --verify-only
```

For a numerical replay with NumPy and SciPy installed, choose a new output path:

```sh
python3 -I -B replay.py --run --target /absolute/path/to/new-audit-directory
```

The bundle includes all saved inputs, unchanged scientific runner and an owned
120-second supervisor. Package verification and fresh-directory path remapping
were checked without repeating the accepted scientific run. The included README
records the accepted environment and an optional interpreter selection.
