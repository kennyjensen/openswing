# Source structural frequency response

2026-10-30. Frequency response now routes the explicit source structural
operators through the existing full descriptor solver. The physical residual,
source endpoint-average real inertia, source material damping and selected
still-air apparent inertia are the same operators used by eigenmodes.

This extends a supported analysis; it does not replace the aerodynamic model,
change an ISAE acceptance threshold, or establish historical ASWING parity.
Circulatory source dynamics and full-aircraft source Bode validation remain
unfinished.

## Equations and supported inputs

Drela's *ASWING Unsteady Extension*, section 13.2, Eqs.135–136, solves
`(i omega M - A) xhat = B uhat` and recovers rate-dependent outputs with
`(C + i omega Q) xhat + D uhat`. OpenSwing retains that full descriptor form;
no modal truncation or pseudoinverse has been introduced. Singular responses
remain gaps, and every computed response retains the original full-equation
residual checks. Coefficients are frozen at the loaded base; a response about
a drifting/rotating base requires the timescale qualification described in
the source document immediately before section 13.2.

The source policies all require `beam_interpolation: drela-segspl-v1`:

| Structural operator | Frames | Frequency inputs |
|---|---|---|
| `drela-fixed-vacuum-v1` | Fixed | Compatible structural initial disturbances |
| `drela-fixed-still-air-v1` | Fixed, explicit positive fluid density | Compatible structural initial disturbances, with thin-strip apparent inertia |
| `drela-moving-vacuum-v1` | Fixed, prescribed, free, mixed | Initial disturbances; active frame load targets and prescribed accelerations for moving frames |

Initial spectra solve `(s M - A) X = M x0`, with rate transform `s X - x0`
and `s = sigma + i omega`. They are one-sided Laplace spectra, with an extra
time unit in their output units. The existing finite-constraint completion
and spectral-abscissa gate remain active. A fixed-frame initial spectrum is
not a rudder or other aerodynamic transfer function.

No source policy here accepts airflow, gusts, aerodynamic controls or feedback.
The fixed policies retain their stationary-frame restriction. The still-air
policy adds the acceleration-linear part of Eqs.41–44; it does not enable
nonlinear fluid dynamics. Existing midpoint frequency behavior remains available.

## Matrix ownership and saved identity

`frequency_response.FrequencyAnalysis` receives the explicit structural operator
and uses `linear_dynamics.make_system` to construct the corresponding source
network. The source tangent protections remain in force. Existing dense/sparse
assembly, beam elimination and input/output recovery operate on those same
equations.

Refinement retains the exact loaded `A` and `M` objects and preserves all old
samples. A live frequency handle records both interpolation and structural
operator. Extension/discard requests must match that identity, including when
the caller attempts to return to the default policy. Repeated runs can reuse
the matrices only when the complete existing physical identity agrees.

The browser exposes these policies in frequency settings, keeps fixed-frame
and no-flow input restrictions visible, and carries the selected equations
through requests, refinement, JSON exports and saved solutions. Still-air
density uses the existing shared medium field. The workbench continues to
compute a fresh still-air base; native matching-density saved-base input
remains subject to the existing physical identity validation.

## Independent checks

[`tests/test_source_frequency.py`](../../tests/test_source_frequency.py) checks:

* A two-mass axial system with masses 2 and 3, stiffness 100, driven by a
  prescribed origin acceleration: `q/a = -3/(100 + 3 s^2)`.
* The same system with a free or mixed translational target, where net load
  includes inertia: `q/Ftarget = 0.6/(100 + 1.2 s^2)`.
* Both 4- and 14-interval systems, exercising dense and sparse full pencils,
  physical tip displacement/velocity and the complete matrix residual.
* A uniform shear beam released in its first discrete shape. Endpoint-average
  dispersion gives `omega = 2 sqrt(GKn/mu)/h * tan(pi/(4 N))`; apparent normal
  mass adds `pi rho c^2/4` to `mu`. Both displacement and velocity transforms
  are checked for fixed vacuum, moving-policy fixed vacuum, and still air.
* Exact matrix and sample retention, repeated-run reuse, policy mismatch
  rejection, and rejection of unsupported physics before model parsing.

The new 16 checks and the selected existing native frequency/initial-response/
policy regressions pass **209/209**. The complete JavaScript test set passes
**196/196**. These counts are implementation regressions, not ISAE reference
passes. The browser evidence is recorded separately in
[`source-frequency-20261030`](../../artifacts/isae/source-frequency-20261030/).
The built offline browser checks three policies, five frequencies per policy
and exact retention of the original three samples. The 14-interval moving
case uses a 282-state sparse pencil and six frame input channels; its axial
response is checked analytically. The two fixed shear cases use 90-state
dense pencils and check the dry/wet initial spectra analytically. All three
saved solutions verify and reopen in the built workbench without recomputing,
with live refinement disabled for imported results. Mobile layout remains
within the viewport. The [ready project](../../examples/source-frequency-check-project.json)
contains those computed solutions and their editable cases.
The existing aerodynamic frequency-refinement workflow also passes after
correcting its mobile test navigation: exports are in Output, while Solve
and operating inputs are in Settings. The old test's hidden-export wait was
interrupted; this required no application change.

The full project remains incomplete. This work does not resolve SA-1–SA-5,
the Daedalus operating-point ambiguity, or the unimplemented circulating
source dynamic equations.
