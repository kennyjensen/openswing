# Daedalus: loads driving the tail-boom response

Fin attachment reactions dominate the current tail-boom lateral bending and
yaw rotation near the Bode dip. Removing only the boom's distributed real
inertia changes fin-root displacement by **−1.614%** and rotation by
**−1.358%** at 1.157378 Hz, with phase changes below 0.013°. The fin's
aerodynamic, apparent-mass and real-inertia loads remain in its prescribed
reaction. This does **not** rule out a coupled boom/fin/aircraft resonance.

This reconstructs the existing full-aircraft motion. It supplies no new Bode
prediction or correction: yaw remains **0.074218 versus 0.033986 deg/s/F3**
at the selected reference minimum.

![Root-motion contributions and fin-force split](../../artifacts/daedalus-boom-drivers-20261113/report-v2/boom-drivers.png)

[Vector figure](../../artifacts/daedalus-boom-drivers-20261113/report-v2/boom-drivers.svg),
[complex contributions CSV](../../artifacts/daedalus-boom-drivers-20261113/report-v2/root-contributions.csv),
[complete report](../../artifacts/daedalus-boom-drivers-20261113/report-v2/result.json).

## Boundary and calculation

The literal `dae.asw` attaches the fairing to boom station **2.5 ft**, aft of
the wing attachment at 0 ft. Cutting at 2.5 ft leaves two attachments:
stabilizer at 17.5 ft and fin at 20 ft. The fin retains its one-foot rigid
offset. The cut motion is taken from the accepted full solution, not zeroed.

The selected boom has 13 elements, 13 free nodes and **156 mechanical
unknowns**: node positions/rotations and internal resultants. It weighs
**1.945 lb** under the current source endpoint mass rule. Loaded geometry,
internal preload, section stiffness and source compatibility are retained.
Its real mass includes the source finite-interval rotary contribution.

For `exp(i*omega*t)` motion, the local real inertial load is `+omega² M q`.
The selected residual is decomposed as

```text
(J + omega² M) q
    + fin attachment load
    + stabilizer attachment load
    + boom airloads
    + frame inertia/gravity load
    + prescribed-cut-motion contribution = 0.
```

Actual nodal loads and attachment wrenches come from fourth-order directional
evaluations of the complete nonlinear aircraft residual. Frame-only real
inertia/gravity is evaluated separately. Its difference from the total
real-mass load agrees with the separately assembled local endpoint mass
action on the actual motion. Attachment moments include their changing arms.
Boom airloads include distributed body loads and any body-shoulder loads on
these nodes.

The same mechanical operator is solved with a separate right-hand side for
each category. Their sum must recover every selected coordinate, including
internal resultants, and the fin-root motion through the loaded rigid offset.
These are conditional contributions: prescribed attachment reactions already
contain the rest of the aircraft's feedback. They are not independent aircraft
responses, and scalar magnitudes must not be added as percentages.

The [authoritative index](aswing-authoritative-references.md) and source catalog
govern this calculation. Compatibility and endpoint load rules are discussed
in the [steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
Eqs. 48–56 and 80. Real/apparent inertia, circulation-rate lift and unchanged
joint laws are in the [unsteady description](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
Eqs. 34–44 and §6.4. Production section/chart functions are reused; this is an
assembly and accounting check, not an independent physics oracle.

## Loads driving the fin root

Lateral displacement contributions at 1.157378 Hz:

| Driver | Real, ft/F3 | Imaginary, ft/F3 |
| --- | ---: | ---: |
| Fin attachment | +0.01586288 | −0.01675976 |
| Stabilizer attachment | +0.00075346 | −0.00126231 |
| Boom airloads | +0.00000706 | −0.00001018 |
| Frame inertia/gravity acting on boom | −0.00003611 | −0.00006012 |
| Forward attachment motion | +0.00025262 | −0.00038180 |
| **Sum** | **+0.01683990** | **−0.01847417** |

Root yaw rotation has the same ordering: the fin-reaction contribution is
`0.114799 − 0.125590i deg/F3`, against the total
`0.120776 − 0.136068i deg/F3`. These are elastic rotation phasors relative to
the aircraft frame, not its yaw-rate Bode output. Fin reactions also dominate
at 0.2 Hz; the CSV retains both frequencies and coordinates.

Removing local distributed real boom inertia while keeping the same actual
attachment/air/frame loads and forward-attachment motion gives:

| Frequency | Lateral magnitude change | Lateral phase change | Rotation magnitude change | Rotation phase change |
| --- | ---: | ---: | ---: | ---: |
| 0.2 Hz | −0.04830% | −0.000071° | −0.04095% | −0.000191° |
| 1.157378 Hz | −1.61405% | −0.002816° | −1.35801% | −0.012638° |

This does not remove fin inertia or fluid apparent mass, retrim the aircraft,
or let prescribed loads readjust. It cannot establish a resonance frequency
or bound the full Bode sensitivity to mass.

## Fin reaction split

The fin's nodal external loads, including real inertial reactions, are summed
about the **moving boom tip**. The moment derivative retains both
`arm × delta_force` and `delta_arm × base_force`. The summed wrench matches
the attachment reaction before driving the boom calculation.

Lateral force applied by the fin to the boom at 1.157378 Hz:

| Contribution | Real, lb/F3 | Imaginary, lb/F3 |
| --- | ---: | ---: |
| Circulation lift | +0.106905 | −0.206313 |
| Circulation-rate lift | +0.181223 | +0.092304 |
| Profile force | −0.001758 | −0.000823 |
| Apparent-mass loads | +0.037087 | −0.192547 |
| Fin real inertia/gravity | +0.033314 | −0.044941 |
| **Sum** | **+0.356771** | **−0.352319** |

The intrinsic section pitch term contributes no force; its retained moment is
negligible here. Circulation, circulation-rate and apparent-mass loads have
comparable magnitudes and different phases. The fin reaction's phase cannot
be read as a direct measurement of boom compliance.

## Verification and remaining work

| Check | Largest absolute error |
| --- | ---: |
| Mechanical matrix under step halving | 3.330e−11 |
| Compatibility block versus full aircraft matrix | 3.330e−11 |
| Five finite full-residual subtraction checks | 2.082e−17 |
| Load derivatives under step halving | 9.778e−16 |
| Local/frame real-mass split | 4.474e−17 |
| Complete selected mechanical state reconstruction | 5.775e−14 |
| Fin-root position/rotation reconstruction | 2.247e−13 |
| Fin load sum versus attachment wrench | 4.061e−12 |
| Fin physical-load response sum versus prior fin contribution | 8.363e−14 |

Matrix/load derivative gates are 2e−8 in scaled units; attachment wrench closure
uses 2e−6 native force/moment units. The mechanical matrices pass a scaled
reciprocal-condition gate of 1e−12 (observed approximately 0.00114). No gate was
relaxed. Detailed per-check units, residual gates and arrays are in the driver.

All **seven serial jobs** succeeded and were reaped with one BLAS thread,
512 MiB address space, 15 CPU seconds and 25 wall seconds. Maxima were 4.062 CPU
seconds, 6.891 wall seconds and 97.305 MiB RSS. The first figure had crowded
labels; the second changes tick density and layout only. No physical calculation
was repeated for that fix. The [driver](../../scripts/check_daedalus_boom_drivers.py)
retains per-job source, input hashes, logs, arrays and terminal receipts.

The [preceding feedback diagnostic](daedalus-root-feedback-20261113.md) showed
that fin-root motion suppresses yaw; this report identifies its driving loads.
Neither establishes native ASWING agreement. No production equation/default,
ISAE fraction or browser/build verification changed. The next useful question
is how fin circulation and apparent-load phases split between frame motion and
elastic motion, retaining the already identified wing contribution and the
uncertain historical operating point.

**Follow-up:** the [independent fin apparent-load replay](daedalus-fin-phase-20261113.md)
now checks those frame/elastic acceleration terms and finds no discrepancy.
The [wing-lift product-rule split](daedalus-wing-lift-terms-20261113.md)
identifies wing-root rotation through the local relative-velocity term as a
stronger next diagnostic near the yaw dip. Neither changes the predicted Bode
curve or establishes the native operating settings.
