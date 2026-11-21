# Loaded elastic boom–fin response with aerodynamic feedback

The clamped boom–fin component agrees with an independent continuous-beam and
lifting-line calculation at **1 Hz**. All **26 fine-mesh comparison criteria**
pass the preset 1% limit; the worst grouped complex relative error is **0.3601%**.
This checks distributed elastic motion with live aerodynamic feedback. It does
not resolve the [full Daedalus yaw discrepancy](daedalus-rudder-cruise-mesh.md),
and no production equation or accuracy tolerance was changed.

## Compared systems

The [existing fixture](daedalus-boom-fin-fixture.json) supplies the literal
variable-section Daedalus tailboom and fin, their mass offsets, the one-foot
rigid connector and saved spatial dead loads. The boom root is clamped. The
independent loaded spatial-rod solution retains bending, twist, preload
geometric stiffness and continuous distributed inertia. Axial extension and
shear are rigid, as specified by this fixture.

The live lifting fin sees a physical +x flow of 6.7 m/s, expressed in the model's
foot/pound/second units and rotated into the clamp coordinate system. Density
is 0.002378, sound speed 1115, and fixed Prandtl–Glauert Mach is 0.1.
The calculation retains unsteady circulation, circulation-rate and apparent
loads, profile force, moving vortex geometry and physical moment arms.
Stall limiting is off. The boom's aerodynamic radius is removed while its
structural properties and real inertia remain. Live gravity, propulsion and free
aircraft-frame motion are absent; the original fixed spatial loads and preload
remain in this component.

Each mesh has its own independently calculated constant nodal counterloads
that balance the steady fin airloads at the reference loaded shape. Those
counterloads stay fixed in every perturbation. Thus these are separately
balanced discrete aerodynamic systems, **not a common-load aircraft mesh
convergence study**. OpenSwing receives the independent pose, forces and
circulation as a starting guess and corrects its complete equilibrium.

The two meshes have 34/68 structural intervals, 36/70 nodes and 19/38 circulation
unknowns. Full native harmonic systems have 667/1,298 unknowns. Both receive
two inputs: one native F3 unit and a unit physical z couple at the upper fin tip.
The independent calculation eliminates the continuous beam equations using
Green functions and then solves for all nodal motions and circulation together;
the native calculation uses its complete sparse equations.

The reference follows Drela's [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
and [unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
Its beam integration, vortex quadrature, differentiation and coupled solve do
not import OpenSwing physics. Spatial rotations and nodal loads use mutually
consistent interpolation and virtual power. The separate kinematic check passes
144 identities, and the extended beam reference reproduces its previously
accepted mechanical response before live aerodynamic feedback is added.

## Results

Each input has 13 comparison groups: nodal motion, circulation, clamp and joint
reactions, four net aerodynamic load families, their four strip-load families,
and relative velocity at the aerodynamic force points. Complex values retain
both amplitude and phase. Within each group the criterion is the infinity norm
of the complex error divided by the reference infinity norm. Translations are
scaled by 20 ft and wrench moments by 20 ft; exact-zero reference groups use an
absolute limit of `1e-10`. This is not a pointwise relative-error bound.

| Group, worst of the two inputs | Coarse error | Fine error |
| --- | ---: | ---: |
| All nodal motion | 1.0942% | 0.3073% |
| Circulation | 1.0850% | 0.3362% |
| Clamp reaction | 0.7969% | 0.2466% |
| Fin joint reaction | 0.7861% | 0.2446% |
| Net total aerodynamic load | 0.8611% | 0.2684% |
| Worst of all 13 groups | 1.1574% | 0.3601% |

All 26 errors decrease on the finer mesh. Coarse results are descriptive;
six coarse group/input comparisons exceed the fine-mesh 1% criterion.
Corrected native base-position and base-rotation errors relative to the
continuum deflection decrease to 0.4073% and 0.4380%, respectively. Those base
shape comparisons are also descriptive, not additional acceptance gates.

Both meshes pass the original equilibrium, conditioning and harmonic-residual
gates, including a fresh full residual. Each native case uses one equilibrium
correction, one matrix pair, one two-input harmonic solve and nine physical
output snapshots. There are 845/1,483 residual calls. Native execution took
17.6/28.6 seconds on this host; these are not browser performance measurements.

The independent reference checks two complex-step sizes and 16/32-point vortex
quadrature, passing 300 checks on each mesh. A saved-data audit of the coarse
reference reconstructs all derivative blocks and response equations. The
comparison itself uses only saved outputs and performs no new physical solves.

## Retained setup failures and scope

The first rigid-limit helper check stopped on a scalar/vector shape mismatch
in its checker. Its complete first numerical pair was retained and checked
without repeating it after the checker was corrected. The first elastic
reference run later stopped when its recorder could not serialize a complex
scalar. Its base circulation and three complete numerical packets were retained
and reused; the serializer correction did not repeat that prefix. Both failures
remain in the evidence. Neither native mesh required a retry.

The earlier [free-carrier/hinged-fin check](coupled-fin-response.md) covers a
different coupling: free-frame and rigid internal motion. This component adds
distributed elastic deformation, but still excludes their combined aircraft
assembly. The published aircraft operating point, the near-1 Hz minimum,
higher-frequency convergence and nonlinear rudder-step validation remain open.
All broad requirements remain Partial, and ISAE coverage is unchanged.

## Reproduce the check

The portable [regression](../../tests/test_elastic_fin_feedback.py) passes its
fine-mesh case and all 26 response criteria in 20.2 seconds on this host. It
uses compact, source-attributed independent expected arrays, constructs the
complete native problem, and retains the original geometry and numerical gates.
It needs no staging directory or optional raw archive:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python -I -B -m pytest -q tests/test_elastic_fin_feedback.py
```

The independent [reference entry point](../../scripts/elastic_fin_reproduce.py)
freshly computes the loaded rod base, Green functions and all three aerodynamic
quadrature/step variants from the repository fixture. Its verified coarse run
passes 302 checks; a separate comparison finds all checked geometry and complex
response arrays numerically identical to the accepted original result. It uses
no production physics or saved numerical solution. Fifteen import/serialization
smoke checks and 125 saved comparisons also pass.

```sh
.venv/bin/python -I -B scripts/elastic_fin_reproduce.py --subdivisions 1 --output elastic-fin-reference
```

The output directory must be new. The command owns one single-thread child with
a 300-second limit and preserves failures. `--subdivisions 2` selects the second
declared mesh; the original fine reference passed, while this portable command
was freshly verified on the coarse mesh only.

The [machine-readable publication](elastic-fin-feedback.json) and
[raw evidence archive](elastic-fin-feedback-20261025-evidence.zip) retain the
original failures, independent and native results, reviewed sources and process
closeouts. The earlier [status record](elastic-fin-feedback-status.json) remains
an unchanged record of the exploratory stage. This publication adds no browser
build, hosted release or production-kernel change.
