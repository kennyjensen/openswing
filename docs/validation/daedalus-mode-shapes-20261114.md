# Daedalus: physical character of the two cancelling modes

The two strongest oscillatory modal contributions near the yaw dip include
both wing bending and lateral tailboom bending. The **1.2525 Hz** mode has
most of its beam material-strain measure in the wing; the **1.2978 Hz** mode
has most in the aft boom. This confirms that the current model contains the
tailboom deformation mechanism. It does not resolve the reference discrepancy:
full-model yaw remains **0.074218 versus 0.033986 deg/s/F3** at 1.157378 Hz.
No physical parameter, production equation, default or ISAE fraction changed.

![Current mode shapes and beam material participation](../../artifacts/daedalus-mode-shapes-20261114/plot/mode-shapes.png)

## New primary evidence from the wing paper's bibliography

Drela's [1989 wing-load paper](daedalus-wing-paper-20261113.md) cites Sullivan
and Zerweckh's **Flight Test Results for the Daedalus and Light Eagle Human
Powered Aircraft**, NASA-CR-183305. The full 154-page report is now retained in
[reference/](../../reference/daedalus-flight-research-20261114/sullivan-zerweckh-1988-flight-tests.pdf),
with [searchable text](../../reference/daedalus-flight-research-20261114/sullivan-zerweckh-1988-flight-tests.txt)
and a [checksummed source supplement](daedalus-flight-research-sources-20261114.json).
The [NASA record](https://ntrs.nasa.gov/citations/19890001519) dates publication
7 June 1988; the printed cover says October 1988. Both dates are retained.

The dynamic results concern **Light Eagle**, not the literal public Daedalus
model. They guide mechanism checks without supplying a matched validation:

| Report location | Evidence and implication |
| --- | --- |
| Printed p. 8 / PDF p. 30 | Loaded wing curvature couples bending and torsion; tailboom flexibility affects lateral dynamics and control delay. Linearization must use the loaded aircraft. |
| Printed p. 34 / PDF p. 56, §3.2 | A simple lateral-response model estimates a 1.4 Hz tailboom mode, 20% critical damping, and separate structural/aerodynamic lag effects. These are approximate phenomenological estimates, not ASWING calibration inputs. |
| Printed p. 37 / PDF p. 59, §3.3 | The fuller aeroelastic model starts with free-free modes including apparent mass at zero flight speed. Structural frequencies overlap; the report cautions that mode selection lacks a clear spectral gap. |
| Printed p. 38 / PDF p. 60, Table 3-2 | A symmetric fore/aft wing mode at 1.6 Hz has strong tailboom participation. Antisymmetric first vertical and fore/aft wing modes are listed at 0.9 and 1.4 Hz. The table does not give the two current Daedalus full-aircraft poles below. |

Table 2-3 (printed p. 9 / PDF p. 31) also has an apparent unit-conversion or
decimal discrepancy. Its apparent-mass pitch inertia is printed as both
**138.6 slug ft²** and **1879 kg m²**; the former converts to **187.916 kg m²**.
All six paired inertia entries show approximately the same factor of ten.
The later nominal pitch inertia of **186 kg m²** is consistent with the
converted order of magnitude. The saved diagnostic preserves the printed
numbers and conversions separately. Neither is substituted into `dae.asw`.
Table 3-2's aerodynamic-lag frequency label likewise must not be conflated
with §3.2's 0.14-second time constant.

## Current model diagnostic

This uses the accepted source-equation/SEGSPL model at **6.7 m/s**, Mach 0.1,
with live influences, aerodynamic lag and propeller plume: 108 nodes,
103 beam intervals, 82 circulation states and 2,044 total coordinates. It
does not change the browser's selected operator or defaults. The eigenvectors
come from the accepted [current modal comparison](daedalus-source-modes-20261114.md),
not a fresh aircraft solve. Selection takes the two conjugate pairs with the
largest yaw contributions at the reference dip. It identifies the existing
response mechanism; it neither fits a mode count nor excludes other poles.

| Quantity | Wing-dominated pair | Aft-boom-dominated pair |
| --- | ---: | ---: |
| Positive-imaginary pole, s⁻¹ | −4.956795 + 7.869451i | −6.939570 + 8.154006i |
| Damped oscillation frequency, Hz | 1.252462 | 1.297750 |
| Wing share of beam material-strain measure | 76.57% | 11.42% |
| Forward-boom share | 8.28% | 13.92% |
| Aft-boom share | 11.79% | 63.38% |
| Fin share | 1.33% | 9.23% |
| Yaw contribution at 1.157378 Hz, deg/s/F3 | −0.084003 − 0.043058i | +0.108477 + 0.093529i |

The complex contributions partly cancel. Other modes, including a real pole
and faster oscillatory pairs, are significant, so their sum is not the complete
yaw response. These are appreciably damped aeroelastic poles, not isolated
undamped structural frequencies. Similar frequency ranges across two aircraft
do not establish agreement in mode shape, damping, control coupling or Bode
response.

For the plot, each eigenvector is independently scaled to **1 mm maximum
body-relative nodal displacement envelope**. This is arbitrary mode display
normalization, not physical displacement per rudder input. Subtracting each
component root's translation and rigid rotation reveals actual beam deformation.
The aft-boom lateral amplitudes are then **0.2052 / 0.6492 mm**; wing vertical
amplitudes are **1.3586 / 0.6354 mm**. The wing fore/aft components shown in
the middle panel are smaller, **0.1533 / 0.0322 mm**. A root-relative amplitude
can exceed the normalization based on body-relative motion.

The participation measure is the positive quadratic in incremental local
beam loads and strains, summed with each undeformed interval length:
`Q = sum(ds * Re(conj(delta_load) · delta_strain) / 4)`.
Local load increments include rotation of the loaded section frame. This
**beam-only material measure is not total modal energy**: it excludes brace
energy, prestress/geometric terms, fluid terms and kinetic energy. It is useful
for locating beam deformation; the percentages must not be read as complete
aircraft energy fractions.

## Verification and consequence

The four eliminated cyclic coordinates were recovered before checking all
2,044 homogeneous equations. Maximum relative eigen-equation residual is
**1.175e−12**. The independently derived beam compatibility tangent closes
within **1.080e−14** at the displayed scale. All group fractions sum to one,
and both mode normalizations are checked. Full arrays and figures are retained:

- [Numerical results](../../artifacts/daedalus-mode-shapes-20261114/analyze/result.json)
- [Mode arrays](../../artifacts/daedalus-mode-shapes-20261114/analyze/arrays.npz)
- [SVG figure](../../artifacts/daedalus-mode-shapes-20261114/plot/mode-shapes.svg)
- [Bounded diagnostic driver](../../scripts/check_daedalus_current_mode_shapes.py)

Both serial jobs completed and were reaped under one BLAS thread, 512 MiB
address space, 15 CPU seconds and 25 wall seconds per child. Neither required
a new matrix assembly or aircraft solve. The NASA PDF tables and resulting
figure were visually inspected. Browser/build jobs remain held.

The new evidence supports the user's interpretation that tailboom flexibility
matters near the dip. It narrows the open question to the coupled response's
amplitudes, phases and historical setup rather than an absent tailboom mode.
The related [Fourier/modal study](daedalus-fourier-modes-20261114.md) shows why
discarding modes to reproduce the minimum would be misleading: it worsens the
low-frequency and complete-curve comparison. No new reference pass is claimed.
