# Curved-wing force sampling: whole-wing refinement

2026-10-30. **The implemented zero-core force sampling has a persistent,
spacing-dependent near-field/Trefftz drag difference in a smooth curved-wing
diagnostic.** Local induced velocity also continues to change with log(N).
This occurs with prescribed circulation, shared adjacent wake origins and
independently verified Biot–Savart fields. It is separate from nonlinear
convergence or stall. It does not establish how native ASWING treats the
singular force integral, or identify a correction for the archived SA-4 case.

The study retains 50 configurations, 92 whole-wing receiver fields and zero
equilibrium solves. No production equations, settings or ISAE pass counts change.

## Construction and scope

The synthetic beam is an exact circular arc, parameterized by unit material
arc s in [-1,1], with curvature 0 or ±0.45. Its chord varies so the wind-directed
quarter-chord offset is constant. Circulation is prescribed as
`Gamma=(1-(s/0.7)^2)^4` inside |s|<0.7 and zero outside. It is smooth through
third derivative and vanishes near both tips, removing tip-loading ambiguity.

The production geometry and vortex kernels evaluate the original Glauert
sample and Eq.154 chord-interpolated force receiver. They retain the actual
section-span force, own-bound exclusion, all trailing legs, PG=0 and zero core.
Every mesh shares adjacent endpoints exactly. Uniform and cosine grids span
32–2048 intervals; a prospective modified-cosine follow-up spans 256–2048.

These choices isolate the discretization in the
[steady formulation, Eqs.67 and 150–160](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).
The synthetic geometry is not a parsed SA-4 input, and prescribed Gamma does
not satisfy a tested tangency/stall equilibrium. Near-field/Trefftz disagreement
alone is not an ASWING reference failure.

## Retained results

At 2048 intervals, positive curvature gives:

| Spacing | Near-field drag | Trefftz drag | Difference / Trefftz |
|---|---:|---:|---:|
| Uniform | 0.317927958 | 0.327202561 | −2.83451% |
| Cosine | 0.317387794 | 0.327172898 | −2.99081% |
| Modified cosine | 0.318881164 | 0.327258636 | −2.55989% |

These are force units, not CD errors against native ASWING. Reversing curvature
reverses the gap, with essentially the same magnitudes. The straight control
agrees to rounding. All mesh levels and both curvature signs remain in the
[machine-readable analysis](../../artifacts/isae/sa4-curved-global-refinement-20261030/analysis.json).

![Refinement and local logarithmic velocity](../../artifacts/isae/sa4-curved-global-refinement-20261030/refinement.svg)

## Mechanism and quantitative checks

The local bound and wake integrals have logarithmic terms. For constant
quarter-chord offset, their combined drag-density coefficient is

```text
C(s) = rho/(4*pi) * d[Gamma(s)^2 * (wind · tangent)]/ds.
```

Its whole-wing integral vanishes for this compact circulation. Nevertheless,
if the local interval length is `H(s)/N`, the finite spacing-dependent term
is predicted to contain

```text
D_H − D_uniform -> rho/(4*pi) * integral Gamma^2 * (wind · tangent)
                                     * d(log H)/ds ds.
```

The [derivation](../../artifacts/isae/sa4-curved-global-refinement-20261030/grading-derivation.md)
gives both spacing maps and the independent local-velocity coefficient.
The measured log(N) coefficient at three interior stations agrees within
0.311% on the finest uniform/cosine doubling. This is evidence of logarithmic
local growth, rather than convergence to a mesh-independent local velocity.

For modified cosine, the prospectively computed spacing term was
±0.000897131846. The measured change in the **near-minus-Trefftz gap** is within
0.000183% at N2048. However, the predeclared **raw near-drag** test required 1%
agreement and **fails at 6.25%** for both curvature signs. The remaining
Trefftz quadrature difference is 0.0000560751; it accounts for almost all of
that finite-mesh discrepancy. The gate is unchanged: 2/4 declared follow-up
gates pass (both refinement trends), and both accuracy gates fail. The very
close gap accounting is reported separately, not substituted for that test.

The original uniform/cosine observation motivated the derivation and is not a
prospective test. Its gap-change prediction agrees within 0.0468% at N2048.
Finite refinement and local asymptotics do not supply a general global proof.

## Receiver relocation is not a fix

A second arm moves only the receiver to the exact smooth curve, preserving
the own-bound exclusion. The initial prediction for its total force change
was wrong: it included neighboring strips but omitted the own trailing legs.
The [corrected algebra](../../artifacts/isae/sa4-curved-global-refinement-20261030/self-term-derivation.md)
keeps both contributions. On the positive-curvature uniform N2048 grid:

| Chord receiver minus smooth receiver | Measured | Candidate limiting integral |
|---|---:|---:|
| Other-strip contribution | −0.009279469 | −0.009274763 |
| Own trailing legs | +0.018453053 | +0.018453179 |
| Total | +0.009173583 | +0.009178416 |

Thus moving the receiver does not simply remove the adjacent contribution.
The original incorrect protocol and prediction columns are retained. Neither
receiver relocation nor an empirical subtraction is adopted.

## Verification and implication

Independent scalar long-double bound/ray formulas reproduce all fields to
maximum scaled error 4.11e−15. Numerical integration of the directed
Biot–Savart integral passes 192 comparisons, maximum scaled error 9.46e−16.
All 210 saved geometry/force reconstruction checks pass. These checks establish
the evaluated arithmetic, not the physical choice of singular self treatment.

The result rules out assuming that shared wake origins and a finer grid alone
will remove this particular curved-wing force discrepancy. The next useful
comparison is to apply the derived local-cutoff analysis to fixed circulation
on the actual SA-4 geometry, and to identify the documented/native treatment
of singular force evaluation. An arbitrary same-surface core or drag correction
would change the problem without resolving that question.

The complete SA-4 native diagnostic remains **562/588**. The project remains
incomplete. [Protocols, raw fields, scripts and receipts](../../artifacts/isae/sa4-curved-global-refinement-20261030/README.md).
