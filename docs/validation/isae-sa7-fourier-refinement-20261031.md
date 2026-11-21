# SA-7: Fourier closure does not resolve low-lift efficiency

2026-10-31. The −5-degree full-aircraft efficiency difference remains
**3.54%** using either 20 or 40 circulation modes per wing, across 64, 128
and 256 cosine intervals. A separate continuous-wake calculation using the
actual solved Fourier coefficients preserves the discrepancy.

All twelve new cold calculations finish. The sample includes −5 degrees
and a zero-incidence control, both mode counts and all three meshes, with
six matching saved pointwise controls. It retains the published strength 40,
original geometry, section data, wake cores, current-wind influences and
zero Prandtl–Glauert Mach. No native producing mode count is asserted.

| Circulation representation | Native checks passing | Gains | Losses |
|---|---:|---:|---:|
| Saved pointwise controls | 39/42 | — | — |
| 20 Fourier modes | 39/42 | 0 | 0 |
| 40 Fourier modes | 39/42 | 0 | 0 |

Each representation fails only the three −5-degree efficiency checks.
All lift, drag, CL, CD, CDi and CM checks pass, as do all zero-incidence
efficiency checks. All seven channels are retained at each condition.

The native −5-degree efficiency is 0.369357:

| Intervals per wing | 20-mode efficiency | 40-mode efficiency |
|---|---:|---:|
| 64 | 0.382431343 | 0.382431218 |
| 128 | 0.382432228 | 0.382432108 |
| 256 | 0.382432450 | 0.382432330 |

This preserves the earlier pointwise refinement result. The two tested
Fourier truncations do not provide a correction to the last low-lift error.

## Independent checks

A separate calculation reconstructs the sine sampling functions and their
weighted residuals, then integrates the published section forces and moments.
Across 3,584 strips, maximum normalized strip-force discrepancy is 1.06e-18;
the maximum total-force discrepancy is 1.36e-16. The maximum weighted
circulation residual is 9.12e-17. The maximum local residual is 6.34e-4;
the truncated representation enforces the weighted equations, not pointwise
tangency.

An independent infinite-filament calculation reproduces the reported discrete
CDi, CLi and efficiency within 3.39e-15. A second method calculates each
continuous wing's self-drag from Fourier orthogonality and its cross-wing
drag by Gaussian integration. It uses the solved coefficients directly,
with no fitted circulation reconstruction. Quadrature refinement changes CDi
by at most 1.06e-17, and mutual-drag reciprocity agrees within 3.71e-18.

At −5 degrees and 256 intervals, the continuous efficiencies are 0.382432376
and 0.382432256 for 20 and 40 modes. Both remain 3.54% high. Zero-incidence
efficiency errors stay below 0.066%. This evidence rules out these mode choices
and the tested wake-reporting arithmetic as explanations for the discrepancy;
it does not authenticate native geometry or run settings.

The [full results](../../artifacts/isae/sa7-fourier-refinement-20261031/report.md),
[per-state evidence](../../artifacts/isae/sa7-fourier-refinement-20261031/analysis.json),
and [verification receipt](../../artifacts/isae/sa7-fourier-refinement-20261031/receipt.json)
retain all comparisons, source hashes and process accounting. Two postprocessing
corrections required no new physical calls. Production and registered counts
remain unchanged: **395/406** full-aircraft checks at the registered settings,
or the separate, unconfirmed strength-20 diagnostic **404/406**. The current
fore-only pairing problem remains separate from these full-aircraft results.
