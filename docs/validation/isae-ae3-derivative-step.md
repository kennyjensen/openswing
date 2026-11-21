# AE-3 control derivative step diagnostic

Both smaller derivative API steps pass the existing nonlinear control checks for **20O-05-n128**. The original `1e-5` failures remain recorded. The two new calls restored the same saved equilibrium; no equilibrium was re-solved, and no model, measurement, mesh or production default changed.

The comparison uses native stability `Cl` per literal file-flap setting. It applies neither the separate experimental sign/area mapping nor a radian conversion. The saved nonlinear centered estimates are `-0.00021099868207671217` at `h=0.05` and `-0.0002109986928631703` at `h=0.025`.

The gate remains `abs(D_h - D_step) <= 1e-9 + 1e-5*abs(D_step)`, approximately `3.110e-9` here.

| API step | Native Cl control derivative | Error versus h=0.05 | Error versus h=0.025 | Both gates |
|---|---:|---:|---:|---|
| 1e-05 | -0.00021099502792073339 | 3.654156e-09 | 3.664942e-09 | Fail, retained |
| 5e-06 | -0.00021099777931970256 | 9.02757e-10 | 9.135435e-10 | Pass |
| 2.5e-06 | -0.00021099846717677857 | 2.148999e-10 | 2.256864e-10 | Pass |

The adjacent derivative changes are `-2.7513989691728587e-9` and `-6.878570760128922e-10`, with ratio **0.25000266545119765**. This is consistent with centered-stencil step sensitivity. The unchanged API step controls state/input probes and directional output differencing together; this study does not isolate their contributions. No extrapolated value replaces any reported result.

The actual output stencils were:

| API step | control.1 output step | normalized p output step |
|---|---:|---:|
| 1e-05 | 1.0000000000000001e-05 | 2.5010289302070995e-06 |
| 5e-06 | 5.0000000000000004e-06 | 1.2505106679671589e-06 |
| 2.5e-06 | 2.5000000000000002e-06 | 6.2525485934036305e-07 |

All restored states and base residuals match the saved reference byte for byte. Both new base residuals are zero; the largest freshly recomputed full `J dx + R_p` normalized residual is `5.485e-14`, below the unchanged `1e-8` gate. The dense SVD rank threshold remains `1e-10`. Full matrices, responses, serialized outputs and parameter metadata are retained. Both children completed within their 300-second caps and were reaped.

This demonstrates numerical consistency for this selected point at the two smaller steps. It does not establish a universal step choice, isolate a pure Jacobian cause, or resolve mesh and experimental gaps. The normalized `p` column is reported without adding a new acceptance gate. ISAE coverage remains **17 partial / 24 pending / 0 fully validated**, with AE-3 pending.

[Machine-readable study](isae-ae3-derivative-step.json) · [Raw reports, matrices and reviews](isae-ae3-derivative-step-20261024-evidence.zip) · [Original locked-wing comparison](isae-ae3-locked-control.md)
