# Daedalus yaw-rate selector, plot and animation check

The user's suspected output/display mismatch remains **unreproduced for their
loaded result**. A new check of the actual JavaScript selector and SVG plotting
path finds no swapped yaw-rate component in the retained current-mesh case.
This is a check of OpenSwing's own output consistency, not evidence that its
physics or Bode curve agrees with native ASWING.

One presentation inconsistency was corrected: sample details previously stayed
in radians while the plot could display degrees. Details now show the magnitude
and complex response in the selected angular units and update immediately when
those units change. CSV remains explicitly labeled in native units. No solver,
output mapping, aircraft parameters or transfer-function values changed.

## Independent measurement from the displayed geometry

The checked input is `control.3`. Selecting **Flight frame → Yaw rate r · body z**
resolves to `output.frame.rates_body.real[2]` and `imag[2]`. The plot displays the
complex magnitude, with radians converted to degrees when selected.

The new measurement instead starts from the Earth-view points returned by the
actual `frequencyGeometry` and `modeGeometry` functions. It differentiates the
first fairing chord at two harmonic phases. This chord is attached to the
aircraft frame at the fairing bottom and points along body +x. Subtracting its
endpoints cancels translation; projecting its velocity into the loaded body
axes and dividing its y component by chord length yields body omega_z. This
calculation does not read the saved angular-rate or attitude perturbations.

| Frequency | Bode omega_z, deg/s/F3 | From animated chord, deg/s/F3 |
| --- | ---: | ---: |
| 1 Hz | 0.07488170182 | 0.07488169689 |
| 1.1573777 Hz | 0.07384851680 | 0.07384851029 |

The maximum complex difference is **1.14e-10 rad/s/F3**, consistent with the
finite time-difference width of 1e-4 s. These are body angular rates, not heading
angle amplitudes or projected heading rates. The fixture's loaded frame is
steady. The corresponding full-output and source-kinematics checks are described
in the [earlier output audit](daedalus-yaw-output-20261114.md).

## Scope and verification

The actual output selection, generated SVG point titles and CSV values are
checked against that independent chord measurement at both frequencies. Tests
also cover degrees/radians, dB, changing frequency and input, and tripling the
animation amplitude without changing the unit-input Bode magnitude. Input data
remains unchanged and no numerical-settings callback runs.

**Seven test bodies / 134 assertions pass** in isolated V8 using the 35 actual
JavaScript dependency modules, an event/selection DOM and deterministic clock.
This is not a browser-rendering test. No Node, browser, build, WASM or solver
job was started. The existing development server's updated source was checked
through read-only HTTP; a manual refresh is needed because HMR is disabled.

The compact physical fixture contains unchanged saved fairing geometry and
frame response from the two previously checked frequencies. Its placeholder
conditioning/error fields exist only to render the UI and are not numerical
validation evidence. Source fixture checksums are retained in the file.

The user's exact input/output selection, displayed value and animation amplitude
were requested. Their current computed solution has not been captured, so this
check cannot rule out a different loaded state, older page, or a browser-specific
display issue. No claim that the user's observation is resolved is made.

- [Regression](../../tests/frequency-selection.test.mjs)
- [Physical fixture and origin checksums](../../tests/data/daedalus-yaw-geometry.json)
- [Independent measured values](../../artifacts/daedalus-yaw-ui-20261114/geometry-checks.json)
- [Test results](../../artifacts/daedalus-yaw-ui-20261114/isolated-v8-results.json)
- [Verification receipt](../../artifacts/daedalus-yaw-ui-20261114/verification.json)

No ISAE completion fraction, comparison scope or progress observation changed.
