# Daedalus: output conventions and the published lateral-rate magnitudes

An in-plane rotation of roll/yaw axes cannot explain the current discrepancy.
At 1.157378 Hz the combined rate magnitude is **0.078069 versus 0.050132
deg/s/F3**, a **55.73%** difference. Even the previously declared graphic
coordinate envelope leaves at least **46.68%**. No choice of rotation angle
can make both rates agree within 5% at this frequency.

The reference bank/roll relation is a useful clue, but the same graphic
envelope prevents using it to exclude the current 3.056° elevation. No
operating point or phase has been recovered. The original yaw prediction
remains **0.074218 versus 0.033986 deg/s/F3**; no production equation changed.

![Rate invariant and bank/roll relation](../../artifacts/daedalus-reference-kinematics-20261114/report-v2/reference-kinematics.png)

## Sources and scope

The [authoritative reference index](aswing-authoritative-references.md) and
[source catalog](aswing-authoritative-sources.json) remain governing.
Drela's [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
printed p. 6, Eqs. 9–16, defines body angular rates, Euler angles and their
rate relations. The [original Bode PDF](../../reference/drela-rudder-bode-20261113.pdf)
labels body `Omega_x`, `Omega_z`, reference sideslip and bank angle. Its SHA-256
is `b37f684a57c2e93c1ec64566480d0051c05adf7b59376e409c004cfb581e0dfe`.

The raw vertices and original graphic-envelope definition come from the
[retained four-output evidence bundle](daedalus-rudder-four-outputs-20261025-evidence.zip).
Its embedded PDF is checked byte-for-byte against the current local copy.
All three axes' log-magnitude calibrations are reconstructed from the PDF
grid rectangles and reproduce the retained magnitudes. This analysis uses
the current source-equation/SEGSPL case's 65 complex output samples; older
solver responses in that bundle are not substituted.

The [prior comparison](daedalus-rudder-four-outputs.md#a-clue-about-the-reference-operating-point)
already observed that `2*pi*f*abs(bank)/abs(roll)` is close to one. The present
work adds phase-independent bounds, a conservative treatment of the drawing
resolution and an axis-rotation invariant. It does not repeat that earlier
zero-elevation physical retrim.

## Necessary attitude bounds

At a stationary base the documented Euler identity is

`i*w*Phi_hat = -p_hat + tan(Theta0)*(sin(Phi0)*q_hat - cos(Phi0)*r_hat)`.

For zero bank it reduces to `i*w*Phi_hat = -p_hat - tan(Theta0)*r_hat`.
The triangle inequality therefore gives

`abs(w*abs(Phi_hat)-abs(p_hat))/abs(r_hat) <= abs(tan(Theta0))`

and

`abs(tan(Theta0)) <= (w*abs(Phi_hat)+abs(p_hat))/abs(r_hat)`.

The calculation uses **99 exactly shared roll/bank graphic abscissae** and
interpolates yaw along its connected log-log polyline. The central bank/roll
ratio spans **0.992584–1.013277**, reproducing the prior observation.

| Graphic coordinate half-width | Necessary absolute elevation range | Limiting upper-bound frequency |
| --- | ---: | ---: |
| 0, central polylines only | 0.23566–2.57373° | 6.798965 Hz |
| 0.75 PDF point, original envelope | 0–6.02260° | 6.798965 Hz |
| 1.5 PDF points, sensitivity only | 0–11.41158° | 6.845969 Hz |

The sharp roll minimum makes the upper bound sensitive to horizontal graphic
uncertainty. Treating central polylines as exact would incorrectly give their
small rounding differences the status of physical data, even excluding exactly
zero elevation. Under the retained envelope, **3.056365° is not excluded**.
These are necessary ranges, not estimates or confidence intervals.

For half-width `h`, each nominal vertex's true abscissa may vary by `h`, and
each curve may move horizontally and vertically by `h`. Curve magnitude
extrema are evaluated over `x +/- 2h`, including internal vertices; frequency
uses `x +/- h`. Independent extrema give conservative bounds. The envelope
describes graphic coordinates, not physical uncertainty or a solver tolerance.

The current trim has bank **0.006599°**, not exactly zero. If that exact
attitude and the central polylines were assumed, escaping the triangle bound
would require a pitch-rate magnitude of at least **127.0 deg/s/F3** near
6.799 Hz. The original graphic envelope reduces this necessary lower bound
to zero. No claim about the unknown reference pitch response follows.

## An invariant that does rule out an output-axis explanation

For any real rotation angle `chi` in the roll/yaw plane,

```text
p_new = cos(chi)*p + sin(chi)*r
r_new = -sin(chi)*p + cos(chi)*r
abs(p_new)^2 + abs(r_new)^2 = abs(p)^2 + abs(r)^2.
```

This holds for complex harmonic amplitudes with arbitrary relative phase.
Consequently, matching both magnitudes within 5% requires their Euclidean norm
also to agree within 5%. This condition cannot be evaded by selecting another
axis angle independently at each frequency. Satisfying the condition does not
prove that either rate or any common rotation matches.

| Quantity at the drawing's yaw dip | Result |
| --- | ---: |
| Current combined roll/yaw norm | 0.07806932 deg/s/F3 |
| Central drawing norm | 0.05013163 deg/s/F3 |
| Drawing norm within original graphic envelope | 0.04770686–0.05322424 deg/s/F3 |
| Difference from central norm | +55.7287% |
| Smallest difference over envelope | +46.6800% |
| Current yaw, axes rotated by +3.056365° | 0.07477104 deg/s/F3 |
| Current yaw, axes rotated by −3.056365° | 0.07347016 deg/s/F3 |

Across the 65 retained frequencies, **32 cannot meet even the necessary joint
5% norm condition**, including the graphic envelope. This is not a new
pass/fail suite; the other 33 are not validated cases. The invariant concerns
in-plane rotations. An arbitrary three-dimensional rotation can mix an unknown
reference pitch response and is outside this result's scope.

Replacing bank angle by the integral of body roll rate would give **0.00333038°**
at the dip, versus the current **0.00309191°** and reference **0.00507383°**.
That post-processing change would leave yaw unchanged and still underpredict
bank. It is a diagnostic output convention, not a justified production change.

## Execution, retained attempts and next work

- [Complete result](../../artifacts/daedalus-reference-kinematics-20261114/report-v2/result.json),
  [65-frequency CSV](../../artifacts/daedalus-reference-kinematics-20261114/report-v2/comparison.csv),
  [SVG plot](../../artifacts/daedalus-reference-kinematics-20261114/report-v2/reference-kinematics.svg).
- [Attitude bounds](../../artifacts/daedalus-reference-kinematics-20261114/bounds-v2/result.json),
  [all graphic bounds](../../artifacts/daedalus-reference-kinematics-20261114/bounds-v2/bounds.csv).
- [Bounded reference driver](../../scripts/check_daedalus_reference_kinematics.py),
  [saved-response comparison](../../scripts/report_daedalus_reference_kinematics.py).

Four bounded serial jobs are terminal and reaped: three successful and one
retained rejection. The first reference attempt used a mistyped yaw-grid
height; its calibration check rejected it. The corrected driver reads all
grid rectangles directly from the pinned PDF. No threshold changed. The
second report only renames a necessary-condition field to prevent a true value
being misread as proof that matching is possible; numerical values are unchanged.

Each job used one BLAS thread, 512 MiB address space, 15 CPU seconds and
25 wall seconds. The plot was visually inspected. No aircraft residual,
factorization or harmonic solve was run; these jobs analyze existing evidence.
Production code, model files, ISAE fractions and progress history are unchanged.
Browser/build checks remain held.

The preceding [interacting-surface study](daedalus-coupled-avl-20261114.md)
constrains direct wing–fin airflow. This check further constrains output-axis
and bank-post-processing explanations. The physical/dynamic cancellation and
unknown historical inputs remain open. A useful next target is the **full
descriptor's rudder-to-yaw transmission zero** and its associated coupled
motion: locate the cancellation directly rather than inferring it only from
individual modal residues or changing coefficients to fit the drawing.
