# FFWT-4 fixed-wing initial comparison

The literal `FFWT_Fixed.asw` now has **21/200 passing values** in the first
history at the 5% allowance, or **21/1,600** across all eight archived fixed-wing
histories. These values span 0–0.298 s, before the gust arrives. This is initial
state agreement, not a completed gust-response validation. Other configurations
and shared comparison registration remain open.

| Initial mesh | Actual nodes | Root moment (N m) | Native (N m) | Error |
|---|---:|---:|---:|---:|
| Nominal cosine16 | 47 | 0.740953052 | 0.732178 | 1.19849% |
| Nominal cosine32 | 63 | 0.736245026 | 0.732178 | 0.55547% |

Both cold equilibria and their independently restored residuals pass 1e-8.
The prescribed-frame transient on nominal32 accepts 20 steps at dt=.0149,
without rejection; maximum residual is 1.158e-13. It retains BDF1 startup,
BDF2 continuation and a validated portable checkpoint. The native table has
200 rows including t=0, ending at step199, despite the driver's `200` command.
The remaining 179 rows of this history and seven complete fixed-wing histories
remain in the denominator.

Model bytes, mass distributions, stiffness, source sensors and physical
equations are unchanged. Speed22 and incidence6 come from the driver. The type5
gust uses the literal `-10.9366 0 10.9366 .6978`, with the existing documented
gradient-length mapping. It is zero on the wing at startup; adding its identity
to the transient's fresh equilibrium reproduces the earlier root moment within
1e-8 N m. The source's internal name is `FFWT Removed`, although both the driver
and filename identify `FFWT_Fixed`; the complete source is retained.

Cosine spacing, pointwise circulation, PG0 and other operating defaults remain
declared. The driver asks for I100 on beam1 and I40 on nonexistent beams2/3.
Exact historical nodes and defaults are not authenticated. The two initial
meshes differ by about 0.64%, so strict mesh convergence is not established.
No phase, amplitude, mass or stiffness was fitted to output.

Reproducible helpers are `scripts/verify-isae-ffwt4-initial.py` and
`scripts/verify-isae-ffwt4-time.py`. Evidence is in
`artifacts/isae/ffwt4-initial-20261106/{n16,n32}/` and
`artifacts/isae/ffwt4-time-20261106/`, including `assessment.json` and the complete
`s020` result/checkpoint. All jobs completed and were reaped. No continuing
background solve is required to inspect these results.
