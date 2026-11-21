# Daedalus: full-state load sensitivities near the yaw dip

The current yaw mismatch is much more sensitive to **ordinary wing lift** than
to wing profile drag or stall leakage. This narrows the investigation without
changing or fitting the model. At the drawing's 1.157378 Hz dip, the unchanged
source-equation case still gives **0.074218 versus 0.033986 deg/s/F3 (+118%)**.

## Method

The [bounded driver](../../scripts/check_daedalus_load_sensitivity.py) reuses
the accepted 6.7 m/s endpoint/SEGSPL equilibrium and its complete 2,044-coordinate
descriptor. Four fresh baseline harmonic states are solved. For each, detailed
physical residuals separate every surface's circulation lift, circulation-rate
lift, profile force, intrinsic pitching moment and apparent inertia. Body loads,
point/engine loads, real mass/gravity, and the separate stall residual are also
retained. Transfers use the production conservative endpoint wrenches.

Fourth-order real/imaginary directional stencils evaluate each component's
harmonic residual at two widths, 0.001 and 0.0005. Their differences are below
2e−8 in scaled residual units; actual maxima are approximately 6e−14. Complete
complex force/moment sums close within 1.8e−9 native units. A full multi-RHS
harmonic solve then gives the response derivative for each component multiplier.

These are **fixed-equilibrium affine sensitivities**: multiplying a component
retains a constant offset so the accepted base remains unchanged. They are not
retrimmed aircraft parameter changes, independent additive Bode contributions,
or permission to rescale a physical force law.

## Yaw magnitude sensitivity

Each entry is the approximate **percent change in yaw magnitude for a +1%
component multiplier**, evaluated locally at the baseline. Signs can reverse
with frequency because complex loads reinforce or cancel differently.

| Component | 0.1 Hz | 0.2 Hz | 1 Hz | 1.157378 Hz |
| --- | ---: | ---: | ---: | ---: |
| Wing circulation lift | −0.70573 | −0.81800 | +0.68126 | +1.17670 |
| Wing circulation-rate lift | +0.00276 | +0.02877 | −0.23019 | −0.31068 |
| Wing profile force | −0.03618 | −0.04281 | +0.02712 | +0.03639 |
| Wing stall residual | −0.00241 | −0.00217 | +0.00162 | +0.00065 |
| Fin circulation lift | +0.43414 | +0.62632 | +0.21382 | +0.14501 |
| Fin circulation-rate lift | −0.00750 | −0.00292 | +0.24332 | +0.22621 |

At the reference dip, the wing lift and fin lift yaw moments are respectively
**2.5680 + 4.9631i** and **2.1372 − 4.1265i lb ft/F3**. Fin circulation-rate
lift contributes **3.6236 + 1.8450i**, and fin apparent inertia contributes
**0.7205 − 4.0190i**. Their phases matter; comparing magnitudes alone hides the
cancellation. These are selected load terms, not the complete zero-sum balance.

The baseline maximum wing CL is 1.29879 against its 1.7 upper limit. The maximum
stall leakage slope times the declared stall factor is 0.01309. These results
make stall a weak local explanation for this particular Bode discrepancy.
Large parameter changes cannot be inferred from these first derivatives.

Full states, component residuals, nodal/global load closure, complex output
derivatives and numerical checks are in:

- [0.1 Hz](../../artifacts/daedalus-load-sensitivity-20261113/low-frequency/result.json)
- [0.2 Hz](../../artifacts/daedalus-load-sensitivity-20261113/slow-animation/result.json)
- [1 Hz](../../artifacts/daedalus-load-sensitivity-20261113/one-hertz/result.json)
- [Drawing dip](../../artifacts/daedalus-load-sensitivity-20261113/reference-dip/result.json)

Each adjacent `arrays.npz` retains all complex arrays. All four jobs completed
and were reaped, with unchanged inputs, under one-thread/512 MiB/15 CPU-second/
25 wall-second limits. No production defaults or ISAE counts changed.

## Wing images and independent reference

The subsequent [wing-tip GIF overlay](../../artifacts/daedalus-animation-calibration-20261113/wing-outline/wing-comparison.png)
uses the previous independent fairing/propeller camera and the complete states
at 0.2 and 1 Hz. Its camera extrapolation is too uncertain to assess wing
compliance: at 1 Hz the projected tip departs from a harmonic trace by up to
16 pixels horizontally, while the measured trace departs by only 0.64 pixels.
The 0.2 Hz camera includes an even larger outlier. This is **not evidence of a
wing stiffness error**, and no wing fit or physical change was made.

The [comparison with Drela's wing-load paper](daedalus-wing-paper-20261113.md)
instead supplies an encouraging steady-shape check with explicit setup
differences. Its roll-pin clue was also tested conditionally and worsens the
Bode dip. Native Bode agreement remains open.
