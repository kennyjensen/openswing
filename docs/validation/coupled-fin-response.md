# Free-frame and hinged-fin response check

The requested [log–log magnitude axes, decade labels and minor grids](bode-log-axes.md)
are complete. The Daedalus rudder-to-yaw response still differs from
[Drela’s drawing](https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf).
This investigation checks aerodynamic, internal-motion and free-frame feedback
together. It does not identify a production correction for that aircraft curve.

## Independent coupled model

A free carrier supports a massive, rigid lifting fin through an oblique-axis
torsional hinge. Both bodies move in response to aerodynamic loads. This extends
the earlier prescribed-motion comparisons: fin motion changes the flow, while
the resulting loads change both hinge motion and the carrier’s six frame motions.

The [fixture](coupled-fin-fixture.json) specifies a 4 kg carrier and 1 kg fin,
their offset centres of mass and full centroid inertias. The hinge is at
`(1.2, 0.25, 0.15)` m with axis parallel to `(1, 0.3, 0.2)`, stiffness
12 N·m/rad and loaded angle 4°. The fin is 2 m long with 0.6 m chord,
`Xax=0.35`, 2° incidence, lift slope `2π`, nonzero profile drag and section
moment. Airspeed is 10 m/s and density is 1.225 kg/m³. Gravity, propulsion,
distributed real mass and structural damping are absent. The two hinge nodes coincide;
the carrier-origin-to-hinge lever arm remains finite.

The independent [mechanical reference](../../scripts/coupled_fin_reference.py)
uses seven physical coordinates: three translations, three carrier rotations
and the hinge angle. It derives real inertial reactions from the two bodies’
CG trajectories and rotated inertia tensors. An independent
[aerodynamic reference](../../scripts/coupled_fin_aero_reference.py) integrates
the vortex fields and supplies circulation, profile, circulation-rate and
apparent loads. Neither reference imports production equations. The equations
follow Drela’s [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
and [unsteady extension](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf).
The compared virtual-point velocity convention remains explicit in the source;
this is not a claim of original-executable parity.

Each 4/8-interval fin gets its own independently manufactured steady balance
at the same loaded angle: a constant carrier-body wrench and spring rest angle.
The 32-point quadrature defines that balance, which is held fixed for the
16-point check and lag off/on. These are two discrete systems, **not a common-load
mesh-convergence study**. Production must recover the prescribed pose and
circulation and negligible acceleration before a response is accepted.

Inputs are one radian of section-incidence control and a positive carrier yaw
couple of one N·m. The latter maps to negative native `target.moment.z`.
Raw reported net loads exclude that imposed input; the physical balance adds
the yaw couple on both sides of the comparison. The full production systems
have 202/278 unknowns. The independent harmonic systems have 11/15 unknowns
after exact elimination of coordinate velocities; production is not reduced.

## Results

All **12 cases** pass: 4/8 intervals, 0.7/1/1.3 Hz, and circulation lag off/on,
with both inputs in each solve. Checks cover every circulation value, selected
nodal/frame coordinates, hinge motion, real-mass loads, all aerodynamic load
families, fin-side hinge reactions and physical global force/moment balance.

Every physical output uses `abs(error) <= 2e-7 + 2e-8*abs(reference)` in its
declared SI units. The largest comparison uses **18.43%** of that allowance.
The largest selected native-coordinate difference is `7.30e-9` in its saved
scaled coordinate. Maximum native scaled harmonic residual is `7.40e-15`;
the smallest estimated reciprocal condition is `5.69e-5`. The original
production conditioning and residual gates remain unchanged.

Independent checks also verify two complex-step sizes, 16/32-point quadrature,
and real-plus-apparent mass against a separately derived mass matrix. Apparent
mass occurs once. The mass-block difference is at most `8.88e-16`; the continuum
span integral is retained separately and is not substituted for discrete strip
weights. Parsed production nodes, attachment indices, frames, bound endpoints,
control points and force points agree with the independent geometry before
any production residual is evaluated.

The accepted response run passes 1,654 checks and uses 4,304 production residual
evaluations, two base corrections, four matrix pairs and twelve full two-input
harmonic calls. Its reference responses use 24 small two-input solves, reusing
the previously completed reference preparation. These are native execution
records, not browser performance benchmarks.

## Retained setup failures and audit

The first attempt completed all independent preparation and its 2,233 checks,
then stopped before any production residual because the new adapter supplied
a scalar circulation-mode setting instead of a per-beam dictionary.

After that adapter correction, the next attempt stopped after 32 residual calls
in its first equilibrium tangent. The test fin’s first native station was zero,
which invoked ASWING’s documented automatic surface mirroring. Because its
lateral coordinate was constant, the two branches overlapped. A small perturbation
separated coincident filaments and triggered the subsonic validity guard.
This did not establish a vortex-kernel defect. The
[user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt) describes
the mirroring convention.

The final adapter expresses the unchanged physical span `s=0…2` using native
stations `t=s−1`, including the root Joint and Weight attachments. It adds
21 explicit geometry checks per mesh before any residual. Both earlier failures
remain intact. No physical parameter, production equation or tolerance was
adjusted to obtain agreement; completed reference preparation was not repeated.

Separate saved-data audits pass **49,848** reference-preparation checks and
**28,304** coupled-response checks. They reconstruct derivatives, output
stencils and saved equations using four and 72 matrix products respectively,
with no new physical evaluations or solves. All numerical children exited and
were reaped. [Machine-readable results](coupled-fin-response.json) and the
[evidence archive](coupled-fin-response-20261025-evidence.zip) retain the failures,
raw results, reviewed sources, operation counts and process closeouts.

The durable [regression](../../tests/test_coupled_fin_response.py) passes both
one-hertz, four-interval cases with the same two inputs and unchanged gates.
It shares one equilibrium and checks all physical outputs and mapped coordinates.
Run it with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python -I -B -m pytest -q tests/test_coupled_fin_response.py`.

This checks a loaded rigid-body/hinge component. Distributed elastic deformation,
the full Daedalus coupling, its published operating point, the near-1 Hz minimum,
higher-frequency mesh convergence and a nonlinear rudder-step comparison remain
open. No production kernel, browser build, broad requirement or ISAE completion
state changes in this increment.
