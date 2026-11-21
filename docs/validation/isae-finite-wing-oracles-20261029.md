# SA-1–SA-5: independent finite-wing velocity checks

Updated 2026-10-29. These checks found no percent-scale error in the tested
bound-vortex, trailing-wake or section-closure calculations. They do not explain
the remaining native ASWING differences or change any registered ISAE score.
The current totals remain **1,190/1,288 default** and **1,208/1,288 modified**.

## Finite-chord continuum comparison

The new [verifier](../../scripts/verify-finite-wing-modes.py) compares the
production factored influence operator with independently integrated scalar
Biot–Savart fields. It prescribes circulation rather than solving for it:
`Gamma = A sin(k theta)`, `y = B cos(theta)`, with `A=B=1`, modes 1–3,
control-point offsets `d=0.1,0.3`, and 32, 64 and 128 cosine intervals.
The bound line runs from negative to positive y; trailing rays point along +x.
Mach number, core radius and image contributions are zero.

For a receiver at `x=d, y=B cos(theta0)`, define `delta=y−B cos(theta)`.
The independent continuum fields are

```text
w_bound = −d A B/(4 pi) integral[0,pi]
          sin(k theta) sin(theta) / (d² + delta²)^(3/2) dtheta
w_wake  = A k/(4 pi) PV integral[0,pi]
          cos(k theta) [1 + d/sqrt(d² + delta²)] / delta dtheta
```

The wake integral uses a Cauchy principal-value transformation with a smooth
numerator. An analytic control removes the offset-dependent wake multiplier:
`w_half = −A k sin(k theta0)/(4 B sin(theta0))`. The full finite-chord field
is not equated to the limiting Prandtl expression at fixed aspect ratio.

All **198/198 predeclared checks pass**, across 18 prescribed fields and 54
receiver rows. The largest final-grid component error is `5.749e-4` normalized
by `A/B`; the largest final refinement ratio is 0.25063, below the declared 0.4
limit. Refined quadratures agree within `3.317e-12` scaled, the half-wake
identity within `5.299e-16`, and the production component sum within `4.441e-16`.

| Offset d | Mode | Max total-field error, N=32 | N=64 | N=128 |
|---:|---:|---:|---:|---:|
| 0.1 | 1 | 7.478e-4 | 1.882e-4 | 4.706e-5 |
| 0.1 | 2 | 4.084e-3 | 1.012e-3 | 2.518e-4 |
| 0.1 | 3 | 9.061e-3 | 2.295e-3 | 5.749e-4 |
| 0.3 | 1 | 3.426e-4 | 8.571e-5 | 2.143e-5 |
| 0.3 | 2 | 2.687e-3 | 6.593e-4 | 1.632e-4 |
| 0.3 | 3 | 6.727e-3 | 1.547e-3 | 3.767e-4 |

Errors are absolute field errors normalized by `A/B`, not percentages relative
to a potentially zero modal velocity. Each grid uses its three interior
Glauert receiver indices `N//4, N//2, 3*N//4`, so the receiver positions change
slightly with refinement. This is sampled convergence evidence, not a uniform
error bound or a fixed-location formal order test. It does not cover tip/root
singular limits, nonlinear equilibrium, curved geometry or native setup parity.

The [protocol](../../artifacts/isae/finite-wing-mode-oracle-20261029/protocol.json)
pins the script, theory text and 130 kernel modules before execution.
The [report](../../artifacts/isae/finite-wing-mode-oracle-20261029/report.json)
retains each field and gate; the
[terminal receipt](../../artifacts/isae/finite-wing-mode-oracle-20261029/terminal-receipt.json)
records exit 0, reaped execution, no timeout and zero nonlinear solves.
An [independent saved-result review](../../artifacts/isae/finite-wing-mode-oracle-20261029/independent-review.md)
passes 1,271 audit checks and reproduces all 198 declared gates. It checks
the derivation and saved arithmetic without repeating integrations. The
quadrature comparisons are numerical evidence, not rigorous error bounds;
full planar vector components were not retained for independent replay.

## Independent SA-5 dihedral replay

A separate [scalar replay](../../artifacts/isae/sa1-sa5-finite-wing-review-20261029/report.md)
reconstructs two saved 400-interval SA-5 states at 18°, one per spacing rule.
It independently reads the literal model, rebuilds the straight dihedral legs,
Glauert receiver locations and section frames, and evaluates finite bound
segments, shared wake strengths, force-point flow, control-point flow and
the smooth-stall residual. Node parameters and solved circulation are retained
inputs; no production kernel is imported and no new equilibrium is solved.

Across 800 panels, geometry agrees within `1.55e-15 m`, section cl within
`1.96e-13` scaled, and force-point velocity within `1.86e-11` normalized.
The modified-grid replay passes every gate. The default-grid replay retains
one declared failure: panel 398 has a normalized local-residual difference
`1.449e-10`, exceeding its `1e-10` comparison gate. Both saved production
solutions still pass their original physical validity and convergence gates.

A separate, predeclared [precision study](../../artifacts/isae/sa1-sa5-finite-wing-review-20261029/precision/report.md)
holds the source nodes and circulation
fixed and evaluates panels 398, 1 and 199 with binary64 and 80-digit Decimal
arithmetic. At panel 398, increasing arithmetic precision leaves the original
coordinate error at `−1.4412e-10`. Substituting the saved force-point receiver
coordinate and reconstructing its control point with the same documented
offset reduces the 80-digit difference to `+3.1716e-14`. This isolates the
tiny receiver-coordinate displacement as the main cause of that scoped replay
miss. It is a qualified mixed-coordinate diagnostic; the original failed run
and its gate are preserved.

The saved solver output contains no full control-point velocity vector.
Its normal projection is reconstructed from the saved local residual and
section closure; the transverse replay components lack an archived-vector
comparator. Neither this replay nor its precision study is a comparison with
an original ASWING executable. The tiny replay difference does not account
for the percent-level induced-drag deficit.

## Implications for the remaining cases

The [source review](../../artifacts/isae/sa4-finite-wing-review-20261029/review.md)
finds the inspected pointwise/Fourier sampling and residual weights consistent
with the published equations. The same-surface core exclusion also follows
the inspected formulation; adding a fitted core is unsupported.

Together with the earlier [section-limit and loading audit](isae-sa1-sa5-loading-audit-20261029.md),
these checks narrow the investigation without establishing a universal fix.
SA-1/SA-5 retain high-angle circulation deficits that amplify into induced-drag
error. SA-2 benefits from documented-coordinate spacing reconstruction.
SA-4 retains its distinct curved-axis geometry and large tip-wake velocity
problems. Production equations, mesh defaults and acceptance tolerances are
unchanged by this investigation.
