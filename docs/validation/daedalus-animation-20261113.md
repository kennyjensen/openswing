# Daedalus: quantitative comparison with the rudder animations

Observed 13 November 2026 UTC. **The Bode curves remain unmatched.** The new
image comparison supports the modeled tailboom bending at 1 Hz, but does not
validate the aircraft yaw response or recover the original operating point.
No aircraft properties, production equations, defaults or ISAE counts changed.

The subsequent [wing-load investigation](daedalus-load-sensitivity-20261113.md)
found that extrapolating this small central camera calibration to the distant
wing tip amplifies its uncertainty too much for a wing-compliance conclusion.
The [comparison with Drela's steady-wing paper](daedalus-wing-paper-20261113.md)
provides a more useful independent wing-shape reference. Neither follow-up
turns the local boom comparison into validation of the complete Bode response.

![Native images, projected geometry and motion comparison](../../artifacts/daedalus-animation-calibration-20261113/report-final/animation-comparison.png)

[SVG](../../artifacts/daedalus-animation-calibration-20261113/report-final/animation-comparison.svg),
[combined data](../../artifacts/daedalus-animation-calibration-20261113/report-final/result.json),
[bounded runner](../../scripts/check_daedalus_animation.py).

## What the images add

The comparison uses 19 frames from the first cycle of each official movie.
Time follows the frame annotations: 0–5 seconds at 0.2 Hz and 0–1 second at
1 Hz, including the repeated endpoint. GIF playback delay is not physical time.
The displayed native forcing amplitude is F3=40.

The blue fairing outline supplies an independent camera reference. Its current
computed elastic motion at that display amplitude is below **0.003 ft** and
**0.062°**. The magenta propeller disk supplies a second reference, with its
literal **5.5 ft** radius and jig location. Camera parameters are fitted only
to these two objects, never to the Bode curves, boom motion or fin outline.

An orthographic camera is insufficient for the best fit. The retained
Drela/Youngren plotting library implements perspective projection in `VIEW`
and `VIEWR`, consistent with the manual's ingress/outgress controls. A separate
fit including perspective reduces frame-zero joint outline RMS errors from
**0.520 to 0.343 px** at 0.2 Hz and **0.522 to 0.339 px** at 1 Hz. This is a
camera calibration, not evidence that JVL and ASWING share all rendering code.

Across the 1 Hz cycle, joint outline RMS errors are **0.326–0.491 px**;
the largest directional outline error is **2.15 px**. The 0.2 Hz movie is less
clean: RMS **0.299–0.800 px**, maximum **3.52 px**, with propeller occlusion
especially affecting frames 10–20. Per-frame fits retain those errors.
Small fore-boom motion, rasterization and unknown native chord-display options
remain calibration limitations. The camera estimates are not accurate enough
to recover a reliable native yaw-rate curve from the fairing alone.

## Boom bending, separated from overall motion

The cyan beam's aft displacement is measured relative to the tangent of its
forward portion. A rigid straight line remains straight under perspective,
so this removes the main contribution of whole-aircraft rotation. The same
fore/aft image windows are used for the projected OpenSwing beam. Raw pixels,
polynomial diagnostics, tangent windows and complex model states are retained.

Fresh full harmonic vectors at **0.2 and 1 Hz** come from the accepted current
endpoint/SEGSPL, 6.7 m/s, C16 matrices. All coordinates remain in the solve.
No amplitude multiplier or physical parameter is fitted. A disclosed movie
phase offset is allowed because the native viewer permits changing its phase.

| Frequency | GIF bending amplitude | Projected model amplitude | Aligned curve RMS difference | Phase alignment |
|---:|---:|---:|---:|---:|
| 0.2 Hz | 1.436 px | 1.714 px | 0.331 px | 6° |
| 1 Hz | 2.248 px | 2.271 px | 0.206 px | 0° |

The native traces' largest residuals about a sinusoid are **0.487 /0.468 px**.
The plot's ±0.5 px shading is a descriptive reference band, **not a statistical
confidence interval or acceptance tolerance**. With a constant mean camera,
the 1 Hz model amplitude is 2.319 px; using the fitted per-frame camera gives
2.271 px. The apparent 1% amplitude difference must not be reported as 1%
physical accuracy. Within these image limitations, the modeled 1 Hz boom
curvature and phase are consistent with the movie.

The fin remains a separate, less settled comparison. At 1 Hz its measured
vertical image-motion amplitude is **3.647 px**, versus **2.809 px** projected
from OpenSwing. Its mean projected center is about **1.81 px right and
1.93 px down** from the measured center. These differences are sensitive to
camera calibration, loaded shape and rendering conventions. Fin motion is
neither declared passed nor used to tune the mechanics.

The subsequent [finite camera-profile study](daedalus-camera-uncertainty-20261113.md)
quantifies this limitation. At five 1 Hz phases, camera-pose changes with scale
and perspective fixed absorb the two-coordinate center discrepancy with
subpixel changes to the calibration and centered fin outlines. These
deliberately constrained fits are ambiguity diagnostics, not corrected native
motion measurements or replacement accepted cameras.

## Mean shape does not identify the speed

The mean aft boom departure is **1.049 /1.259 px** in the two movies. The
current endpoint 6.7 m/s equilibrium projects to **1.645 /1.964 px**. A
separate [saved-equilibrium comparison](../../artifacts/daedalus-animation-calibration-20261113/mean-shape-speeds/result.json)
projects the previously completed speed cases through the same cameras:

| Speed, earlier midpoint/natural policy | Mean departure in 0.2 Hz view | Mean departure in 1 Hz view |
|---:|---:|---:|
| 6.0 m/s | 2.451 px | 2.927 px |
| 6.7 m/s | 1.648 px | 1.968 px |
| 7.5 m/s | 1.365 px | 1.630 px |
| 8.25 m/s | 1.262 px | 1.506 px |
| 9.144 m/s | 1.278 px | 1.525 px |

Higher speeds bring this particular static image metric closer, but worsen
low-frequency Bode agreement. For example, the completed 8.25 m/s case has
**+124% yaw error at 0.1 Hz**. The earlier midpoint policy is disclosed rather
than relabeled as the endpoint policy. No new trim or speed response was run
for this image comparison, and no speed is inferred from it.

## The PDF and GIFs have different publication histories

Drela's [site revision history](https://web.mit.edu/drela/Public/web/aswing/)
states that the moving GIFs were replaced on **12 June 2009**. Fresh HTTP
headers independently give that date for both movies. The Bode PDF has
Last-Modified **2 June 2008**, agreeing with its embedded creation date.
The [receipt](../../reference/daedalus-animation-provenance-20261113/receipt.json)
preserves the headers and a checksummed copy of the page.

The [release notes](../../reference/version_notes.txt) associate the propeller
circle display with 5.82, 2 September 2008, and the plume correction with 5.83,
6 September 2008. Both fall between the PDF and GIF publication dates. This
is a **version/setup qualification**, not proof that their equations or
operating conditions differ. Both references remain targets; their common
label “operating point 1” does not authenticate identical saved settings.

The newly retrieved [Bode/ROM note](../../reference/daedalus-animation-provenance-20261113/rom_bode_test.pdf),
*Analysis of Exact and ROM Bode Responses for Alternative State Vector
Definitions*, is dated 23 August 2008 on its title page. Its PDF metadata
records later production in 2012. Equations 1–2 on p. 1 specify the direct
descriptor solve and output recovery used by OpenSwing. Its counterexample
on pp. 5–6 concerns acceleration outputs from an eigenmode ROM; it supplies
neither a Daedalus operating point nor a demonstrated error in a direct yaw
response. The current comparison uses the full descriptor, not that ROM
approximation. [Supplementary source catalog](daedalus-animation-sources-20261113.json).

## Numerical evidence and next investigation

Both full-state harmonic solves pass the existing gates: maximum scaled
residual **5.89e−18**, minimum estimated reciprocal condition **1.776e−8**.
These are numerical checks, not native comparison passes. The completed
four-output comparison remains **0.074218 versus 0.033986 deg/s/F3** at the
reference yaw minimum, a **+118%** error.

The useful next physics question is how wing/fin aerodynamic loads and frame
motion cancel near 1.1 Hz, now constrained by the observed local boom motion.
The static tail-shape difference and the reference version boundary need to
remain visible. Neither observation warrants changing EI, mass, lag or
damping simply to deepen the notch.

All jobs used one BLAS thread and the existing 512 MiB address-space,
15 CPU-second and 25 wall-second limits. Every child was reaped. The first
largest-component fairing filter dropped legitimate disconnected lines; one
job failed, and its outputs remain retained. Earlier raw fin masks included
palette artifacts outside the fin; those results are retained separately from
the connected-fin extraction. Saturated-only magenta extraction missed the
antialiased disk and produced unsuccessful camera fits; these are not accepted
calibrations. Browser/build tests remain held. No tracked ISAE fraction or
scope changed, so no ISAE progress event was added.

Across the **20 capped study jobs**, maximum use was **3.575 CPU seconds,
9.704 wall seconds and 192.5 MiB RSS**. One process exited nonzero as disclosed
above; unsuccessful optimizer results in earlier image trials remain explicit
even where the enclosing process exited normally. The runner parses, all
retained script snapshots match their job hashes, current production-source
pins remain unchanged, and the source supplement and local report links were
checked. The final figure was visually inspected.
