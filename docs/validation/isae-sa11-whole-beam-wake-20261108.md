# SA-11: separate induced-drag and efficiency checks on the close-force fields

2026-11-08 UTC. All 21 saved whole-beam states over 0–5° also give formal
Trefftz induced drag and span efficiency within the current 5% allowance:
**CDi error is +1.390% to +1.537%**, and **efficiency error is −2.984% to
−2.930%**. The close total-drag result therefore does not hide an out-of-band
discrepancy in either of these separately reported outputs.

**All full production states remain rejected at two winglet roots.** No
undefined section moment is evaluated, and none of these diagnostic sums is
an accepted load or primary pass. SA-11 remains **163/9,184 at 5%**. Original
inputs, targets, comparison scope, production equations and guards are unchanged.

## Same fields, separate wake quantities

The [authoritative index](aswing-authoritative-references.md) and eight-source
catalog were checked. Drela's steady description **§8.1, Eqs. 207–211, p. 49**,
defines Trefftz lift, side force, induced drag and span efficiency. The latter
uses `CLi² + CYi²`, not total near-field lift. The existing frozen-influence
implementation uses jig geometry and body-x wake direction; **§4.6, p. 36**
and the User Guide's K/F discussion describe the frozen approximation.
This study retains that production convention rather than asserting an
additional recovery of native setup.

The inputs are the [completed 0–5° receiver comparison](isae-sa11-whole-beam-polar-20261108.md):
report-derived −4° upper-winglet twist, disclosed bundled Joint correction,
original section data, 240 m/s, density 1.2256, PG Mach `240/340.21`, frozen
influences and 64 unchanged native endpoints. The two receiver rules and two
circulation fields are crossed at every angle, giving 84 wake replays and
**zero new physical solves**. These remain an explicit setup alternative.

The saved quarter-chord endpoints can be used directly: their offsets from
the beam endpoints are parallel to this frozen wind, so the transverse trace
and force measure are identical. The whole-beam wake samples use the saved
beam-axis `rm`; native-receiver samples use the saved native `RV`. The existing
theta-midpoint quadrature is retained. It is not an exact continuous wake
integral, nor is it independent of the receiver positions.

| Alpha | Archived CDi | Whole-beam formal CDi | CDi error | Archived efficiency | Whole-beam formal efficiency | Efficiency error |
|---:|---:|---:|---:|---:|---:|---:|
| 0° | 0.00246978 | 0.00250410 | +1.390% | 1.20140 | 1.16619 | −2.930% |
| 1° | 0.00445428 | 0.00451877 | +1.448% | 1.20987 | 1.17417 | −2.951% |
| 3° | 0.01017120 | 0.01032448 | +1.507% | 1.21605 | 1.17990 | −2.972% |
| 5° | 0.01819430 | 0.01847394 | +1.537% | 1.21831 | 1.18195 | −2.984% |

Every intermediate row is retained in the analysis. The native-receiver
diagnostic was closer for these two quantities: CDi error −0.379% to −0.287%
and efficiency error +0.876% to +0.999%. Whole-beam sampling improves total
drag substantially while modestly worsening these two wake outputs. Results
from the two settings are not mixed to construct a better score.

## Near-field drag is not the reported Trefftz CDi

For the whole-beam fields, near-field vortex drag is **26.84–31.72% lower**
than Trefftz drag. The coefficient difference ranges from −0.00495763 to
−0.00079424. At 0°, for example,

```text
formal total CD        = 0.00894208
formal profile CD      = 0.00723221
formal near-vortex CD  = 0.00170987
formal Trefftz CDi     = 0.00250410
```

The accounting identity is

```text
CD_total = CD_profile + CDi_Trefftz + (CD_vortex_near - CDi_Trefftz).
```

It closes within **1.39e−17** across the 21 states. Consequently, subtracting
archived `CDi` from archived total `CD` does not independently identify native
profile drag. No native profile-drag column is supplied here. This verifies
the distinct output definitions and accounting; it does not establish
near-/far-field quadrature convergence or resolve their physical difference.

## The root failure retains the offset-wake mechanism

The maximum is always at the positive-y upper-winglet root, 0.506492 mm from
the common axis of the two root wake rays. Their origins are separated by
**53.210964 mm** in x. With unit-ray influence vectors `Km` and `Ku`, the
existing pair is exactly

```text
Gamma_m Km - Gamma_u Ku
  = Gamma_m (Km - Ku) + (Gamma_m - Gamma_u) Ku.
```

The first term is the finite-connector field remaining at fixed main-wing
circulation after removing only the root-ray imbalance. It is an algebraic
decomposition of existing vorticity, not an added connector or changed model.

| Alpha | Main/winglet circulation mismatch | Offset term speed | Imbalance term speed | Actual local Mach | Conditional Mach with only imbalance term subtracted |
|---:|---:|---:|---:|---:|---:|
| 0° | 3.290% of main Gamma | 324.487 m/s | 54.993 m/s | 1.22339 | 1.08205 |
| 5° | 3.025% of main Gamma | 838.876 m/s | 130.692 m/s | 2.84888 | 2.47193 |

All 21 conditional values remain above one. Subtracting one term alone is
**not a consistent circulation solution**: a real change would alter other
bound and wake contributions and require a fresh solve. The result rules out
that simple postprocessing cancellation as sufficient; it does not rule out
every formulation that consistently treats a junction. All other incident,
bound and wake terms are retained in the conditional scalar above.

An independent analytic PG-space semi-infinite-ray formula reproduces both
reported source vectors to recorded precision. The two-term decomposition
closes within **4.55e−13 m/s**. This confirms the previously identified offset
mechanism in the same setup whose integrated coefficients are now close.

## Verification and next action

An independent scalar two-dimensional infinite-filament sum reconstructs all
84 wake fields and coefficients. Maximum velocity difference is **4.08e−12
m/s** and coefficient difference **3.78e−15**. Endpoint comparison agrees
within 5.56e−16 m. The checker verifies **158 source pins**, prior result
checksums, raw reference tokens, all case artifacts, the exact receiver/
circulation decomposition and the retained root rejections.

Keep the single documented whole-beam rule and the separate force/wake
definitions. The four separately reported coefficient families—CL, total CD,
CDi and efficiency—are all close over this declared range, but the section
moment is still undefined at the roots. The remaining work is a consistent
explanation of local junction flow and the original producing setup. No
default change, clipped velocity, discarded root strip or accepted solution
follows from these diagnostics.

The [three-angle drag decomposition](isae-sa11-drag-closure-20261108.md)
subsequently separates projection, force measure, bound and finite-origin wake
terms. The beam/bound measure contributes only roundoff to the body-x gap.
The invalid roots account for about 42% of the gap, while main-wing interactions
dominate its receiver-sampling change. This narrows the force-sampling question
without establishing a corrected or converged force.

- [Audit driver](../../scripts/audit-sa11-whole-beam-wake.py)
- [Predeclared plan](../../artifacts/isae/sa11-whole-beam-wake-20261108/plan.json)
- [All 21 rows and 84 wake replays](../../artifacts/isae/sa11-whole-beam-wake-20261108/analysis.json)
- [Independent accounting and root-ray checker](../../scripts/check-sa11-whole-beam-wake.py)
- [Verification and all root decompositions](../../artifacts/isae/sa11-whole-beam-wake-20261108/verification.json)
