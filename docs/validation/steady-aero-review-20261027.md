# Steady aerodynamics: review against Drela's documentation

Reviewed 2026-10-27. **The principal lifting-surface equations agree with the
published formulation. Full numerical equivalence to ASWING is not established.**
SA-1 remains **19/154** strict archived-output checks, with all 22 solves completing.
No aerodynamic equation, model input, or acceptance tolerance was changed during
this review.

The primary specification is Drela's [ASWING 5.99 steady technical
description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf), dated
10 March 2015, supplemented by the [user
guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt). The SA-1 archive
labels its results ASWING 5.96. Agreement with the published equations and
reproduction of that archived executable's numerical choices are separate checks.

## Findings requiring attention

1. **Confirmed departure: default fuselage apparent mass differs from the printed
   formulation.** [FlightCondition](../../openswing/aero.py#L130) defaults to
   `body_added_mass_factor=1`; [body_loads](../../openswing/volume.py#L141) therefore
   applies `-rho*pi*R^2*a_perp`, whereas steady Eq. 86 prints
   `-2*rho*pi*R^2*a_perp`. Setting the existing option to 2 reproduces that printed
   coefficient. This was an explicit classical-cylinder convention, documented in
   [NUMERICS](../NUMERICS.md), rather than evidence of ASWING executable parity.
   It matters for accelerating/turning fuselages, including quasi-steady cases;
   it vanishes for a stationary body and cannot explain SA-1, which has no
   nonlifting body. This review records the departure without changing unrelated
   physics while SA-1 is the priority.

2. **Confirmed validation-setup issue: `NODE I200` was treated as 200 intervals.**
   The [polar adapter](../../scripts/isae_suite_polars.py#L196) calls this
   `declared_panels` and uses 200/400 intervals. The
   [version notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt),
   v5.67, describe `i` as a request for a number of *nodes*. They do not establish
   the resulting SA-1 node array, breakpoint allocation, or Fourier count. The
   current grids are therefore reconstructions, not proven original ASWING
   discretizations. `OPER K I100` is the Newton iteration limit, not a circulation
   mode count. This must be reflected in future comparison metadata; simply
   renaming 200 panels as 200 nodes does not recover the historical mesh.

3. **Unresolved load-transfer detail: the paper does not unambiguously settle the
   discrete force quadrature.** Section 2.1 defines subscript `a` as an endpoint
   average and Eq. 56 uses `f_a * delta_s`. Section 4.2 redefines `a` as the
   Glauert-angle midpoint *in that section* and locates the aerodynamic force there.
   [OpenSwing](../../openswing/aero.py#L559) uses the sampled force times interval
   length. Its sampled force obeys the local force law, but the text alone does
   not prove identical load transfer in the historical executable. A diagnostic
   Fourier endpoint-trapezoid replacement changes attached circulation lift by
   only 0.00000447 at 200 intervals and 0.00000112 at 400; the observed total-CL
   discrepancy is about 0.0000840. This particular alternative does not explain
   the mismatch and has not been adopted.

4. **Other numerical choices remain qualified.** Default pointwise circulation
   is expressly allowed by Eq. 62; the Fourier alternative is also implemented.
   Historical Fourier count, exact node spacing, startup Mach/fast-mode settings,
   and executable stall constants are not recovered from the SA-1 files.
   Natural cubic beam interpolation is explicit; the guide does not specify its
   end conditions. Body quadrature uses eight Gauss points per interval and
   excludes a body's own volume field from its incident velocity. Those choices
   need separate executable comparisons before claiming numerical identity.
   Straight geometry and constant section properties make interpolation policy
   irrelevant to SA-1.

5. **Unresolved curved-wing self influence.** The interior force point can be
   off its own straight bound-vortex segment on curved geometry, but the code
   excludes that entire own bound segment from the force-point velocity. The
   source does not fully specify this noncollinear case. The straight SA-1
   calculation cannot verify that convention. The [geometry
   review](steady-aero-review-20261027/pg-review.md) also records the distinct
   physical/virtual quarter-chord descriptions in the steady and unsteady papers.

## Equation-to-code review

| Component | Documentation | Implementation | Review result |
|---|---|---|---|
| Relative flow and axes | Eqs. 1, 64–66 | `FlightCondition.vectors`; `aero.py` flow assembly | Signs and reference-point rotation terms agree. |
| Pointwise/Fourier circulation | Eqs. 62–63, 150–153 | `circulation.py` | Both permitted representations exist; Fourier samples use the material Glauert midpoint. |
| Flow tangency | Eqs. 200–201 | `aero.py` residual and `CirculationBasis.test` | Fourier residual uses `sin(k theta) * delta_theta`; the common `2/pi` scaling does not change its roots. A truncated series need not satisfy every local residual. |
| Wind-aligned vortex geometry | Eqs. 154–159 | `frozen_influence.py: lifting_geometry` | Bound/control offsets and section normal/control rotation agree. |
| Compressibility | Eqs. 146–149 | `aero.py` PG matrix; vortex velocity transformation | The symmetric physical-axis transform is algebraically equivalent to the paper's rotated, stretched coordinates. Velocities use the transpose transform, not its inverse. |
| Biot–Savart and wake cores | Eqs. 160–161 | `aero.py` kernels; `factored_influence.py` | Independent scalar replay verifies the SA-1 kernel. Default cross-surface core follows `max(c/4, delta_s)`; the chord ratio is configurable. Own physical surface has zero core; curved self-influence is qualified above. |
| Lift and local section CL | Eqs. 67, 69, 202 | `aero.py` velocities and load assembly | `rho*Gamma*(V cross s)` and `2*Gamma/(c*V_perp)` agree. No freestream-speed substitution or fitted lift multiplier is used. |
| Separation/stall | Eqs. 203–204 | `aero.py: _stall_leakage`, residual | Same logarithmic leakage function and velocity scaling. Defaults 40 and 0.05 equal the paper's approximate suggested values, not independently verified 5.96 defaults. |
| Profile drag and section moment | Eqs. 70, 72–74 | `aero.py` load assembly | Friction, pressure, separation-drag and quarter-chord moment terms agree. CP tangency is used in separation drag; the force velocity is evaluated at the bound-vortex point. |
| Frozen influence option | Section 4.6; guide K/F | `frozen_influence.py`; `aero.py` | Jig geometry and zero wind angles are used for frozen coefficients; circulation and loads remain live. Current SA-1 runs explicitly disable freezing. |
| Trefftz outputs | Eqs. 207–211 | `trefftz.py` | Circulation lift/side force and efficiency definitions agree. The discrete wake-energy quadrature is explicit; exact historical quadrature is unverified. Total CL is not substituted for Trefftz CLi. |
| Slender-body flow and profile loads | Eqs. 68–71, 162–164 | `volume.py` | Formula-level review agrees; numerical quadrature/self-exclusion qualifications remain. Apparent-mass departure is listed above. |

The PG equivalence is useful to state explicitly. If the paper uses
`P = D R`, with `D = diag(1/lambda,1,1)` and wind rotation `R`, the implementation
uses `Q = R.T D R = I + (1/lambda-1) e e.T`. Rotational covariance of Biot–Savart
and the transpose velocity transformation make these equivalent. Also
`xi/|xi cross s| = e/|e cross s|`, so the physical bound/control-point offsets
do not require an extra Mach factor.

The review concentrates on the aerodynamic operator and its SA-1 application.
It is not a new certification of every engine model, wall-contact configuration,
coupled structural policy, or dynamic feature.

## Independent numerical evidence

The fresh [registered baseline](../../artifacts/isae/sa1-focused-baseline-20261027/report.md)
completed all 22 jobs. An [independent saved-evidence
audit](isae-sa1-current-evidence-20261027-fresh-fourier.json) reproduced all counts:
154 finite outputs, 19 matches, and 198 passing numerical checks. No complete
seven-output row matches. All 19 matches are nonzero drag/CD/CDi outputs.

A [declared six-solve diagnostic](../../artifacts/isae/sa1-basis-diagnostic-20261027/protocol.json)
compared pointwise circulation with 40 Fourier coefficients at the existing
200/400 meshes, for one attached and one stalled row. Forty coefficients were
motivated by the ISAE report, not selected by fitting. The change is far too small
to explain either discrepancy; this does not identify the original Fourier count.
The diagnostic retains complete strip fields and both projected/local residuals.

An independent [scalar horseshoe calculation](steady-aero-review-20261027/oracle.py), with no production solver imports,
reconstructed those six saved states. Maximum discrepancies were approximately
`8e-13 m/s` in velocity, `2e-14` in local normalized residual, and `6e-12 N` in
total force. This checks the sampled operator rather than merely recomputing
coefficients from an already stored total force. It does not verify that the
historical ASWING run used the same samples or quadrature.
Its six independent sanity checks also pass, including direct line integration,
the two-dimensional lift-slope limit, and dimensional scaling; see the
[pinned receipt](steady-aero-review-20261027/pg-review.json).

Attached-flow CL differs by about **+0.058%**; at 18.091 degrees it differs by
**−2.67%**. The finest-mesh induced-drag difference at the latter point is about
**−4.68%**. Refinement from 200 to 400 intervals and the tested basis change do
not account for these gaps.

The [complete SA-1 source inventory](isae-sa1-source-readiness-20261027/report.md)
retains every original file and target candidate. The native table provides
77 outputs, checked on two meshes. Modified/relabelled figure curves with
conflicting provenance are retained as candidates, not silently treated as
native ASWING targets.

Review receipts and specialist derivations are in
[steady-aero-review-20261027](steady-aero-review-20261027/).
The focused regression run passed **145 tests** in 77.76 seconds, covering
aerodynamics, circulation representations, Trefftz outputs, frozen influences,
stall parameters, volume/body loads, and ground images. These are implementation
checks, not additional archived-ASWING matches.
SA-1 remains the active implementation priority. The next correction must be
supported by the source equations or recovered run settings; this review does
not support changing lift gains, stall limits, or pass tolerances to fit the archive.
