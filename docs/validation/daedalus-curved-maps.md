# Daedalus: actual curved geometry and preload checks

Independent checks of the actual loaded, corrected C16 Daedalus geometry found
no discrepancy in the tested vortex, load-transfer or beam-compatibility maps.
The [Bode mismatch](daedalus-shell-mesh.md) remains unchanged: yaw is 28.1% high
at 1 Hz and 2.172 times the drawing at 1.15737773741517 Hz; roll is 32.7% low
at 1 Hz. No production equation, aircraft property or operating condition changed.

This extends the straight [free-elastic benchmark](free-elastic-coupling.md)
to selected maps at the actual curved aircraft state. It does not supply an
independent complete aircraft response or establish historical ASWING parity.

## Vortex fields and geometric load transfer

The public corrected-mesh cruise state restores with its existing identity and
residual gates. All four lifting surfaces are present: wing, stabilizer,
rudder and fairing, with 82 panels and 86 receiving nodes. The saved complete
response directions at 1 Hz and 1.15737773741517 Hz supply separate real and
imaginary perturbations. No new aircraft trim, linearization or harmonic solve
is performed.

An independent implementation integrates the Biot–Savart filaments in
Prandtl–Glauert coordinates and differentiates the section rotation interpolation
and its virtual-work transpose. It retains live geometry, cross-surface cores,
distinct control/force/axis receivers and the declared own-bound exclusion.
The virtual-vortex and transformed-flow equations follow Drela's
[steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
The implemented rotation interpolation is checked explicitly; historical
discretization equivalence is not inferred from that agreement.

All 682 array comparisons pass the fixed componentwise gate
`abs(error) <= 2e-8 + 2e-8*abs(reference)`. They retain 222,270 scalar comparisons,
including quadrature, derivative-width and baseline checks; these are not
222,270 independent aircraft cases.

| Directional quantity | Largest absolute native/reference difference |
| --- | ---: |
| Control-point induced velocity | 3.765e-10 ft/s per native F3 |
| Force/axis-point induced velocity | 3.971e-10 ft/s per native F3 |
| Transferred nodal force/couple components | 9.216e-12 in their respective input units per native F3 |
| Section-frame entries | 6.588e-13 per native F3 |

Quadrature orders 16/32 and complex-step widths `1e-24`/`1e-20` agree separately.
The native four-point stencil uses widths `1e-3` and `5e-4`. Its largest
width-change error uses 2.41% of the allowed componentwise tolerance. The
independent saved-array review reproduces all comparisons and passes 1,851
checks. Total transferred wrench conservation holds within 1.33e-12 in the
corresponding force/moment units.

The baseline load evaluation retains body-volume flow, the active propeller jet,
stall, profile force and apparent loading. The resulting strip wrenches are
held fixed when differentiating their geometric transfer. Consequently this
check does **not** validate those load laws or their derivatives. The vortex
field target excludes the separate body and jet fields on both sides.

## Loaded beam compatibility

The separate mechanical audit independently differentiates the objective
discrete compatibility equations, including rotation of the loaded internal
force and moment into the material frame. It compares all 618 compatibility
rows and all 2044 saved descriptor columns, plus the four saved response
directions and six rigid-motion directions.

All 576 checks pass. The largest matrix-entry difference is 9.095e-13; the
largest directional-action difference is 3.331e-16, against the fixed
`2e-10 + 2e-10*abs(reference)` gate. Independent fourth-order residual stencils
at two widths differ by less than 9.34e-13. A common rigid rotation includes
rotation of the internal resultants, preserving objectivity. A separate
saved-array review passes 408 checks without new physics or solves.

Loaded moment transport is nonzero on all five beams and is retained. The
force-transport contribution through constitutive compliance vanishes for
this file's infinite axial/shear stiffness. This does not remove the separate
force-dependent geometric stiffness in the equilibrium rows. Nodal/global
balance, live brace/joint loads, moving-root continuum impedance, inertia and
the complete aerodynamic feedback remain outside this compatibility check.

## Reproduce and inspect

All six portable regressions pass: five aerodynamic-map tests and one complete
compatibility-map test. They compare current production maps with retained
independent expected arrays:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_daedalus_curved_aero.py tests/test_daedalus_curved_mechanics.py
```

The [report](daedalus-curved-maps.json) and
[evidence archive](daedalus-curved-maps-20261025-evidence.zip) retain source
pins, physical inputs, complete arrays, original gates and process receipts.
The next unresolved scope is the complete loaded-aircraft force/moment and
free-frame feedback, including the load derivatives excluded above. Unknown
historical reference settings and higher-frequency convergence remain open.
