# SA-11 winglet Mach rejection and finite cores

The bundled upper-winglet and upper/lower-winglet models reject even at the
interface's initial aerodynamic settings: rigid prescribed geometry, 30 m/s,
5 degrees incidence, zero sideslip, 48 requested intervals per beam, frozen
influences, automatic PG Mach and wake-core ratio 0.25. This is a local
induced-velocity problem; these rejected states are not predictions of physical
supersonic flow.

Six small serial native calls used one BLAS thread. The
[driver](../../artifacts/isae/sa11-winglet-core-20261107/reproduce.py) and
[complete conditions and diagnostics](../../artifacts/isae/sa11-winglet-core-20261107/results.json)
are retained. Each model was run at the initial settings and at 240 m/s with
core ratios 0.25 and 1.0. No solver implementation or input geometry was changed.

| Model | Speed, m/s | Core ratio | Maximum local normal Mach | Receiver beam |
|---|---:|---:|---:|---:|
| Upper winglets | 30 | 0.25 | 3.593822 | 3 |
| Upper winglets | 240 | 0.25 | 24.76856 | 3 |
| Upper winglets | 240 | 1.0 | 24.76856 | 3 |
| Upper and lower winglets | 30 | 0.25 | 10.35774 | 4 |
| Upper and lower winglets | 240 | 0.25 | 96.00893 | 4 |
| Upper and lower winglets | 240 | 1.0 | 96.00893 | 4 |

The upper-winglet receiver is 0.05631705 mm from its largest contributing
main-wing trailing ray. At 30 m/s this individual grouped wake term contributes
5339.407 m/s; other terms partly cancel it, leaving a section-normal speed of
1222.654 m/s. In the upper/lower model, the largest grouped wake term originates
on the receiving lower-winglet strip and lies 0.02201191 mm from the receiver.
These are force-point diagnostics, not tangency-control-point distances.
The circulation residuals are below 7.1e-14; converged tangency does not certify
the force-point velocity.

## What Drela documents

- The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
  **Wake Vortex Core Radius — W**, recommends a chord ratio of 0.25 and gives
  `radius = max(ratio * chord, interval_width)`.
- Its **Physical index** section specifies zero core for mutual influences
  between beams sharing a physical index. Its example is a main wing plus
  winglet. It also warns that close trailing-leg/control-point encounters can
  cause serious numerical noise with this declaration.
- The [steady Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=33),
  section 4.2, equation 161, introduces the finite core for influences from
  other surfaces. It gives `epsilon = max(chord/4, interval_width)`.
- The [AVL User Primer](https://web.mit.edu/drela/Public/web/avl/AVL_User_Primer.pdf),
  **COMPONENT** and **Discretization**, likewise excludes finite cores between
  surfaces sharing a component, explicitly including wing/winglet components.

Every beam in these two SA-11 inputs has physical index 1, including after
parsing. Their mutual lifting influences therefore correctly receive zero core
under the documented rule. Increasing the UI core setting does not change
those coefficients: both 240 m/s pairs have identical complete rejection
diagnostics. The configured finite-core implementation already exists in
OpenSwing; this failure is not evidence that it is missing.

## Next investigation

Inspect the junction's bound-vortex endpoints, shared trailing-ray grouping,
circulation carryover, and force/control-point placement against the published
geometry definitions. Separate the cross-beam junction encounter in the upper
model from the same-strip lower-winglet contribution and the already documented
[swept force-velocity limit](swept-lifting-line-limit.md). Check candidate
corrections on nearby discretizations and the unswept/isolated-wing controls.

Adding a nonzero core to these same-physical-surface interactions could bound
their singular velocities, but would change the documented method and possibly
the circulation carryover. It is not an established ASWING-parity fix. Changing
physical indices or reducing resolution just to avoid the guard also does not
establish validity. Keep the local-Mach guard and require any justified change
to be reflected consistently in loads and derivatives.

No ISAE completion fractions or comparison scopes changed.

The [subsequent junction investigation](isae-sa11-winglet-junction-20261107.md)
independently verifies the endpoint construction, separates the upper root's
finite-segment field from its small circulation jump, checks AVL 3.52's tiny
same-component numerical core, and compares current-wind influences. Unfreezing
allows the upper model to compute at 30 m/s and 5 degrees on two checked meshes;
the upper/lower model still rejects and local-flow convergence remains unresolved.
