# Daedalus: interacting-surface AVL comparison and direct airflow feedback

The loaded wing, stabilizer, fin and modeled lifting fairing now have a joint
native AVL comparison. The four total roll/yaw moment derivatives differ by
**0.85–3.77%** under the disclosed steady conditions. Some smaller cross-axis
and individual-surface derivatives differ much more; this is not a claim that
every quantity passes a 5% gate.

In the actual unsteady source model, removing direct wing-to-fin or fin-to-wing
circulation **and vortex-motion** feedback changes the yaw dip by at most
**0.217%**. Removing both changes it by **−0.147%**. This weakens direct mutual
airflow as the explanation for the reference mismatch. Structural and
free-flight coupling remain active. Full yaw remains **0.074218 versus
0.033986 deg/s/F3** at 1.157378 Hz. No production correction or reference pass
follows.

![Native convention comparison and conditional feedback effects](../../artifacts/daedalus-coupled-avl-20261114/report/coupled-avl-feedback.png)

## Native case and conversion

The [authoritative reference policy](aswing-authoritative-references.md#avl)
and [source catalog](aswing-authoritative-sources.json) govern this comparison.
It extends the [isolated wing/fin study](daedalus-loaded-avl-20261113.md) to
all four lifting surfaces together: beam 1 wing, beam 2 stabilizer, beam 3 fin
and beam 5 fairing, with **28/18/18/18 intervals**. The beam-4 body and engines
are omitted from both steady comparisons.

Both use the accepted loaded 6.7 m/s source-equation/SEGSPL geometry and trim
controls, held rigid. The diagnostic flow has **Mach zero, unit speed/density,
body-x wake**, and incident angles **3.0563625° / 0.0180183°**. A uniform
velocity offset preserves incident direction while holding the source wake
on body x. Native AVL explicitly uses geometric axes and body rotation rates.
This is not a retrimmed aircraft or the full unsteady case.

Each interval becomes one AVL span interval with one chordwise vortex.
Conversion retains physical-component identity, transfers normal to streamwise
chord using the local span direction, and includes elastic section orientation,
literal incidence, equilibrium control increments and CLAF. Vortex endpoints
agree within **4.441e−16 ft**. Receiver differences remain, up to **0.248480 ft**;
they are measured rather than presumed absent.

Five native executions cover zero rate and `omega/V = +/-0.0001 rad/ft` about
body x and z. A separate reconstruction uses the exported native geometry,
normals and velocity fields:

| Native reconstruction check | Maximum error |
| --- | ---: |
| Circulation, relative | 1.285e−15 |
| Bound-receiver induced velocity / unit freestream | 3.817e−17 |
| Integrated force/moment coefficients, absolute | 6.662e−16 |

## Core laws and receiver conventions

Drela's steady **Eqs. 160–161, p. 33** prescribe zero core on the same physical
surface and the integral with denominator `(distance² + core²)^(3/2)` between
different surfaces, with `core = max(chord/4, interval length)`. The current
source implementation retains that prescription.

Native AVL 3.52 uses the quartic Leishman expression in
[aic.f](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/aic.f).
This diagnostic explicitly retains its native defaults **CC=0, CW=2**:
different-component core radius is two transverse strip widths;
same-component radius is 0.0001 transverse strip widths. The independent
native reconstruction also retains its rounded `PI4INV`. These are distinct
methods, not an assumed common regularization.

The operator replay changes conventions in this declared order: native →
source kernel with native radii → source radii → source control points →
section normals → force-velocity receivers → force vectors → moment arms.
Its endpoints reproduce both native and OpenSwing results. Increments depend
on that order; they are not unique additive physical errors.

Percent differences are `(OpenSwing/AVL − 1)*100`; all signed derivatives are
retained in the machine output:

| Scope and moment | Rate input | Difference |
| --- | --- | ---: |
| Total roll moment | Roll | −0.956% |
| Total yaw moment | Roll | −1.846% |
| Total roll moment | Yaw | −0.850% |
| Total yaw moment | Yaw | −3.766% |
| Fin yaw moment | Roll | +5.848% |
| Fin yaw moment | Yaw | −4.589% |

The fin yaw-rate difference is dominated by control-point placement. Core
changes matter more for the smaller roll-driven fin response: the intermediate
source-core stage is about 113% of native, before receiver changes bring it
to 105.85%. This differs from the isolated-fin result because the other
surfaces now affect its flow.

Large relative differences remain. Total vertical-force derivative with roll
rate is **0.03657 versus 0.16606**, a **354%** difference in the unit-flow
diagnostic. Fin roll-moment derivative with roll rate is **−31.9296 versus
−10.8952**, a **−65.88%** difference. Stabilizer/fairing cross-axis results
also differ appreciably. Agreement of the four dominant total lateral moments
does not validate these quantities or establish native-ASWING equivalence.

## Direct airflow pathways in the full dynamic model

This separate calculation uses the complete **Mach 0.1, 6.7 m/s** source model,
including body, engine, structure, free-frame motion, lag, apparent inertia
and the live wind-aligned wake. Its 2,044-coordinate descriptor is unchanged
except for the explicitly removed diagnostic blocks.

Each block contains source circulation and nodal-pose columns in the target's
circulation equations and aerodynamic nodal loads. Target global force/moment
rows are reconstructed from those nodal loads at the fixed target positions.
Wing-to-fin removal therefore includes effects of changing the wing's vortex
strength, position, orientation and geometry/core on fin loads and circulation.
Fin-to-wing removal is analogous. Both blocks are checked against two
fourth-order nonlinear directional stencils along the actual dip response.

Maximum block-action difference is **1.761e−13** scaled residual, or
**8.576e−8** relative to the largest component of the corresponding action.
Earlier circulation-only blocks remain separate. No changed aircraft is
retrimmed: an affine offset preserves the mean loaded state and mean wake.
Structural, free-frame and indirect aerodynamic pathways remain active.

| Frequency, Hz | Wing → fin removed: yaw change | Fin → wing removed: yaw change | Both removed: yaw change |
| --- | ---: | ---: | ---: |
| 0.1 | +0.02052% | +0.33860% | +0.35876% |
| 1.157378 | +0.06961% | −0.21669% | −0.14705% |
| 2.0 | −0.01730% | −0.04206% | −0.05939% |

These are full harmonic solves, not first-order output estimates. At the dip,
baseline yaw is **0.07421777** and removing both gives **0.07410864 deg/s/F3**.
Both remain far above the drawing's **0.03398619**. The separate
circulation-only diagnostic gives **0.07410700**, so including vortex motion
in this direct-channel accounting barely changes the conclusion.

This does not show that wing/tail coupling is unimportant: the mechanically
coupled modes and free-flight feedback in the
[mode-shape](daedalus-mode-shapes-20261114.md) and
[modal-load](daedalus-modal-loads-20261114.md) studies remain. It specifically
constrains the direct mutual-vortex hypothesis. Fin response to its own local
and aircraft-frame motion remains a separate mechanism.

## Evidence and execution

- [Combined results](../../artifacts/daedalus-coupled-avl-20261114/report/result.json),
  [steady derivative CSV](../../artifacts/daedalus-coupled-avl-20261114/report/steady-derivatives.csv),
  [feedback CSV](../../artifacts/daedalus-coupled-avl-20261114/report/feedback.csv),
  [SVG figure](../../artifacts/daedalus-coupled-avl-20261114/report/coupled-avl-feedback.svg).
- [Native driver](../../scripts/check_daedalus_coupled_avl.py),
  [convention replay](../../scripts/replay_daedalus_coupled_avl.py),
  [feedback diagnostic](../../scripts/check_daedalus_circulation_feedback.py),
  [report generator](../../scripts/report_daedalus_coupled_avl.py).

Fifteen bounded serial jobs are retained: **13 completed and two rejected**.
The first two feedback-solve attempts rejected before solving because the new
diagnostic had not marked its matrices immutable, as required for reusable
beam factors. The runner now marks matrix data/index arrays read-only; no
solver safeguard or threshold changed. Both attempts and their runner
snapshots remain. All 16 completed harmonic solves pass the original
full-equation checks. Every diagnostic parent and native child was reaped.

Each child used one BLAS thread, 512 MiB address space, 15 CPU seconds and
25 wall seconds; native calls additionally had an eight-second limit. The
figure was visually inspected. Production code, aircraft inputs, source
catalog, ISAE fractions and progress history are unchanged. Browser/build
jobs remain held.
