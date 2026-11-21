# Solved flight-condition metadata

After a steady trim, the input widgets adopted the solved values, but
`presentResult` attached the original request condition to the computed result.
Saved results could therefore describe the starting guesses as their condition.
Bode and modal result envelopes could have the same inconsistency when their
base equilibrium solved operating constraints.

`solvedFlightCondition` in `web/steady-flight.js` mirrors the reconstruction in
`openswing/operating_points.py::_actual_condition`: solved speed, angles,
controls, powers, motion/pose vectors and final feedback commands override the
requested values. Other options are retained. The original request is not
mutated. Steady, frequency and modal presenters use this helper; time snapshot
condition semantics remain unchanged.

Trim input adoption now maps `position_earth` to the existing `position-earth`
widget IDs and converts rates/angular accelerations from radians to degrees.
Attitude angles and control commands remain in their existing units.

Verification used isolated V8 with lightweight DOM fixtures, executing the
production modules and extracted presenter/capture functions. It did not start
Node, a browser, a build or a solver:

- Steady-flight workflow: 11 test bodies / 89 assertions, including agreement
  with an already saved Daedalus equilibrium and saved-result capture retaining
  both solved conditions and the original request.
- Trim-to-response request checks: 6 bodies / 166 assertions.
- Responsive startup and resize regression: 3 bodies / 217 assertions.
- Main-module syntax passes. Removing the steady metadata correction in an
  isolated negative check makes the saved-result comparison fail.
- Read-only HTTP checks against the existing server return 200 for the corrected
  responsive layout and the new metadata helper. The responsive module contains
  none of the removed-element references that caused the startup error.

The total is 20 bodies / 472 assertions. This is not a full browser or cold-trim
validation; the UserLAnd process hold remains in force. ISAE status and numerical
physics code are unchanged. Evidence is in
`artifacts/solved-flight-metadata-20261115/`.
