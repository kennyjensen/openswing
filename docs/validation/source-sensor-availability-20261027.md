# Independent measurements from partially defined sensor frames

OpenSwing now retains sensor position, GPS motion, scalar airspeed and beam-frame
structural outputs when the supplied directions cannot define a complete sensor
triad. A nonzero longitudinal V direction also retains heading and elevation,
subject to their existing vertical-attitude singularity rules. Undefined projected
measurements remain null, with an explicit reason. The original records, attachment
locations and required mesh stations are unchanged.

This follows the unsteady formulation §10: anchor quantities precede the sensor
transformation; Eqs.95–97 define the pylon position, Eq.105 defines scalar speed,
Eqs.112–113 use the longitudinal direction, and Eqs.115–116 define GPS motion.
Eq.98 still requires independent V/Aspec directions for the full triad. No
replacement transverse direction is invented. Both omitted directions retain the
existing default convention. Nonfinite values anywhere in the scaled sensor row
remain errors, and the existing near-parallel conditioning threshold is unchanged.

Inspection and sensor results show the availability warning. Custom-trim choices
and default ROM outputs exclude unavailable channels; explicitly requesting an
undefined feedback, trim or ROM measurement still fails. Tables and CSV exports
retain missing values. The modal speed derivative now uses the actual stagnation
flag, so unavailable flow angles do not incorrectly suppress a defined speed
derivative. Existing zero-flow and vertical-attitude derivative guards remain.

The unchanged original ST1 `Static_deflection/[45_0]_3a.asw` now imports, retains
its sensor at −0.22, and reaches source structural residual evaluation. The
[complete refreshed inventory](source-sensor-availability-20261027/catalog.json)
verifies all 279 original model hashes: 212 parse losslessly and 67 still reject.
This is one newly accepted model. Other original grammar failures remain explicit.
Importing a model is separate from matching its archived results.

Validation:

- 182 focused Python tests pass, including 30 new availability checks. These cover
  independent moving-pylon kinematics, extreme vector magnitudes, scaled-field
  overflow, identical structural loads for different sensor frames, derivative
  availability, feedback, trim and ROM behavior.
- 70 JavaScript tests pass, including nine new checks for messages, selectors,
  tables, CSV, default ROM outputs and older saved-result compatibility.
- Six constructed checks pass in both native Python and offline Node/Pyodide.
  All 259 compared numeric values agree exactly. Each runtime evaluates one
  finite source structural residual for the unchanged ST1 input; neither runs
  an equilibrium solve. Network access is disabled and no requests occur.
- All 123 local public/kernel modules match the native sources exactly. Four
  modules change: sensors, geometry, bridge and linear_dynamics. Hosted deployment,
  browser UI execution and distributed archives are outside this verification.

The initial test run exposed two failures caused by placing availability notices
in fatal parser diagnostics; notices now appear only in inspection/results.
A third failure was a stale command key in a new negative feedback test. The
original failures and successful rerun are retained in the
[native verification record](source-sensor-availability-20261027/native-verification.json).
The [runtime comparison](source-sensor-availability-20261027/wasm/native-wasm-comparison.json)
retains input/source hashes, exact fixtures, runtime results and terminal receipts.
This capability check adds no archived ASWING comparison pass.
