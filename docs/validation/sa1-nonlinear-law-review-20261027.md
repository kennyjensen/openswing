# SA-1 nonlinear section-law source review

**No new constitutive-law sign, normalization or angle-geometry defect was found.** The implemented smooth stall law matches the inspected primary equations. This is a bounded source and retained-field review, not validation against the original executable. Registered SA-1 acceptance remains **19/154**. No solver, production import, parameter variation or production edit was performed.

The [receipt](sa1-nonlinear-law-review-20261027.json) pins the exact reviewed source, code, model, two saved states and PDF page images. The review supplements the existing influence-operator and profile-force audits without rerunning them.

## Equation and implementation checks

The older steady 5.60 paper, p33 Eqs158–160, and steady 5.99, p40 Eqs202–204, display the same law:

```text
cl = 2 Gamma / (c Vperp)
V(rcp) dot ncp - Vperp/(4 pi h) Ks f(cl) = 0
f(cl) = width * log[(1 + exp((cl - CLmax)/width))
                    /(1 + exp((CLmin - cl)/width))]
4 pi h = a0 = dCLda
```

The retained renderings of [5.60 p33](sa1-nonlinear-law-review-20261027/steady-5.60-p33.png) and [5.99 p40](sa1-nonlinear-law-review-20261027/steady-5.99-p40.png) were visually inspected. The leakage speed is unadorned `Vperp`: no hidden `c.p.` subscript or additional cosine is present. The prose's `c Vperp` phrase is not a separate speed definition; the displayed lift-coefficient denominator is the product of chord and perpendicular speed. These pages do not recover the exact historical 5.96 executable or its settings.

| Check | Primary source | Reviewed code |
| --- | --- | --- |
| Control-point distance and lift slope | 5.99 pp32–33, Eqs155–159; text1615–1657 | `frozen_influence.py:25–29`; `aero.py:330–339` |
| Local normal speed and section cl | 5.99 p16 Eq69, p40 Eq202; text780,2048 | `aero.py:458–474` |
| Leakage sign and scaling | 5.99 p40 Eq203; text2053; 5.60 text1698–1700 | `aero.py:470–476` |
| Signed smooth logarithmic law | 5.99 p40 Eq204; text2055; 5.60 text1701–1703 | `aero.py:177–195` |
| Exact fixed-geometry leakage derivative | Differentiation of Eqs202–204 | `aero.py:487–495` |
| Force velocity and separated-flow term | 5.99 p16 Eqs67,69,70; text770–794 | `aero.py:553–563` |

The stable logarithmic evaluation is algebraically equivalent to the displayed ratio. Its derivative is the **sum** of two logistic functions, because the denominator exponent decreases as cl increases. The sign restoration after sorting the exponent arguments is correct. The branch at32 changes evaluation, not the physical law. The paper's unit asymptotic derivative also establishes the natural-log interpretation.

The leakage derivative is `Ks/a0 * [2 fprime/c + (f-cl fprime) dVperp/dGamma]`, with the appropriate diagonal and full velocity derivative. The implementation retains both terms. Dividing the residual by the prescribed freestream speed changes only residual normalization, not its zero.

## Independent nonzero-angle two-dimensional limit

Take an isolated, infinite-span, untwisted planar wing at zero PG Mach, constant circulation, no motion or gust, and exclude the bound line's own singular velocity. This is an analytic limit, not a replacement model for finite-span SA-1. Define flow angle alpha relative to the physical chord, section zero-lift offset alphaA, `delta = alpha + alphaA`, `a0 = 4 pi h`, and `cl = 2 Gamma/(c U)`.

For the documented current-wake geometry, the control point lies a distance `h c` along `e = (cos alpha, 0, sin alpha)` from the bound line. The bound line produces `-Gamma/(2 pi h c) * ell` there, where `ell = (-sin alpha, 0, cos alpha)`. Equation158 gives `ncp = (sin alphaA, 0, cos alphaA)`. Therefore Eq203 reduces exactly to

```text
a0 sin(delta) = cl cos(delta) + Ks f(cl).
```

At fixed zero-angle frozen influence geometry, the induced control-point velocity is instead in the negative physical normal direction, while the actual freeflow and ncp remain live:

```text
a0 sin(delta) = cl cos(alphaA) + Ks f(cl).
```

The current implementation retains these angle factors through vector geometry and dot products. In the negligible-leakage current-wake limit, `cl = a0 tan(delta)`; its small-angle slope is a0. The paper's approximate section slopes `a0` and `a0/(1+Ks)` are not exact finite-angle scalar constitutive laws to substitute for the vector equations. Adding a separate cosine correction, replacing sin(delta) with delta, or hard-clipping at CLmax would change the published formulation. The previously completed current/frozen comparisons are not rerun here.

## What the retained fields clarify

The literal original [SA_1.asw](../../.reference/isae-sa1/SA_1.asw), lines79–87, supplies `dCLda=6.2832`, zero twist/zero-lift offset and moment coefficient, and limits `CLmin=-1.2`, `CLmax=1.2`. The paper recommends **approximately** `Ks=40` and `width=0.05` (5.99 p41, text2091; 5.60 p33, text1724). The reviewed condition uses exactly these values. The original executable's constants are not independently established, and this gap provides no basis for tuning them.

Scalar arithmetic on the already saved n400, pointwise states gives:

| Saved state | Maximum local cl | Maximum leakage / U | Ks fprime at maximum cl | Reported stalled strips |
| --- | ---: | ---: | ---: | ---: |
| 1.9971 degrees | 0.1726931379 | 3.7962026e-10 | 4.7799137e-8 | 0/400 |
| 18.091 degrees | 1.1500713258 | 0.0998970170 | 10.76887936 | 0/400 |

This is evaluation of the published formula at retained cl and velocity values, not a solve or parameter sweep. The leakage term is effectively inactive in the attached state but substantial in the high-angle state even though every local cl remains below 1.2. The explicit smooth formula has nonzero tails inside the nominal limits; the text's descriptions of zero interior derivative and outside-limit activation are approximate. Hard-thresholding the leakage would not implement Eq204.

The output Boolean `stalled` (`aero.py:829`) reports `cl > CLmax or cl < CLmin`. Consequently, **zero flagged strips does not mean no soft stall leakage**. This is a limitation of interpreting that threshold flag, not an identified residual-law defect.

These facts distinguish the attached and high-angle regimes. They do not establish why original ASWING differs by roughly +0.058% in attached CL and -2.67% at high incidence. In particular, the tiny retained attached leakage cannot be treated as a common multiplicative cause of both discrepancies. No alternative historical constant, clipping law or angle correction was identified. Original target precision, all targets and the 19/154 result remain unchanged.
