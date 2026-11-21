# In-app yaw-rate consistency check

Selecting a saved **Flight frame → Yaw rate** or **Operating → rates.z** result
now shows a check below its sample details when the loaded frame is stationary
and sufficient body/Earth geometry is available. The check independently
reconstructs the frame's angular rate from the geometry, compares the complex
rate with the selected Bode quantity, and displays both magnitudes per unit
input in the selected angular units. No solve is requested.

For each base point `r`, the code removes elastic body displacement from the
Earth displacement, transformed back into the loaded body axes. The remaining
field is `translation + rotation cross r`. Centering removes translation, and
a three-variable least-squares fit recovers the infinitesimal frame rotation.
Multiplying its complex components by `i*omega` gives the angular rate in a
stationary frame. This reconstruction does not read saved frame angle or rate
perturbations. Elastic rotation is removed: this is a reference-frame check,
not a local gyro average.

Initial spectra, moving base orientations, insufficient/degenerate geometry
and inconsistent body/Earth geometry are excluded. A successful comparison
establishes consistency of the saved transfer and display geometry, not
correct physics or agreement with Drela's native curve.

Nine test bodies / **156 assertions** pass in isolated V8. They cover the
actual selector, SVG values, CSV, sample/input changes, saved physical Daedalus
geometry at two frequencies, display units, amplitude, and detection of a
deliberately altered rate. Additional tests reconstruct a known rotation with
a tilted base, large translation and varying elastic displacement, and reject
inconsistent or degenerate geometry. No browser, Node, build, WASM or solver
job was run. The user's actual loaded result remains unavailable. Source
served by the existing development server was checked; HMR remains disabled.

[Implementation](../../web/frequency-motion-check.js),
[mathematical regression](../../tests/frequency-motion-check.test.mjs),
[UI regression](../../tests/frequency-selection.test.mjs),
[results](../../artifacts/daedalus-motion-consistency-20261114/isolated-v8-results.json),
[receipt](../../artifacts/daedalus-motion-consistency-20261114/verification.json).
