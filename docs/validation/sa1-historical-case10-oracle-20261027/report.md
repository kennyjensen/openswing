# Historical CASE10 straight-wing saved-field diagnostic

This is separate from the registered original SA-1 comparison, which remains **19/154**. The historical literal driver names `CASE10.asw` and `CASE2_TEST_POLAIRE.txt`, requests NODE/I40, and specifies incidences 0–10 degrees. CASE10 retains lift slope **6.28**, rather than original SA-1's 6.2832. The 40/80-interval cosine grids are declared reconstructions, not recovered historical node arrays. [The receipt](report.json) pins the three sources, both diagnostic drivers, original zero-row error packets and all 22 completed states.

The [independent scalar replay](oracle.py) uses the wind-aligned horseshoe law with the source-specific control-point offset `h=6.28/(4*pi)`. It reconstructs velocities, local residuals, section and total forces/moments, near-field drag and infinite-wake quantities from retained Gamma, without production imports or new solves. All 22 states agree to roundoff: maximum differences are 3.02e-14 m/s in local velocity, 1.19e-15 in normalized residual, 2.73e-12 N in total force and 2.00e-15 across coefficients. All 123 frozen kernel pins and original input pins match.

For every nonzero native row, `CLi=(-4 Cm-CDi sin(alpha))/cos(alpha)` and `CLi=sqrt(pi AR e CDi)` are compatible within their combined printed intervals. At 1 degree they imply circulation integrals 10.22030655 and 10.22032276 m³/s, whereas the current 40-interval value is 10.25117804 m³/s. Native profile lift inferred from `CL-CLi` is -4.72895e-5; current profile lift is -4.71709e-5. The profile projection difference is small compared with the circulation-lift discrepancy.

| Alpha (deg) | Native CLi from Cm | CLi error,40 intervals (%) | CLi error,80 intervals (%) | CDi error,40 intervals (%) |
|---:|---:|---:|---:|---:|
| -0 | -0.000000000 | undefined | undefined | undefined |
| 1 | 0.072327989 | +0.302060 | +0.302060 | -0.010947 |
| 2 | 0.144700318 | +0.301885 | +0.301885 | -0.010921 |
| 3 | 0.217160532 | +0.302008 | +0.302008 | -0.010931 |
| 4 | 0.289753799 | +0.301938 | +0.301938 | -0.010804 |
| 5 | 0.362524106 | +0.301973 | +0.301973 | -0.010911 |
| 6 | 0.435518287 | +0.301567 | +0.301567 | -0.011274 |
| 7 | 0.508775588 | +0.301666 | +0.301668 | -0.011464 |
| 8 | 0.582340926 | +0.299807 | +0.299815 | -0.015062 |
| 9 | 0.656222423 | +0.290054 | +0.290096 | -0.031871 |
| 10 | 0.730239636 | +0.243991 | +0.244214 | -0.114792 |

The attached-flow circulation-lift bias is about 0.302%, versus about 0.058% in the original I200 archive. The ratio is approximately 5.23 while the requested node-count ratio is 5. This is consistent with a historical resolution-dependent discretization or force-integration effect. It does **not** establish an error order or identify a quadrature rule: the literal lift slopes differ, and the historical grids, circulation bases, executable and startup settings remain unknown. Each discrepancy above uses its own model/table pairing.

A concrete quadrature candidate remains insufficient. For uniform Glauert spacing, a Fourier endpoint-trapezoid circulation integral equals `cos(pi/(2*N))` times the midpoint integral. At N40 this lowers lift by 0.07710%, leaving the 1-degree CLi still 0.22473% above the native center. At N200 the reduction is 0.003084%, also much smaller than the original discrepancy. This derived alternative has neither the necessary size nor a demonstrated historical basis; no multiplier or quadrature change has been adopted. Forty-to-eighty refinement changes 1-degree current CL by only 5.25e-9.

Zero incidence is explicit. Both completed outputs have zero CL, lift, CDi and Cm, analytic profile drag `Cdf+Cdp=0.01123975`, and **undefined efficiency**. The native efficiency token 0 is preserved without fabricating a current prediction. The first two zero-row diagnostic packets failed while serializing `float(None)`; their solver calculations had completed. The root reused 20 nonzero packets and reran only those two zero rows, reporting 24 total physical calls. This audit adds none.

Strict retained-scalar accounting is **12/154 matches, 140 finite failures and 2 unavailable efficiencies**. An independent floating-point strip sum gives zero-row CD 0.011239749999999998 versus retained 0.011239750000000001. These straddle the native half-place boundary, so the independent oracle aggregate gives 10 matches. Both outcomes are retained. Exact decimal 0.00352562+0.00771413 lies exactly on the inclusive boundary. No precision allowance was expanded and no physical value was replaced. The [initial failed audit assertion](initial-attempt.json) and [initial script](initial-oracle.py) are preserved; the corrected audit keeps retained-scalar and oracle comparisons separate.

No operator defect was found. The stronger historical low-angle bias makes recovery of the actual node/circulation representation and discrete lift integration more valuable, but aggregate polar columns cannot distinguish those mechanisms. The original SA-1 inputs, comparisons and denominator remain unchanged.
