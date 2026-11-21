# Daedalus: Figure 7 in-plane stiffness and physical response

The paper and the public `dae.asw` have a measurable local in-plane stiffness
difference, but the tested reconstruction does **not** explain the rudder Bode
mismatch. After a physical retrim, yaw at 1.157378 Hz changes from **0.074218**
to **0.074261 deg/s per F3**, a **+0.0583%** change. The published magnitude is
**0.033986**, leaving **+118.50%** error. All twelve sampled magnitudes change
by less than **0.096%**. No production or public-aircraft change is justified.

![Independent property comparison](../../artifacts/daedalus-paper-stiffness-20261114/trace/stiffness.png)

## Independent drawing comparison

The [authoritative index](aswing-authoritative-references.md), original source
catalog and [paper source record](isae-st4-node-placement-sources-20261109.json)
were consulted. The source is Drela's **Method for Simultaneous Wing Aerodynamic
and Structural Load Prediction**, AIAA-89-2200, Figure 7 on PDF p. 8 / printed
p. 329, retained in [reference/](../../reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf).
Section 5.2 attributes stiffness discontinuities to changes in spar ply layup.
This is the older wing calculation, not an authenticated input for the later
full-aircraft Bode drawing. The paper's 240 lb flight calculation and Figure 7's
230 lb plotting normalization remain distinct.

The native black **EIn** curve is traced independently of the current model
overlay or Bode values. Calibration is retained from the preceding
[property audit](daedalus-paper-properties-20261114.md): x = 132 to 908 pixels
represents semispan fraction 0 to 1; ordinate zero is y = 438.5, with 96.6
pixels per unit of `5 EIn / (Lref b²)`. Dimensional reconstruction assumes
Lref = 230 lb and b = 112 ft. Modern `EInn` is the corresponding in-plane
stiffness under the existing principal-axis convention.

The independent visual corridor finds dark pixels in **99.59%** of retained
columns. Crossings, the root endpoint and merged outer curves are excluded.
There are **18 distinct readable original table stations** (19 entries because
28 ft is repeated). Their median absolute difference from the public input is
**2.76%**. The largest difference occurs at 34 ft, where the drawn drop occurs
earlier. Because this discrepancy is present at an original input knot, it
cannot be attributed solely to interpolation between modern knots.

| Semispan station | Public EInn, million lb ft² | Traced EIn, million lb ft² | Trace minus public |
| --- | ---: | ---: | ---: |
| 16 ft | 1.290 | 1.211 | -6.10% |
| 28 ft | 0.901 | 0.881 | -2.21% |
| 30 ft | 0.854 | 0.793 | -7.12% |
| 34 ft | 0.712 | 0.469 | -34.14% |

At 34 ft, independent ±2-pixel horizontal/vertical bounds give **0.457–0.481
million lb ft²**. These are drawing-placement bounds, not confidence intervals;
they exclude normalization, span, historical-version and unknown drawing errors.
The full [station table and trace](../../artifacts/daedalus-paper-stiffness-20261114/trace/)
retain the masks and bounds, including their larger values at steep drops.

## Conditional input and physical solve

The separate [conditional aircraft](../../artifacts/daedalus-paper-stiffness-20261114/case/dae-figure7-inplane-sampled.asw)
changes only readable wing `EInn` entries, using the nominal trace selected
before the response calculation. All original table stations, multipliers,
other properties and unrelated file lines are retained. Root, 36 ft and 40–56 ft
values remain literal because those drawing values were excluded. The original
SEGSPL interpolation is retained: this samples the paper curve at existing
knots and does **not** reconstruct its complete sharp-step shape. No mass
modification from the preceding studies is included.

The original source mesh is unchanged: 108 nodes, 103 intervals and 82
circulation unknowns. A fresh physical nonlinear trim at 6.7 m/s, Mach 0.1,
with live influence, unsteady lag, plume and bilateral braces converges to
**7.9823e-11** maximum scaled residual. Total weight remains **233.301933 lb**,
alpha becomes **3.055890°**, and the tips lie **8.048737 / 8.053370 ft** above
the loaded root. There is no constant residual offset.

The dynamic calculations retain all **2,044 states**. The original descriptor
factor is used only as a preconditioner: each correction evaluates the complete
changed aircraft's nonlinear harmonic residual, including changed geometry,
preload, aerodynamics and actual rudder forcing. Its condition estimate is not
a rank certificate for the changed operator. Each frequency reaches the
unchanged gates of maximum residual <2e-11 and next relative output correction
<2e-7. The **same final state** also passes at independent derivative widths
0.002 and 0.004. Their maximum residual is **9.4511e-12**; maximum paired output
correction difference is **4.4156e-9 relative**.

| Frequency, Hz | Public-model yaw | Reconstructed-stiffness yaw | Published yaw | Change from public model |
| --- | ---: | ---: | ---: | ---: |
| 0.1 | 0.121763 | 0.121776 | 0.118238 | +0.0107% |
| 1.157378 | 0.074218 | 0.074261 | 0.033986 | +0.0583% |
| 1.5 | 0.094316 | 0.094393 | 0.081818 | +0.0809% |

Yaw units are deg/s per F3 unit. At the published dip, roll, sideslip and bank
magnitudes change by -0.0758%, +0.0177% and -0.0953%, respectively.

![Four-output comparison](../../artifacts/daedalus-paper-stiffness-20261114/report/comparison.png)

Only the three markers per output are new results; continuous curves are the
retained literal-model sweep and published drawing. This is neither a new
frequency sweep nor a claim about the exact minimum of the changed model.
The partial reconstruction does not exclude every possible historical stiffness
distribution, but the independently visible differences tested here have a very
small effect. They provide no reason to tune wing stiffness to the Bode curve.

## Reproducibility

Driver: [check_daedalus_paper_stiffness.py](../../scripts/check_daedalus_paper_stiffness.py).
Evidence: [study directory](../../artifacts/daedalus-paper-stiffness-20261114/),
[verification receipt](../../artifacts/daedalus-paper-stiffness-20261114/verification.json).
All 13 serial jobs exit successfully and are reaped, under 512 MiB address-space,
15 CPU-second and 25 wall-second limits with one BLAS thread. The nine response
jobs record 105 full-residual probes, in addition to setup, trim and report
evaluations. No browser, Node, build or background solver jobs ran. Production
code, the public `dae.asw`, the authoritative catalog and ISAE counts/scopes
remain unchanged.
