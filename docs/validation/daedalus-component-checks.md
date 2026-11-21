# Daedalus response: independent component checks

The loaded boom–fin mechanics and idealized wing–fin aerodynamic transfer agree
with separate reference calculations over the cases below. These checks do not
resolve the difference from [Drela's rudder Bode curve](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf).
Production physics and default parameters are unchanged.
The [combined results](daedalus-component-checks.json) include the comparison
and audit records; the [CSV](daedalus-component-channels.csv) retains all 11,712
nodal channel rows.

## Loaded structural component

The fixture retains the Daedalus boom from x=0 to 20 ft, the whole fin from
z=−3.5 to 5 ft, the one-foot rigid connection, and literal material and mass
distributions. Fixed spatial loads reproduce the saved loaded state; the
omitted aircraft parts contribute fixed interface loads. The boom cut is
clamped. The same load points and wrenches are retained under refinement.

An independent spatial-rod calculation integrates the variable-section
equilibrium and harmonic equations. It retains the loaded geometry, connector
preload moment, distributed real mass and fin center-of-gravity offset. It
imports no production geometry, residual, section, inertia or derivative code.
Both calculations omit fluid loads, apparent mass and damping in this mechanical
test. Frozen gravity loads remain in the base; they are not applied a second time.

Two incremental upper-tip inputs are checked: a 1 lb body-y force and a 1 lb·ft
body-z couple, at 0, 0.7, 1.0 and 1.3 Hz. The table gives the largest error across
these eight responses, using the infinity norm of every nodal displacement
divided by 20 ft and every spatial rotation in radians, normalized by the same
reference norm.

| Structural elements | Nodes | Maximum scaled motion error |
| ---: | ---: | ---: |
| 34 | 36 | 0.34074% |
| 68 | 70 | 0.08337% |
| 136 | 138 | 0.02064% |

All twelve production frequency/mesh solves, each with two input columns, pass
the original conditioning and full-equation residual checks. Refinement reduces
the motion error by approximately four each time. The finest mesh satisfies
the predeclared 1% comparison criterion. This norm does not imply that every
small individual channel has the same relative accuracy; the accompanying data
retain the individual channels, base geometry and reaction comparisons.

Tightening continuum integration from 10⁻⁹ to 10⁻¹¹ changes the largest scaled
motion by 1.67×10⁻¹⁰ relative, passing the separate 10⁻⁶ criterion. At 1 Hz,
the finest-mesh force-to-tip-z-rotation and couple-to-tip-y-displacement errors
are 0.1023% and 0.1111%, respectively. The largest finest-mesh reaction-vector
error is 0.0782%; reactions have no separate pass threshold. An independent
audit passes 73 checks using the saved full operators and response vectors,
without rerunning the physical solves.

The standalone [continuum reference](../../scripts/boom_fin_reference.py) and
[literal fixture](daedalus-boom-fin-fixture.json) can reproduce the reference:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python -I -B scripts/boom_fin_reference.py \
  --fixture docs/validation/daedalus-boom-fin-fixture.json \
  --rtol 1e-11 --output /tmp/openswing-boom-fin-reference
```

The output directory must be new. `base.npz` stores force/moment traces after
each load jump along the integration direction. In response files, the saved
base trace at a shared station is from before that jump. Positions, orientations
and harmonic perturbations are continuous there. The lower fin retains its
original increasing material coordinate while integration proceeds downward.
The [comparison script](../../scripts/compare-daedalus-components.py) performs
saved-array reductions with `--stage` pointing to the complete staged production
and reference results; those full matrices are not embedded in the fixture.

## Independent aerodynamic component

A separate idealized straight wing and vertical fin are checked at 4 and 8
intervals per surface, 0.1, 1 and 10 Hz, with circulation lag off and on. All
twelve cases pass the predeclared absolute-plus-relative tolerance of 2×10⁻⁸.
The largest circulation difference is 1.25×10⁻¹⁵; the largest force/moment
difference is 4.71×10⁻¹⁴. The checks include native F3 input sign, the lag matrix,
mutual induction, nonzero wing roll and fin yaw, and the full six-component
loads and their rate contributions.

The reference independently constructs the Glauert samples and integrates the
Biot–Savart filaments using the specified cross-surface core. The first attempt
passed the coarse cases but failed the finer reference quadrature check. That
failure is retained. A separately declared change of integration variable made
the integrand smooth; the influence coefficients from fixed 16/32-point
quadrature then differed by at most 2.49×10⁻¹⁴. No production equation, physical parameter or acceptance threshold
changed, and the passed coarse production cases were not repeated.

The equations are based on Drela's [steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
and [unsteady theory](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
This zero-circulation, fixed-geometry case excludes loaded moving-surface
coupling and motion-driven apparent loads.
The subsequent [loaded-motion study](daedalus-loaded-motion.md) adds those terms
for prescribed fin translation and passes all twelve independent comparisons.
Rotating/deforming sections and full aircraft coupling remain separate.

## What remains unresolved

These are component checks, not a full aircraft comparison with original
ASWING or experiment. The mechanical case has fixed loads and no fluid feedback;
the aerodynamic case has no structural or free-frame dynamics. Natural cubic
material interpolation is independently implemented here, but exact spline
endpoint parity with original ASWING remains unverified.

The published Daedalus operating point is still unidentified. The near-1 Hz
minimum remains too shallow, and higher-frequency mesh convergence is still
open. The [earlier aircraft comparison](daedalus-rudder-cruise-mesh.md) and
[coupling diagnostics](daedalus-rudder-coupling.md) retain those discrepancies.
No broad requirement or ISAE validation status is upgraded by these results.
The [requested log–log display](bode-log-axes.md), decade labels and minor grids
are implemented and tested separately.
