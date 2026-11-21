# Bode display axes and units

Magnitude plots now default to logarithmic horizontal and vertical axes. Major
gridlines are labeled at powers of ten using decimal labels such as 0.1, 1 and
10; lighter minor lines mark 2 through 9 within each decade. The same axes and
unit choices apply to comparison plots and exported comparison SVGs.

Phase retains a linear vertical axis. Linear magnitude and dB remain available.
Zero magnitudes cannot appear on a logarithmic vertical axis: they break the
curve and remain available through linear magnitude and CSV. Missing samples
also remain gaps. No positive floor is substituted for a zero response.

The default frequency display is cycles per input time unit, which is Hz when
the model time unit is seconds. Angular responses default to degrees; radians
remain selectable. These defaults allow the Daedalus yaw plot to use the Hz
and degrees/second convention of Drela's drawing. The frequency solver inputs
remain explicitly labeled angular frequencies in rad/input T.

Display conversion applies `f = omega / (2*pi)` once and converts angular
magnitudes from radians to degrees once. Phase is unchanged by that positive
scale. The dB display uses the selected output unit as its reference. Saved
responses, geometry, sample details and the explicitly labeled native-unit
CSV are unchanged. Existing external overlays receive the same display
conversion after their physical source-unit mapping.

These are presentation changes. They do not resolve the physical discrepancy
documented in the [Daedalus speed comparison](daedalus-rudder-speed.md), whose
reported curves already use Hz and degrees/second. Reference agreement and
cruise-speed mesh convergence remain open.

Validation passes 39 focused JavaScript tests and five distinct browser tests
across two runs. Checks cover decade/minor positions, extreme numeric ranges,
one frequency/angular conversion, phase and dB, zero/missing gaps, immutable
CSV/results, SVG export and mobile layout. The browser fixtures use saved
responses and explicitly synthetic display coordinates; no new aircraft solve
is performed. An initial startup check exceeded a custom 20-second readiness
timeout while loading numerical libraries; the retained retry passes with the
repository's normal 60-second expectation. [Evidence](bode-log-axes.json)
preserves the original failure, exact checked source and the final outcomes.
