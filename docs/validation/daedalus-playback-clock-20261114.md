# Harmonic playback clock and the yaw-rate comparison

Observed and checked 2026-11-14 UTC. This is a display correction; the saved
frequency responses and the production solver equations are unchanged.

The previous animation advanced phase at 90 degrees per wall-clock second:
**every selected frequency played in four seconds per cycle**. Therefore its
visible turning speed followed angular-displacement amplitude. It could not
be compared directly with the physical angular-rate magnitude in the Bode
plot. Earth view retained the aircraft rotation but did not correct this
playback clock. The user's Earth-view observation was a valid reason to audit
the display, rather than assuming the viewing frame explained it.

For a harmonic angle with amplitude A, physical angular-rate amplitude is
`omega * A`. Under the former clock, visible angular-rate amplitude was
`(2*pi/4) * A`, regardless of the selected physical frequency. This exaggerates
the apparent reduction in turning speed when comparing a higher frequency
with a lower frequency. It does not establish that every perceived difference
in the user's currently loaded case has been explained.

## Display changes

- **Model time · 1 T/s** is the default playback clock. For Daedalus, whose
  input time unit is one second, 1 Hz now plays one cycle per second and
  0.2 Hz plays one cycle in five seconds.
- **Phase inspection · 4 s/cycle** retains the old clock as an explicit option,
  with a warning that visible turning speed is not physical angular rate.
- The frequency/shape selector shows both cycles and radians per input time,
  labeling them Hz and rad/s when the model declares T = 1 s. The selected
  frequency-unit preference controls their order.
- The phase slider accepts fractional degrees, avoiding integer quantization
  of automatic playback. Input amplitude still scales geometry; Bode gains
  remain per unit input.

Changing these controls reads the saved response and does not request a solve.
The display uses the same selected frequency and forcing input as the plot.
The existing development server serves the updated modules. Automatic reload
remains disabled: refresh after any ongoing calculation, then select Earth
view, Model time and the same input amplitude across frequencies.

## Verification and remaining discrepancy

Five repository test bodies pass **97 assertions** in isolated V8 using the
actual 35 JavaScript dependency modules. The checks cover the differentiated
harmonic angle at 0.2, 1 and 10 Hz, both playback clocks, frequency labels,
matching plot/geometry input and sample selection, immutable saved responses,
and preservation of the result when changing display controls. DOM events and
the animation clock are simulated. No Node, browser, build or WASM job ran;
an actual browser rendering check remains outstanding.

The [physical yaw-output audit](daedalus-yaw-output-20261114.md) separately
checks the current Daedalus response. Its refined yaw-rate minimum is
**0.0733136 deg/s/F3 at 1.09942 Hz**. A dip exists, but it remains substantially
shallower than the archived drawing. At the drawing's minimum frequency,
1.1573777 Hz, OpenSwing gives **0.0738485** versus **0.0339862 deg/s/F3**.
Fixing the playback clock does not remove that numerical discrepancy or
identify Drela's unavailable operating point. No physical parameter was fitted.

[Verification receipt](../../artifacts/daedalus-playback-clock-20261114/verification.json),
[playback implementation](../../web/frequency-playback.js),
[playback tests](../../tests/frequency-playback.test.mjs),
[selection tests](../../tests/frequency-selection.test.mjs).

No ISAE completion fraction, comparison scope or progress event changed.
