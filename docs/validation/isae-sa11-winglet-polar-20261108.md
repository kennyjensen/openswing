# SA-11: the report-derived twist sign agrees across 21 archived angles

2026-11-08 UTC. The upper-winglet **−4° twist specified in ISAE Figure 40**
brings native AVL within **0.561% in lift and 0.332% in Trefftz induced drag**
of every archived row from **0° to 5°**, at 0.25° intervals. The supplied
`.asw` file's +4° twist gives substantially larger errors over this interval.
This extends the [one-point sign check](isae-sa11-winglet-incidence-20261108.md)
and supports an input discrepancy across the curve, rather than a coincidence
at one operating point.

**This does not validate production OpenSwing.** All 42 retained production
states still exceed the local section-normal Mach limit. SA-11 remains
**163/4,592 at 5%**. No original or bundled model, production equation,
Mach guard, registered fraction or comparison scope changes.

![Native AVL and archived ASWING polar comparison](../../artifacts/isae/sa11-winglet-polar-20261108/winglet-polar.png)

[Exportable SVG](../../artifacts/isae/sa11-winglet-polar-20261108/winglet-polar.svg).
Colors use the application's VibeLattice palette order.

## Scope and controlled inputs

The archived `wingtip_up_polar_Ma_0_70.sh` prescribes 240 m/s and 41 angles
from 0° to 10°. This follow-up predeclares all first 21 rows, with both twist
signs at every angle. No angle is selected or omitted by its numerical error.
The already computed 1° pair is reused with its original timestamps and
checksums; 40 native and 40 production calls are new.

As in the preceding check, the only input alternative is the upper-winglet
twist sign. Geometry, zero-lift angle, profile properties, lift limits and
the main wing retain their supplied values. Both methods use 64 matched
vortices, the same native endpoints and force/control receivers, frozen
body-x influences, PG Mach `240/340.21`, and density 1.2256. The production
stall law and local Mach guard remain enabled. The sign choice is taken from
the report, not fitted to the archived coefficients.

The source and angle-convention qualifications in the
[preceding report](isae-sa11-winglet-incidence-20261108.md) still apply.
Beam-normal twist is distinct from NASA's body-axis toe angle; −4° is the
figure-derived ASW input alternative, not an exact reconstruction of every
NASA dimension. Native AVL omits profile-force lift and section profile
moment in this comparison. Its CL is therefore vortex lift, whereas the
archived CL includes profile-force contributions. Near-field vortex CD is
retained separately and is not substituted for archived total CD.

## Results across the full declared angle interval

Errors below are signed percentages relative to the archived ASWING output.

| Upper-winglet input twist | CL error range | Trefftz CDi error range | Largest OpenSwing/native circulation difference, relative L∞ |
|---|---:|---:|---:|
| Supplied +4° | +2.360% to +5.333% | +2.631% to +22.324% | 3.0148% |
| Report −4° | +0.510% to +0.560% | −0.332% to −0.289% | 0.08130% |

The figure-derived sign improves both native coefficients at every one of
the 21 angles. Its OpenSwing circulation remains close to native AVL across
the interval. This strengthens the input-conflict evidence, but does not
authenticate the original ASWING producing file, discretization or startup
settings. The residual CL offset also cannot be interpreted as a pure
circulation error because the native comparison excludes profile-force lift.

No sampled section exceeds its declared CL limits. The minimum separation
from a limit is **10.54 transition widths** with −4°, versus **2.09 widths**
with +4°. Thus the literal +4° cases approach the soft stall transition at
the upper end of the interval. The corresponding 3.01% maximum circulation
difference must not be generalized as a discrepancy between two fully linear
formulations. No post-stall repair or change to the stall model was attempted.

## The remaining failure is local velocity, not circulation convergence

| Upper twist | Range of maximum section-normal Mach, OpenSwing | Same diagnostic on native AVL fields |
|---|---:|---:|
| +4° | 1.4331–3.0703 | 1.4350–3.1199 |
| −4° | 1.2516–2.9319 | 1.2530–2.9367 |

Each row is a range of spatial maxima across the angle sequence. Native
velocity is projected perpendicular to the same ASW beam tangent before
computing this diagnostic. It is not an AVL acceptance test. All production
rejections occur after circulation convergence; the largest retained residual
is **4.04e-13**, well below the 1e-8 gate.

Drela's **steady technical description, pp. 16–17, equations 64 and 67–73**
uses bound-location local velocity for lift and its beam-normal component for
the section moment, with a `1/sqrt(1-M_perp²)` factor. Rechecking these
equations does not justify replacing the local Mach by freestream Mach or
bypassing the guard to obtain accepted loads.
[Local technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf).

The next priority remains the junction's local section-velocity and
force/moment treatment, including the original span sampling. The twist sign
now has evidence across a complete declared low-angle interval, so further
post-stall polar expansion is not the next step. Total drag, moment, the
remaining variants and the separate Mach 0.75/0.78 normalization conflicts
remain unresolved.

## Reproduction and verification

- [Driver](../../scripts/verify-sa11-winglet-polar.py), running one serial
  two-sign pair per `--row` invocation.
- [Predeclared cases and source pins](../../artifacts/isae/sa11-winglet-polar-20261108/plan.json).
- [Saved-evidence analyzer and plot generator](../../scripts/analyze-sa11-winglet-polar.py).
- [Complete checked results](../../artifacts/isae/sa11-winglet-polar-20261108/analysis.json).

Every new pair ran serially with one BLAS thread, a 45-second outer timeout
and a 768 MiB address-space limit. The native calls totaled **9.77 s** and
production aerodynamic calls **3.54 s**, excluding imports, setup, process
startup and provenance checks. All processes completed; there were no solver
timeouts. The analyzer performs no new solves.

Verification checks 159 unchanged source/production/status pins, every saved
case artifact, the 42 reference-row pairings, native operating Mach and
freestream direction, retained circulation residuals and stall margins, and
both local Mach calculations. Native endpoints and receivers are identical
across all 42 states. Independently reconstructed native lift/near-field drag
agrees with native force output within **3.34e-16**. The generated plot was
visually reviewed. The registered status fractions remain unchanged.
