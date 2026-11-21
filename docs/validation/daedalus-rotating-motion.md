# Daedalus yaw investigation: loaded rotating-fin reference

The requested [log–log magnitude axes, decade labels and minor grids](bode-log-axes.md)
are implemented. The full Daedalus rudder-to-yaw response still differs from
[Drela's published curve](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf).
This additional component comparison passes; it identifies no production
correction that explains the aircraft discrepancy.

## What this adds

The earlier [loaded moving-fin comparison](daedalus-loaded-motion.md) prescribed
lateral translation. This test rotates a loaded fin about an oblique axis, so
the section normal, span, vortex geometry and load moment arms all change.
Nonzero profile drag and section pitching moment are retained. The independent
reference integrates vortex filaments directly and derives the circulation and
complete force/moment variations without importing production aerodynamic,
geometry or derivative functions.

The fixture has a fixed horizontal wing spanning four metres with one-metre
chord and a two-metre fin with 0.75-metre chord. Both have 2° section incidence,
axis location `Xax=0.35`, `Cdf=0.01`, `Cdp=0.02` and `Cm=0.02`. Airspeed is
10 m/s, density 1.225 kg/m³, prescribed PG Mach is zero, and the separately
specified local sound speed is 340.294 m/s at zero altitude. The fin's initial
orientation is `Ry(7°) Rz(5°)`. Its perturbation rotates about `(1,2,3)/√14`
through the fixed pivot `(2,0,0.4)` metres. F3 is fixed at zero.

The input is **unit angular displacement in radians**, with angular velocity
`iωh` and acceleration `−ω²h`. This is a prescribed motion-to-load comparison;
it is not a rudder input or a free-aircraft yaw response. Production probes
transform the midpoint and endpoint frames and apply the complete rigid local
velocity and acceleration fields, including the quadratic centripetal term.

## Results

All **12 cases pass**: 4/8 intervals per surface, 0.1/1/10 Hz and empirical
circulation lag off/on. Each comparison checks the entire circulation vector
and all six force/moment components for the wing, fin and their sum. Total,
rate-lift, apparent-load and remaining steady-load contributions are checked
separately. Twelve reference terms distinguish induced flow, moving geometry,
section rotation, profile force/couple and physical moment-arm transport.

Reference quadrature uses fixed 16/32-point rules. Angular probe widths are
`1e-5` and `5e-6` radians. The component criterion remains
`abs(error) <= 2e-8 + 2e-8*abs(reference)`; neither tolerances nor parameters
were adjusted after seeing results.

| Check | Largest absolute difference | Largest fraction of allowed error |
| --- | ---: | ---: |
| Complete circulation transfer | 2.12×10⁻⁹ | 0.00983 |
| Force/moment transfer components | 1.37×10⁻⁷ | 0.4066 |
| Output change when halving angular width | 1.03×10⁻⁷ | 0.3062 |

Different force/moment components have different units and magnitudes; the
absolute maximum is not a relative-accuracy measure. Every component passes
its own absolute-plus-relative bound. The independent saved audit finds a
maximum normalized production base residual of `8.46e-12` and harmonic
residual of `1.69e-15`. A separate rigid rotation of the complete geometry and
wind preserves the expected force/moment transformation to `4.27e-14`.

One bounded run passes **786 checks**, with 352 aerodynamic evaluations,
44 independent field assemblies and 80 small circulation solves. It makes no
aircraft trim, structural solve or free-frame linearization. A separate
saved-output audit passes **2,882 checks** using 80 saved matrix-vector products
and no new physical evaluations or solves. It reconstructs the raw derivative
stencils, load aggregation and all twelve-term sums. Both runs exited normally;
there was no numerical retry.

The [independent reference](../../scripts/rotating_wing_fin_reference.py),
[ASW fixture](rotating-wing-fin.asw) and
[focused regression](../../tests/test_loaded_rotating_aero.py) are retained.
The regression checks both lag settings at 1 Hz against the independent
reference, using the full nonlinear production residual and load variations.
Both tests pass, using ten production evaluations and three small reference
solves. The largest residual variation is `1.74e-11`; the largest load error
uses 1.67% of its unchanged tolerance.
[Machine-readable results](daedalus-rotating-motion.json) retain the immutable
run summary, detailed checks, independent audit and source hashes. The summary
was written before the saved audit; that later result is recorded separately.

## Interpretation and remaining work

The reference follows the force and moment equations in Drela's
[steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
and [unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
It explicitly tests the current virtual-point velocity-sampling convention
with physical chordwise load arms. Agreement does not uniquely reconcile the
steady virtual geometry with the unsteady material-point velocity description,
or identify the convention used by the original executable. The earlier
aircraft sensitivity comparison found only small changes near 1 Hz when
substituting material-point velocity arms.

This verifies two finite discrete rotating-fin meshes. It does not establish
convergence of the swept force-point limit or experimental fidelity of the
empirical lag model. Loaded propeller/slipstream coupling, complete structural
and free-frame feedback, the unidentified published operating point,
higher-frequency aircraft mesh convergence and a nonlinear rudder-step
comparison remain outside this test. No production equation or default changed,
and no broad requirement or ISAE case becomes fully validated. This increment
adds no browser timing measurement or hosted release.

The subsequent [loaded propeller–fin study](loaded-jet-coupling.md) adds
independent prescribed-motion checks with nonlinear circulation/inlet/jet
feedback. It retains a coarse derivative-probe failure and separately verifies
its output-width convergence. That additional component coverage does not
resolve the complete aircraft response or validate a structural engine mount.
