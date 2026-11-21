# Fuselage apparent inertia in still air

2026-10-31. Explicit zero-speed modes now support circular fuselage beams in
both the source and existing midpoint operators. The source operator also
supports the corresponding initial-disturbance frequency spectra. Body beams
can be combined with lifting surfaces. No small artificial flight speed,
circulation equation or wind direction is introduced.

## Coefficient convention and equations

The body force density is

```text
f = -k rho pi R² [a - (a dot s) s].
```

Here s is the physical local span axis and a is its absolute acceleration.
There is no axial added mass or local rotary inertia about a circular section's
axis. Position-dependent translation/rotation coupling remains in the total
wrench.

Steady Eq.86 and unsteady Eq.45 print **k=2**. The independent accelerating
cylinder pressure integral gives **k=1**, as in the
[MIT derivation](https://web.mit.edu/2.016/www/handouts/Added_Mass_Derivation_050916.pdf).
The existing browser choice between cylinder potential flow (default) and
the printed ASWING coefficient now also applies in still air. Both conventions
are tested explicitly. This does not establish which coefficient a historical
ASWING executable used, and no coefficient is fitted to a reference result.

UI update, 2026-11-16: the selector has been removed. The app uses **k=1**;
both coefficient conventions remain available in the native API and archived
evidence. This adopts the classical accelerating-cylinder result without
asserting that the doubled printed coefficient is present in an ASWING binary.

The source operator averages completed endpoint force densities using the
unloaded interval length, then transfers the interval force equally to both
endpoints. Its total moment uses the arithmetic interval midpoint, consistent
with the existing source box balance. Tapered properties and changing local
axes can give a nonsymmetric global mass operator; its reported rigid
acceleration response is not asserted to be a symmetric spatial mass tensor.

The midpoint operator integrates body acceleration loads with the existing
eight-point body quadrature and transfers each sampled force through its own
interpolation weights. This preserves virtual power. Its reported body spatial
mass matrix agrees with six independently applied rigid acceleration fields.
The two operators retain their respective numerical identities and equations.

## Verification and saved configuration

All **202 native tests** pass: 24 new physics/boundary tests and 178 affected
regressions. All **209 JavaScript tests** pass. Six WASM cases match native
results in **1,648 scalar comparisons**, maximum absolute difference 1.78e-15.
The final offline browser scenario passes with four saved and reopened solutions.

Twenty-four new native tests cover independent circumference-pressure
quadrature, actual nodal fluid matrices, rigid wrench reports, curved/tapered
beams, mixed surface/body loads, coefficient validation, saved-state mismatch
rejection, and initial-response spectra. A shear-flexible cylinder with a tip
mass provides independent discrete mass/stiffness and continuum frequency
references. Both coefficient choices and both operators match the discrete
oracle on 4/8/16 intervals; successive mesh refinements approach the continuum
root of `cot(lambda) = m_tip lambda / (mu L)`.

The spectral oracle releases a separately calculated discrete mode from rest.
Its displacement transform is `q0 s / (s² + omega_mode²)`, including nonzero
Laplace damping. The velocity transform includes the initial-value term.
This checks physical initial-state response rather than a forced-response proxy.

The native API accepts `quiescent_body_added_mass_factor` as 1 or 2. Ordinary
zero-flow FlightCondition requests retain `body_added_mass_factor`; conflicting
values are rejected. A body-containing saved state records the factor in both
its identity and launch settings. Existing surface-only identities retain their
previous shape. The browser forwards the visible selection for modes and source
frequency response and restores it with saved projects.

The first browser run exposed a saved-solution validator that still assumed
the cylinder coefficient. It rejected the printed-coefficient source results
despite correct live numerical output. Validation now receives the requested
coefficient and checks agreement with the configuration and fluid reports.
A separate regression test and the complete browser rerun verify the fix;
the original failure record is retained.

The [machine-readable evidence](body-still-air.json) records native regressions,
JavaScript request checks, six native/WASM API cases, and an offline browser
scenario covering both coefficients, both mode operators, reused spectral
matrices, and saved-project restoration.

## Remaining limits

The zero-flow path is stationary and fixed-frame. Nonlinear still-air time
response, moving-frame still-air analyses, engines and point-object fluid
volumes remain unsupported. Source coordinate poles and spatial branch cuts
remain as documented. Surface thickness, cross-section deformation, inter-strip
fluid interaction and wall corrections are outside these local added-mass laws.
Historical ASWING sampling and full-aircraft validation remain unverified.

The numerical defaults and ISAE results are unchanged. The complete ASWING
implementation goal remains incomplete.
