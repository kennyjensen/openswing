# Daedalus: complete aerodynamic load derivatives

The actual loaded Daedalus aerodynamic loads agree with an independent
implementation along the saved rudder-response directions at 1 Hz and
1.15737773741517 Hz. **This found no correction to the Bode mismatch.** The
[latest corrected-mesh comparison](daedalus-shell-mesh.md) remains 28.1% high
in yaw at 1 Hz, 2.172 times the reference at the yaw dip, and 32.7% low in roll
at 1 Hz. No production equation, aircraft property or operating condition changed.

This extends the earlier [curved geometry and transfer checks](daedalus-curved-maps.md)
to the aerodynamic forces those maps produce. The independent evaluator retains
all four lifting surfaces, the curved tailboom's volume flow and distributed
loads, point-object drag and volume sources, the active propeller jet, stall
leakage, circulation-rate loading, profile drag, section pitching moments, and
apparent loads with local elastic and flight-frame motion. Engine inlet flow
includes circulation and body-flow feedback. Total aerodynamic force and moment
include the distributed, point and engine contributions.

## Method and results

The existing corrected C16 cruise project supplies the stationary loaded state
at 6.7 m/s, Mach 0.1, with 108 nodes and 82 lifting panels. The saved full harmonic
states supply separate real and imaginary directions at both frequencies.
Only the real directions receive the unit native control.3 input. Their state
rates are the corresponding parts of `i * 2*pi*f * Z`.

One baseline and 32 perturbed detailed residual evaluations capture the current
implementation. There are no new trim, linearization, harmonic or inner
circulation solves. The base normalized residual is 5.862e-11, and all 2,694
capture checks pass. Fourth-order directional stencils use widths 1e-3 and 5e-4.

The expected evaluator imports no production physics. It uses independent
Biot–Savart quadrature, body source/doublet integration, numerical propeller-jet
momentum integrals, SO(3) section interpolation, and explicit load equations from
Drela's [steady](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) and
[unsteady](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
technical descriptions. Parsed material samples and raw physical state
directions are inputs; captured native airflow and loads are comparison targets.

All **769 array comparisons pass**, covering 102,441 scalar comparisons across
23 output maps, baseline agreement, four response directions, both native
stencil widths, vortex quadrature orders 16/32 and complex-step widths
1e-24/1e-20. The fixed componentwise gate is
`abs(error) <= 2e-7 + 2e-7*abs(reference)`. These are component comparisons,
not independent aircraft cases.

| Directional quantity | Largest absolute native/reference difference |
| --- | ---: |
| Lifting-strip force | 3.596e-11 |
| Lifting-strip couple | 8.830e-12 |
| Local normalized circulation residual | 1.935e-11 |
| Body-element force | 8.902e-15 |
| Point-object force | 5.720e-13 |
| Engine intrinsic force | 1.484e-12 |
| Total aerodynamic force | 1.784e-10 |
| Total aerodynamic moment | 8.892e-10 |

Force/couple quantities use the file's force and moment units per native F3
unit. The largest change between vortex quadrature orders is 3.054e-16; between
complex-step widths it is 7.106e-15. The largest native width change is
1.188e-9 in total moment, within the original gate.

Separate saved-data reviews pass 3,109 native-capture checks and 1,298
independent-result checks without evaluating physics. A further 397 checks
verify that all 115 portable expected arrays and the saved response inputs
match their source evidence exactly.

The first independent attempt stopped before completing a baseline because the
parser pads Engine records to 25 fields while the type-0 reference accepts the
15 aerodynamic fields. The corrected adapter checks that the ten optional
fields are zero before selecting the first 15. The failed source, traceback and
partial operation accounting are retained. No native capture, physical setting,
comparison gate or completed expected value was replaced.

## Limits and remaining work

This checks the implemented discrete aerodynamic equations at a stationary base
and four selected directions. It does not independently validate material
interpolation or the input state chart. The independent angular-acceleration
interpolation retains its complete first-order stationary-base terms; it is
not a finite-motion time integrator. Ground, gust, automatic Mach, nonzero
optional engine fields and unequal body radius jumps are outside this fixture.

The selected body apparent-mass factor is explicitly 1. Printed ASWING steady
Eq. 86 and unsteady Eq. 45 use 2; historical executable behavior remains
unestablished. A [prior factor-2 study](daedalus-rudder-coupling.md) changed the
old C16 complex yaw response by only 0.037047% at 1 Hz and 0.052608% at the dip
frequency. That is earlier evidence, not a new corrected-mesh sensitivity run.
The body-flow comparison follows declared radius jumps only and does not infer
an end closure from a finite end radius.

Complete structural force/moment balance and its coupling to free-flight motion
were outside this aerodynamic increment. The subsequent
[complete harmonic-balance comparison](daedalus-full-balance.md) now independently
checks those terms along the same four loaded-aircraft response directions.
Historical reference settings, higher-frequency convergence and agreement of
the complete Bode curves remain unresolved. Passing these comparisons does not
establish an ASWING match or completion of the full OpenSwing goal.

## Reproduce and inspect

Five portable regressions compare current native loads with the independent
baseline and four directional arrays. They pass with 17 prescribed residual
evaluations and no aircraft solve:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_daedalus_full_aero.py
```

The [machine-readable report](daedalus-full-aero.json) and
[evidence archive](daedalus-full-aero-20261025-evidence.zip) retain the raw
capture packets, independent expected arrays, source versions, original gates,
saved-data audits, portable regressions and process receipts.
