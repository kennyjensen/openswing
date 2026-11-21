# SA-13: body integration corrected at spline knots

The current source now splits body integration at radius and drag-table spline
knots. This fixes a numerical error in integrating Drela's existing equations;
the radius interpolation, source core, physical force law and structural mesh
are unchanged. **38 targeted implementation checks pass**, including eleven new
regressions. **SA-13 remains 0/612** because these checks do not recover the
original ASWING inputs or resolve the archived observable conventions.
SA-12 remains open.

## Error and correction

The previous body rule used eight Gauss points across each structural interval,
even when it crossed several cubic spline pieces. Gauss integration of a single
polynomial is exact through its supported degree; that guarantee does not apply
across internal spline knots. Consequently, even uniform-flow body forces could
differ from the exact area-change identity in Drela's **steady Eqs.68–69,
printed p.16**:

`integral f_z ds = rho U² sin(alpha) cos(alpha) [pi R²]`.

The new rule uses eight Gauss points within each material spline piece, also
splitting at `Cdf` and `Cdp` knots for profile loads. It preserves the old
eight-point rule when there is no internal knot. It adds integration points,
not structural nodes or fitted geometry.

The shared rule is used for forces, local moments, apparent mass and the volume
source/doublet field. The PG weights and analytic state/geometry derivatives
now use those same material weights and locations. The state-derivative storage
guard counts the expanded rule before allocating its source arrays. Padded
slots have zero weight; arrays retain their per-element shape for elastic
motion and nodal force transfer.

## RS1 force-integral diagnostic

The unchanged, explicitly reconstructed RS1 outline is tested with uniform
unit-speed flow, density one and 9° incidence. Exact endpoint areas provide the
oracle; no archived aerodynamic value is fitted or used as an acceptance target.

| Intervals | Previous maximum strip-force error / peak strip force | Corrected maximum absolute strip-force error (N) |
|---:|---:|---:|
| 8 | 4.4739% | 3.90e-18 |
| 32 | 0.08551% | 4.55e-18 |
| 64 | 0.01964% | 4.72e-18 |

The corrected force integrals are at floating-point roundoff on all three
meshes. This statement concerns the uniform-flow area identity, not every
load under spatially varying incident velocity. The error at 32 intervals was
already much smaller than the unresolved archived-curve discrepancies.

The [before record](../../artifacts/isae/sa13-quadrature-20261109/baseline.json)
and [after record](../../artifacts/isae/sa13-quadrature-20261109/after.json)
pin the unchanged model, all 141 production modules and the three changed
modules. The [reproducer](../../scripts/verify_sa13_body_quadrature.py) performs
only direct kernel evaluations under 512 MiB / 15 CPU-second / 25 wall-second
limits with one BLAS thread.

## Pressure-field numerical check

A separate check reuses the saved independent adaptive integration of the
regularized source law at the 22 pressure measurement stations. It authenticates
the original oracle, its script and the unchanged reconstructed geometry.
Loading the saved before-kernel in an isolated module reproduces the historical
32-interval velocity values within 2e-12 m/s.

| 32-interval calculation | Maximum velocity-component error (m/s) | Maximum error in `100 Cp` (percentage points) |
|---|---:|---:|
| Previous rule | 0.00112184 | 0.0138309 |
| Rule split at knots | 0.000470911 | 0.00804511 |

This field integral is not polynomial, so the corrected eight-point rule still
has finite error. The test compares the same `R/2` core and full Bernoulli
observable, without altering pressure normalization. It does not validate the
experimental curve, the missing original sensor setup, or the conflicting
archived pressure point above `100 Cp`.

The cost is additional integration points: this pressure field retains 1,024
source slots instead of 256, including zero-weight padding. No speedup is
claimed. Packing those unused slots consistently with derivative bookkeeping
is a separate efficiency opportunity. The bounded
[pressure reproducer](../../scripts/verify_sa13_pressure_quadrature.py) and
[results](../../artifacts/isae/sa13-quadrature-20261109/pressure.json) preserve
the comparison; no nonlinear solve was required.

## Regression coverage

The [test receipt](../../artifacts/isae/sa13-quadrature-20261109/checks-v2.json)
records 38 distinct passing checks, run in small serial batches:

- Eleven new checks: exact force/moment and PG source/doublet integrals under
  both spline policies; profile-drag knots; the unchanged unsplit rule;
  state/PG/image derivatives; and both geometry-coordinate charts with
  frozen and current influences.
- Thirteen existing state-field/guard checks covering bodies, point objects,
  shoulders, ground images and allocation limits within the selected tests.
- Fourteen existing volume/body checks, including body-only and mixed
  aero-structural equilibrium, apparent inertia and independent integration.

The moving-pylon coupled test initially failed at its expectation that moving
the pod changes circulation. All three unchanged before-modules reproduce that
same failure: the test implicitly used the newer frozen-influence default.
It now explicitly selects **current influences**, matching its stated purpose,
and passes. No tolerance or production default changed. The
[baseline failure](../../artifacts/isae/sa13-quadrature-20261109/baseline-test-result.json)
is retained. Two initially unsupported three-panel test fixtures were corrected
to the existing minimum of four panels before the new regression count was
recorded.

Production changes are confined to
[`volume.py`](../../openswing/volume.py),
[`volume_state_tangent.py`](../../openswing/volume_state_tangent.py) and
[`geometry_partials.py`](../../openswing/geometry_partials.py).
[New tests](../../tests/test_body_quadrature.py) check physical integrals and
independent derivative stencils rather than archived curve fitting.

Browser, WebAssembly packaging and build verification remain under the existing
UserLAnd hold. No whole-family native rerun, pass-fraction change or scope change
is claimed. The [normalization/derivative audit](isae-sa13-load-integrals-20261109.md)
and [primary-geometry conflict](isae-sa13-primary-geometry-20261109.md) remain open.
