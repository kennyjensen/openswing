# SA-13: exact geometry expression in the discrete pressure figure

All **56 finite values** of the archived red `Discrete ASWING 5.96` pressure
curve obey an exact local geometry relation:

```text
Y_i = 100 [(R_i − R_(i−1)) / (x_i − x_(i−1))]² − 5,
```

with a zero slope assigned to the first row. The radii are half the difference
between the original upper and lower outlines, and all three curves have the
same x coordinates. No source-field integration or numerical sensor velocity
is needed to reproduce these saved values.

The **−5 offset is inferred from the data**, not a documented physical
normalization or an accepted solver parameter. The exact relation establishes
what numbers are stored; it does not establish the author's generating code
or explain the offset. No pressure law is changed to reproduce it.

| Check | Result |
|---|---:|
| Finite values satisfying the relation | 56 |
| Required values in this series | 103 |
| Unavailable values retained | 47 |
| Maximum binary64 absolute discrepancy | 1.78e-15 |
| Maximum independent Decimal discrepancy | 1.64e-14 |
| Original coordinate pairs independently verified | 515 |

Together with the [discrete lift identity](isae-sa13-discrete-loads-20261109.md),
this accounts algebraically for all **239 available values in the four red
curves**. It is not 239 native solver passes. The modified blue curves, missing
entries and original-versus-modified distinctions remain separate. The primary
SA-13 scope remains **0/612**, with 136 unavailable values. SA-12 remains open.

## Relation to the report and the pressure bound

Jan Part I **§6.2, pp.40–41**, describes recovering surface velocities and using
steady Bernoulli; Figure 24(d), **p.42**, labels a source contribution to a
pressure ratio. The cited NACA-TM-574 **printed p.11 / PDF p.13** derives static
gauge pressure from the total velocity. Under that interpretation,

```text
100 Cp = 100 [1 − |V_total|²/U∞²] ≤ 100.
```

The archived second value, **173.2016002683843**, still cannot be that full
incompressible Cp. Its geometric explanation is now explicit:

```text
backward radius slope = 1.3349217215566773
100 × slope²          = 178.2016002683843
stored ordinate       = 178.2016002683843 − 5.
```

There is also a useful theoretical lead. Jan's **Appendix A, p.61,
Eqs.33–34**, gives the local radial source velocity `v_sigma,r = sigma/(2πR)`
and source strength `sigma = 2πR R' U_parallel`. For axial flow this gives
`v_sigma,r/U∞ = R'`. Squaring that *component's* velocity therefore produces
the unshifted expression in the saved curve. This is a plausible interpretation
of its geometry dependence, **not proof of the plotting procedure**.

A restricted kinematic model with `V_x = U∞` and `V_r = U∞ R'` would have
dynamic-pressure ratio `1 + R'²` and static coefficient `Cp = −R'²`. Neither
is the archived shifted positive square. The full Drela **Eqs.162–163, p.34**
instead integrate the source distribution to obtain the velocity field.
The archived identity does not identify that integrated field or its sensors.

Thus the earlier [42.26% conditional Cp discrepancy](isae-sa13-pressure-reference-20261109.md)
remains mathematically correct *if the ordinate is taken as full Cp*. The new
evidence makes output interpretation the immediate issue. A value above 100
is not by itself evidence of invalid flow when the ordinate may be a different
velocity-squared quantity. There is no basis here for changing the core radius,
compressibility guard, physical pressure equation or circulation solver.

## Validation adapter correction

The current [SA-13 adapter](../../scripts/isae_suite_sa13.py) now records a
`PRESSURE_OUTPUT_MAPPING_UNRESOLVED` source diagnostic for this one series.
It computes and checks the identity from the pinned original coordinates and
preserves it in the saved result. Its wording now attributes the sensor and
Bernoulli description to the report instead of treating the archived
postprocessing as established.

The diagnostic adds no numerical or native pass. All eight target series,
612 expected values, original float values and unset precision contracts are
unchanged. The pressure series retains all 103 rows, including 47 unavailable
values. Removing the diagnostic or promoting it to a pressure-validation claim
is rejected by result validation.

**All 22 adapter checks pass**, including original MAT bytes/color/ordinate
verification, unchanged accounting, source-tamper rejection and the three new
diagnostic-preservation checks. They ran in two serial bounded batches:
21 checks in 4.90 s and one MAT check in 1.75 s. No production solver module
was changed or physical solve run.

## Reproducible evidence

- [Source-only audit](../../scripts/audit_sa13_pressure_geometry.py) and
  [analysis](../../artifacts/isae/sa13-pressure-geometry-20261109/analysis.json)
  retain every row, radius, slope, inferred offset and nine source pins.
- [Independent verifier](../../scripts/verify_sa13_pressure_geometry.py) and
  [receipt](../../artifacts/isae/sa13-pressure-geometry-20261109/verification.json)
  read the original MATLAB figure and use Decimal arithmetic, without importing
  OpenSwing or the audit implementation. Runtime was 9.01 s, peak RSS 218.6 MiB.
- Adapter receipts retain the
  [21 checks](../../artifacts/isae/sa13-pressure-geometry-20261109/adapter-tests.json)
  and [original-MAT check](../../artifacts/isae/sa13-pressure-geometry-20261109/adapter-mat-test.json).

Numerical imports and tests used one BLAS thread with 512 MiB address-space,
15 CPU-second and 25 wall-second limits. The existing browser, build and
kernel-loading hold remains in place. No primary completion fraction or
tracked comparison scope changed.
