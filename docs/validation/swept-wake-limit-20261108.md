# Swept lifting-line wake: fixed-point limit and attached-leg control

2026-11-08 UTC. A prescribed-circulation control confirms logarithmic wake
velocity growth at a **fixed point on a straight swept bound line**. The
analytic prediction matches the finest-grid increment within 0.024% on cosine
spacing and 0.011% on uniform spacing. Neither wing curvature nor a nonlinear
circulation solve is needed for this effect.

Chordwise attached legs before the wind-aligned free wake remove this
logarithmic term on the straight control. Their field approaches an independent
finite symmetric-principal-value reference, with maximum error 2.524e-6 m/s
at 511 intervals. This is a vortex-field diagnostic, not a complete alternative
lifting-line solver or a repair validated against SA-11. Production equations
and the registered SA-11 result, **163/4,592 at 5%**, remain unchanged.

![Fixed swept-wake control and independent continuous references](../../artifacts/isae/swept-wake-limit-20261108-review/swept-wake-limit.png)

## Literature connection

The [DLR LIFTING_LINE 3.2 manual](https://unicado.pages.rwth-aachen.de/unicado.gitlab.io/documentation/analysis/aerodynamic_analysis/references/LIFTING_LINE_V3.2_UserDoc.pdf),
printed p. 97, explicitly identifies the singular boundary velocity of a
continuous wake sheet attached to a swept bound vortex. Its force formulation
separates lift/sideforce and evaluates induced drag in the Trefftz plane. That
formulation is not automatically interchangeable with ASWING's section forces.

[Gaunaa, Li and Pirrung (2026)](https://backend.orbit.dtu.dk/ws/portalfiles/portal/446323265/Gaunaa_2026_J._Phys._Conf._Ser._3224_042030.pdf),
§3, printed pp. 5–6, place finite chordwise attached vortex legs between the
quarter-chord line and trailing edge, followed by flow-aligned free wake. They
explicitly identify the attachment direction as a modeling choice. Their full
method also includes forces on these attached legs and consistent coupling
between the three-dimensional field and two-dimensional section model. Only
the field geometry is tested here; those force and circulation equations have
not been implemented by this diagnostic.

See the [expanded literature review](winglet-lifting-line-literature-20261107.md)
and [further sources](winglet-lifting-line-literature-addendum-20261107.md) for
sharp-junction, curved-bound-line and distributed-vorticity treatments. These
are distinct mechanisms and none identifies the missing native ASWING handling.

## Prescribed field and independent reference

Use a straight line of half-arclength 1 m, with source coordinate
`-1 <= s <= 1` in metres:

```text
r(s) = s (sin Lambda, cos Lambda, 0)
Gamma(s) = (1 - s^2) (1 + a s)       [declared scale: 1 m^2/s]
Gamma'(s) = a - 2s - 3a s^2
wake direction = (1, 0, 0)
```

Sweep is -30, 0 or +30 degrees; asymmetry `a` is 0 or 0.2. Both cosine and
uniform node spacing use 15, 31, 63, 127, 255 and 511 intervals. Circulation is
sampled at each interval's Glauert-angle midpoint for both policies. Interior
wake strengths are the adjacent interval circulation differences; endpoint
strengths close the discrete vortex system. The continuous distribution has
zero circulation at both ends, so its reference has no endpoint jump rays.

The origin stays inside the central interval on every grid, away from all
discrete wake origins. Other receivers remain at `(0,0,z)`, with
`z = +/-0.001, +/-0.01, +/-0.1 m`. There is no core, PG transformation, stall
model or circulation solve. Collinear bound segments contribute zero at the
origin, with only the receiver's own interval omitted.

At the origin the independent unit-strength ray kernel is

```text
Kz(s) = -(1 - sign(s) sin Lambda) / (4 pi s cos Lambda).
```

Integrating `-Gamma'(s) Kz(s)` with symmetric exclusion `|s| < delta` gives

```text
Wz(delta) = [-4(1-delta) + 3 a sin Lambda (1-delta^2)
             - 2 a sin Lambda log(1/delta)] / (4 pi cos Lambda).
```

Thus the logarithmic coefficient is `-Gamma'(0) tan Lambda / (2 pi)`.
The excluded interval establishes the limit; it is not an adopted core or
subtraction. Independent quadrature at four exclusion sizes agrees within
1.111e-16 m/s. The discrete production kernel agrees with a separately
evaluated scalar expression within 4.997e-16 m/s.

Subtracting the `a=0` field from the `a=0.2` field isolates the asymmetric
contribution. At +30 degrees its predicted 255-to-511 increment is
-0.012774401601 m/s. The measured increments are -0.012777433721 m/s on cosine
spacing and -0.012775799012 m/s on uniform spacing. Reversed sweep reverses the
coefficient. With zero sweep or zero local circulation gradient, this
logarithmic term vanishes.

The raw +30-degree, `a=0.2` field illustrates the continuing growth:

| Intervals | Direct wake, cosine (m/s) | Direct wake, uniform (m/s) |
|---:|---:|---:|
| 15 | -0.402241110 | -0.414794431 |
| 31 | -0.417500814 | -0.426880121 |
| 63 | -0.431009591 | -0.439591535 |
| 127 | -0.444015209 | -0.452389200 |
| 255 | -0.456857482 | -0.465176436 |
| 511 | -0.469640153 | -0.477944471 |

Off the wake plane, independent continuous integration is finite. At 511
intervals the selected cosine-grid errors are 1.588e-6, 1.303e-6 and
0.02739 m/s at distances 0.1, 0.01 and 0.001 m respectively. The closest
probe is still poorly resolved; do not confuse this discretization error with
the proven on-line divergence or claim convergence at all distances.

## Chordwise attached-leg control

Keep the same bound line and prescribed circulation. Set chord to 1 m and
`c_hat = (cos Lambda, -sin Lambda, 0)`. Each trailing path runs from `r(s)`
to `r(s) + 0.75 c_hat`, then continues along the wind to infinity. This is
the quarter-chord-to-trailing-edge length for the declared chord.

The finite leg is independently checked as the difference of two collinear
semi-infinite rays. The full field can be written as infinite chordwise rays
plus the difference between wind-aligned and chordwise rays starting at the
shifted endpoints. The first part has symmetric principal value `-z_hat/pi`;
the shifted-ray difference is nonsingular at the origin and is independently
integrated. A finite principal value does not make the underlying filament
kernel pointwise nonsingular.

For +30 degrees and `a=0.2`, the continuous result is -0.323782667520 m/s.
Across all six sweep/asymmetry cases and both spacings, the largest
511-interval discrepancy is 2.524e-6 m/s. At zero sweep, attached-plus-free
legs reproduce the original wake exactly within the declared roundoff check.
No coefficient or core is fitted to any result.

## Consequence for SA-11

The [actual-winglet replay](isae-sa11-section-velocity-20261108.md) found that
correcting bound velocity alone does not resolve the failing fields. The
[fixed-probe study](isae-sa11-fixed-wake-probes-20261108.md) also found local
wake sensitivity and changing lower-winglet circulation. This new control
isolates a mathematical wake mechanism independently of either complication.

The next useful investigation is a consistent near-wake, section and force
formulation on simple geometries, followed by the actual offset/forked roots.
In particular, the literature's quarter-chord tangent and ASWING's section
span need not coincide on tapered geometry. Redirecting legs alone does not
establish valid circulation, attached-leg loads or junction conservation.
The original ASWING comparisons remain the acceptance target.

## Reproduction and verification

- [Direct-wake driver](../../scripts/verify-swept-wake-limit.py): one foreground
  job per spacing, 36 prescribed fields each.
- [Attached-leg driver](../../scripts/verify-swept-attached-wake.py): reuses
  those 72 distributions without solving circulation.
- [Independent comparison and plot driver](../../scripts/analyze-swept-wake-limit.py).
- [Analysis and source manifests](../../artifacts/isae/swept-wake-limit-20261108-review/analysis.json).
- [Standalone SVG plot](../../artifacts/isae/swept-wake-limit-20261108-review/swept-wake-limit.svg).

The three numerical stages total 2.683 seconds, excluding interpreter startup
and analysis/plotting. All ran serially with one BLAS thread and bounded memory
and time. Plans, exact driver copies, results and verification manifests are
retained in `artifacts/isae/swept-wake-limit-20261108-{cosine,uniform}/` and
`artifacts/isae/swept-attached-wake-20261108/`. All 143 production/status/scope
hashes remain unchanged. No new completion fraction or progress event results.

The subsequent [solved force-consistency control](attached-wake-forces-20261108.md)
adds section coupling and attached-leg forces on straight swept wings. It
reduces the finest-grid drag discrepancy from 8.278% to 0.848% relative to the
same-circulation Trefftz calculation, while exposing growing tip-force-point
velocities and a residual discrepancy that persists at smaller incidence.
This remains a diagnostic alternative, not a production or SA-11 validation.
