# Source structure coupled to airflow dynamics

2026-10-30. `drela-moving-airflow-v1` connects the source beam equations and
moving-frame inertia to the unsteady lifting-line residual. It supports
coupled modes, frequency response and nonlinear time response for lifting
beams. The browser exposes it as **ASWING structure + airflow dynamics**.
It remains experimental; this is not evidence of complete ASWING reproduction.

## Equations and scope

The source moving operator supplies real-mass inertia, gravity, material
damping and canonical fixed/prescribed/free/mixed frame equations. The shared
aerodynamic evaluator supplies circulation, its lag equation and rate-dependent
lift, nonlinear section behavior, profile/tangency drag, and the full thin-strip
apparent-fluid wrench. Aerodynamic controls and gusts remain active inputs.
Supported time forcing uses the existing ASWING table reader.

Aerodynamic quantities retain the Glauert section points of steady Eqs.150–160.
The integrated aerodynamic wrench is transferred symmetrically about the
arithmetic structural midpoint, preserving the source operator's mixed
section-resultant meaning. The steady source-coupled path now shares this load
assembly. The real-inertia cache is kept separate; no second apparent-mass
matrix is added to the aerodynamic acceleration loads.

This airflow policy deliberately has its own numerical identity. Its fluid
quadrature differs from the stationary endpoint-fluid policy, even though they
share the thin-strip load formulas. Historical ASWING dynamic agreement and
refinement of general coupled configurations remain unverified.

The subsequent [powered airflow extension](source-airflow-engines.md), also
dated 2026-10-30, enables engine types 0/1/2 and power inputs. The original
verification record below predates that extension. The current route still
rejects bodies, struts, stepped axes, feedback and inverse actuator/history
targets. These remain required project work. The
existing broader implementation paths remain available; their existence does
not establish that every feature uses the source structural discretization.

## Analytical and numerical checks

The focused checks cover:

- Four rigid/flexible, mass/no-mass cases matching the source steady residual
  at zero local motion, including nonzero trial geometry.
- Independent thin-strip pitch, heave and angular-acceleration force/moment
  limits, circulation-rate lift, cache invalidation and separation from real
  inertia. Prescribed off-equilibrium circulation tests include tangency drag.
- A four-horseshoe control response with analytic bound/wake integration,
  with circulation lag enabled and disabled. Complex lift and pitching moment
  agree, and the response satisfies the full descriptor matrix equations.
- Dense and sparse matrices for a flexible, tapered lifting beam with
  nonzero frame motion, checked against independent directional residual
  differences.
- Four aerodynamic relaxation poles matching eigenvalues of the independently
  integrated four-horseshoe equation.
- A small control step with analytical matrix-exponential circulation and lift.
  At `t=0.04`, reducing BDF2's maximum step from `0.004` to `0.002` reduces
  relative lift error from **0.02498% to 0.00546%**. Circulation and its time
  derivative are also checked. The step amplitude is `1e-4`, so this verifies
  the small-disturbance limit of the nonlinear implementation.
- JSON checkpoint replay and continuation matching an uninterrupted time run.

The packaged WASM kernel passes **122 grouped comparisons, 276 scalar
components**, against native frequency, mode and time outputs. These checks
use the same 132 production modules shipped to the browser. Native analytical
tests provide the independent physical references; native/WASM agreement alone
is not an independent physics validation.

Across the focused native and affected regression suites, **190 tests pass**;
the complete JavaScript suite passes **200 tests**. The final built-browser
scenario passes offline frequency solving and matrix reuse, time integration
and checkpoint continuation, shifted-Arnoldi modes, and saving/reopening all
three analyses without recalculation. It also checks the narrow mobile layout
for horizontal overflow. See the [verification summary](source-airflow.json).

An early modal evidence export failed because complex eigenvalues were passed
directly to JSON. Serializing real/imaginary pairs corrected the harness; its
physical assertions had passed. The original log is retained. Initial browser
testing found a real omission in saved-solution policy validation, which was
corrected. A subsequent harness attempt needed to open the forcing-table
details before editing its textarea. Another harness assertion needed to include
the original restart context that continuation intentionally attaches to retained
snapshots. The corrected comparison checks every retained snapshot and its
original context exactly. These harness corrections did not change physics.

## Evidence and remaining validation

Native tests are in `tests/test_source_airflow.py`,
`tests/test_source_airflow_time.py` and `tests/test_source_airflow_policy.py`.
The WASM runner is `scripts/test-source-airflow-wasm.mjs`; the browser scenario
is `tests/browser/source-airflow.spec.js`. The verification model is
[`source-airflow-check.asw`](../../examples/source-airflow-check.asw).
Logs, requests, native outputs and the WASM record are retained under
[`artifacts/isae/source-airflow-20261030`](../../artifacts/isae/source-airflow-20261030).
The final verification and distribution receipt is recorded separately there.

The control example isolates aerodynamic dynamics; it is not a flexible
full-aircraft benchmark. The flexible matrix checks verify assembly but do not
establish archived flutter or Bode agreement. Further work must cover the
remaining source-model features, coupled mesh/time refinement and the archived
ASWING cases. ISAE counts and the 3% acceptance policy are unchanged.
