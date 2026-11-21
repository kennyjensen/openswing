# SA-11: the remaining adjacent-bound peak follows the sharp-corner limit

2026-11-08 UTC. The strongest bound contribution in the two aligned native AVL
meshes comes from the main-wing filament ending at the winglet's first bound
row. An independent incoming-line limit predicts its coarse-to-fine growth
within **0.0005%**. This supports the identified sharp-corner mechanism; it
does not establish an accepted solution or justify removing that influence.

The production change is limited to **failure diagnostics**: bound sources now
include their physical distance from the failed receiver, closest point, and
the geometric turn at an exactly shared bound endpoint. The plain exception
includes that context when a bound source is the largest reported contribution.
No aerodynamic equation, circulation, force, core or Mach gate changes.
**SA-11 remains 163/4,592 at 5%.**

## Published force sampling

The [steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf)
specifies the following sequence; the current implementation follows it:

| Equations / printed page | Requirement | Implementation |
|---|---|---|
| 64–67 / pp. 15–16 | Total relative velocity includes induced flow; lift uses it at the bound-vortex location. | `evaluate_aerodynamics` evaluates the bound receiver, then `rho * Gamma * cross(V, s) * ds`. |
| 69, 72–73 / pp. 16–17 | Section profile moment uses beam-normal velocity and its local Mach. | The span projection, local Mach check and section PG factor remain. |
| 155–156 / p. 32 | Bound receiver and flow-tangency control point are distinct. | `lifting_geometry` constructs both separately; control-point velocity is not substituted into the force law. |
| 160–161 / p. 33 | Biot–Savart influence sums all beams, with a finite core for other physical surfaces. | The adjoining bound filament is retained; shared physical index has zero mutual core. |

The [user guide's physical-index section](../../reference/aswing_doc.txt:1017)
explicitly describes a wing and winglet as separate logical beams sharing a
physical index, and warns about close wake/control-point encounters without a
finite core. Neither cited source specifies dropping the neighboring bound
filament at a sharp corner. This source audit does not recover undocumented
native ASWING behavior at that corner.

## Independent endpoint calculation

Use the saved [aligned-root native states](isae-sa11-native-root-conformity-20261108.md):
report-derived −4° twist, alpha 1°, PG `240/340.21`, frozen body-x wake, identical
physical boundaries. No new equilibrium solve is run.

Let the incoming main-wing filament end at `O`, and let the receiver be
`O + r*u` along the outgoing winglet filament, with physical unit direction
`u`. In PG space, define `U = P*u` and the incoming unit direction `t`.
The limiting velocity from the incoming semi-infinite filament is

```
V_limit = Gamma/r * P^T (t × U) / [4*pi*(|U|² + |U|*(t·U))].
```

The direction change at this junction is **54.5910°**. The incoming finite
segment approaches the above `Gamma/r` field as the receiver approaches the
endpoint. This is an analytical reference for the existing field, not an added
vortex or a force correction. The arithmetic preserves native AVL's rounded
`1/(4*pi)` constant for comparison.

| Span positions across physical beams | Receiver distance from joint | Adjoining circulation | Adjoining bound-source speed | Norm of all other bound contributions | Relative limit error |
|---:|---:|---:|---:|---:|---:|
| 64 | 0.630436 mm | 1.037122 m²/s | 58.0530 m/s | 9.8885 m/s | 0.006764% |
| 128 | 0.157704 mm | 2.531598 m²/s | 566.4870 m/s | 8.4868 m/s | 0.006269% |

The measured source-speed ratio is **9.7581003**. Its ratio predicted from
circulation and receiver distance alone is **9.7580520**. No parameter is fitted.
The full bound-field vectors reproduce the preceding independent quadrature
check within 1e−7 m/s. Individual vector norms must not be added as scalar flow
speeds. Wake effects remain part of the actual total field.

![Adjacent-bound endpoint limit](../../artifacts/isae/sa11-shared-bound-corner-20261108/bound-corner.png)

[SVG](../../artifacts/isae/sa11-shared-bound-corner-20261108/bound-corner.svg).
The plot was visually checked and uses the application's color order.

This proves the moving-receiver mechanism for these saved straight-filament
states. It does not prove divergence at every fixed physical location, a
continuum solution, or a native ASWING implementation detail. Close integrated
lift/CDi agreement remains insufficient for valid local section forces and
moments. No adjacent-source exclusion or control-point substitution is adopted.

## More useful failure context, with unchanged flow

The new observer reports geometry in physical coordinates, even when the
influence coefficients use PG or ground images. A shared endpoint requires
exact coordinate equality; nearby roots are not silently joined. The geometric
turn is independent of the stored circulation orientation. It adds no matrix
assembly or flow evaluation to the existing failure path.

A replay of one retained production SA-11 failure at alpha 5°, current-wind
influences, adds the following information to its existing error:

> Distance to its physical bound segment=0.005086355 (input L). Shared bound
> endpoint with a 70.63063-degree geometric turn.

That is the swept main-wing center, a different location from the aligned
native winglet-root study. Its saved circulation and velocity remain fixed;
one recomputed influence row reproduces the rejected velocity within
**1.71e−13 m/s**. The state remains rejected. It also has two sections beyond
their lift limits, so this replay is only a diagnostic check, not post-stall
repair or a new reference pass.

The focused tests pass: **23 passed in 13.18 s** across
`tests/test_airflow_diagnostics.py` and `tests/test_section_airflow.py`, using
one BLAS thread. They cover PG/image reconstruction, current/frozen source
geometry, wake cancellation, physical distances, endpoint orientation, and
nonmerging of a nearby but distinct root. The development server serves this
current Python module; packaged builds include it through the existing prepare
step. No full browser or full-suite rerun is claimed for this diagnostic edit.

Evidence: [endpoint analysis](../../artifacts/isae/sa11-shared-bound-corner-20261108/analysis.json),
[analyzer](../../scripts/analyze-sa11-shared-bound-corner.py),
[error replay](../../artifacts/isae/sa11-shared-bound-corner-20261108/error-context.json),
[replay driver](../../scripts/verify-sa11-bound-error-context.py).
The endpoint analysis precedes the observer edit; its older observer hash is
retained. The verification receipt records that intentional diagnostic-only
change separately from unchanged aerodynamic operators and inputs.

The primary SA-11 adapter still covers the original baseline and extension
tables only. The next coverage task is to audit and register the original
upper and upper/lower winglet polars, including their normalization and driver
settings. Those original-input comparisons must remain separate from the
report-derived −4° diagnostics. No scope or denominator is expanded by this
report alone.
