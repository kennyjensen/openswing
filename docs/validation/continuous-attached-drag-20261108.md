# Continuous loading: isolate attached-force sampling from span discretization

2026-11-08 UTC. A continuous reconstruction of the saved swept-wing circulation
retains an approximately **1% drag deficit** when the entire attached-leg force
is represented by one three-quarter-chord sample. Integrating the globally
summed force along the attached legs restores the continuous Trefftz drag
identity. A separate smooth polynomial control gives a small error of the
opposite sign, confirming that the sampling error depends on the loading shape.

This identifies a force-sampling mechanism without discrete wake filaments.
It does not establish an exact correction for the earlier 0.85% discrete result,
because the reconstruction changes its circulation representation, flattens
incidence, and uses pure vortex Kutta–Joukowski loading. Nor does a total-drag
identity establish finite local forces or valid moments at a winglet junction.
Production code and registered SA-11 remain unchanged: **163/4,592 at 5%**.

The subsequent [native AVL comparison](avl-native-controls-20261108.md)
establishes a real finite-chord reference and checks strip forces and moments.
Its force convention differs from the attached-leg construction here, and
its winglet control still needs local junction refinement despite stable totals.

![Continuous force-sampling control](../../artifacts/isae/continuous-attached-drag-20261108-review/continuous-attached-drag.png)

## Defined comparisons

This follows the [solved attached-leg study](attached-wake-forces-20261108.md).
Every new calculation is a prescribed-field calculation; there are no new
circulation solves or fitted force corrections.

The geometry is a straight planar bound line with half-arclength `L=5 m`,
perpendicular chord 1 m, wind along x, density 1 kg/m³ and zero core. Attached
legs have length `d=0.75 m`. The single-point force samples the leg at
`xi=0.5 m` downstream of the quarter-chord line, corresponding to the section's
three-quarter-chord point. The free wake starts at the physical trailing edge.

Two circulation descriptions are tested:

- Six smooth polynomial controls use
  `Gamma(s)=0.2*(1-s^2/L^2)*(1+a*s/L)`, with `a=0 or 0.2` and sweep `0 or ±30°`.
  These distributions vanish at the tips and have finite endpoint slopes.
- Three reconstructions retain **every original circulation sample exactly**
  from the saved +30° controls: N64/5°, N128/5° and N128/1°. A continuous linear
  interpolant connects the original interval midpoints to zero circulation at
  the two physical tips. This uses no regression or reference fitting. The
  original quarter-chord line is retained, while chord incidence is flattened
  to zero for the planar identity below.

The prescribed circulation does not solve the zero-incidence boundary
condition. These are controlled tests of induced-force accounting, not newly
solved aircraft states or reference replacements.

## Pair-integral derivation

The following derivation is part of this investigation. Let `C=cos(Lambda)`,
`S=sin(Lambda)`, and define the compactly supported correlations

```text
R(delta) = integral Gamma'(s) Gamma'(s-delta) ds
Q(delta) = integral Gamma(s)  Gamma'(s-delta) ds
Q'(delta) = R(delta),  Q(0) = Q(2L) = 0.
```

For a wind-aligned free ray, evaluate its normal-velocity kernel at a receiver
located `h` ahead of the trailing edge and separated by span arclength `delta`.
With `r_h=sqrt(delta^2+h^2)`, direct Biot–Savart algebra gives

```text
K(delta,h) + K(-delta,h) = S / [2*pi*(h+C*r_h)]
K(delta,h) - K(-delta,h) = delta / [2*pi*r_h*(h+C*r_h)].
```

Both identities are independently checked against the production vector
semi-infinite kernel. For these straight, equal-chord geometries, the globally
summed bound-induced and attached-self-induced contributions to attached-leg
drag cancel by antisymmetry and integration by parts. The remaining free-wake
contribution permits a chord integral without individually integrating the
singular local bound/attached intersection forces.

All integrals below run from `delta=0` to `2L`; density is 1. Write
`r=sqrt(delta^2+d^2)` and `h_star=d-0.5`:

```text
D_T = (1/(2*pi)) integral Q(delta)/delta ddelta

D_bound = (C/(2*pi)) integral [Q(delta)/delta]
                          * (r+C*d)/(d+C*r) ddelta

D_AT_sample = (d*S^2/(2*pi)) integral R(delta)
                          / [h_star+C*sqrt(delta^2+h_star^2)] ddelta

D_AT_integrated = (1/(2*pi)) integral R(delta)
    * {log[(d+C*r)/(C*delta)] - C*asinh(d/delta)} ddelta.
```

Integrating the last expression by parts gives

```text
D_AT_integrated = (d*S^2/(2*pi)) integral Q(delta)/[delta*(d+C*r)] ddelta
D_bound + D_AT_integrated = D_T.
```

The logarithmic endpoint is integrable; it is not replaced by a core or cutoff.
`D_AT_integrated` is evaluated from the logarithmic expression, while the
comparison uses the separately evaluated bound and Trefftz expressions. An
additional audit obtains Trefftz drag from the independent energy form
`D_T = -(1/(2*pi))*integral R(delta)*log(delta) ddelta`.

This is an algebraic consistency result for global drag. It does not establish
finite pointwise loads, section stall velocities, moments, derivatives or a
full finite-chord physical solution. The local cancellation cannot be replaced
by simply deleting selected vortex influences in production.

## Results

| Continuous loading, all at 30° sweep | Single-sample total drag versus its continuous Trefftz value | Chord-integrated total |
|---|---:|---:|
| Polynomial, symmetric | +0.04612% | Matches algebraic identity |
| Polynomial, asymmetric `a=0.2` | +0.04267% | Matches algebraic identity |
| Reconstructed N64/5° circulation | -1.09434% | Matches algebraic identity |
| Reconstructed N128/5° circulation | -1.01287% | Matches algebraic identity |
| Reconstructed N128/1° circulation | -1.01386% | Matches algebraic identity |

The saved-shape results demonstrate a deficit with the same sign and order of
magnitude as the preceding discrete calculations, even with continuous wake
loading. This supports single-point attached-force sampling as a contributor.
It does not prove that all of the preceding discrepancy has that cause.

The comparison denominator also changes under reconstruction:

| Saved source | Original discrete Trefftz drag (N) | Reconstructed continuous Trefftz drag (N) | Change |
|---|---:|---:|---:|
| N64/5° | 0.0213124802 | 0.0218505214 | +2.52454% |
| N128/5° | 0.0213139150 | 0.0215845111 | +1.26957% |
| N128/1° | 0.000853021858 | 0.000863855653 | +1.27005% |

Those differences must remain visible. The continuous reconstruction is a
distinct representation, and neither its reference nor its apparently exact
global balance is an original-ASWING validation result. For the polynomial
controls, reversed sweep preserves total drag and the unswept control recovers
the ordinary Trefftz relation without an attached-leg drag contribution.

## Verification

Polynomial correlations are obtained by coefficient arithmetic, not fitting.
Direct overlap integrals check them independently. Direct velocity quadrature
at orders 64, 128 and 256 independently checks bound and sampled attached drag;
the largest final force difference is **6.15e-12 N**. Pair-kernel identities
agree within **8.33e-17** in the declared units.

For each saved shape, the derivative autocorrelation is constructed from exact
interval-overlap events. Direct overlap calculations check that representation.
Quadrature orders 4, 8 and 16 are applied separately on every correlation
interval; the logarithmic first interval is integrated adaptively. The largest
8-to-16 force change is **2.29e-12 N**. The independent logarithmic-energy
calculation agrees with the other Trefftz expression within **1.82e-17 N**.
Extended arithmetic is used for the piecewise correlation bookkeeping; these
small algebraic residuals do not represent comparable physical accuracy.

All nine prescribed controls finish, with no new circulation solves. Recorded
numerical stages total 5.58 seconds, excluding startup and analysis/plotting.
Jobs run serially with one BLAS thread and bounded time/memory. All 143 pinned
production/status/scope files remain unchanged.

- [Polynomial derivation and direct-field checks](../../scripts/verify-continuous-attached-drag.py)
- [Saved-shape reconstruction](../../scripts/verify-attached-drag-reconstruction.py)
- [Independent energy audit and plotting](../../scripts/analyze-continuous-attached-drag.py)
- [Complete analysis, comparisons and manifests](../../artifacts/isae/continuous-attached-drag-20261108-review/analysis.json)
- [Standalone SVG plot](../../artifacts/isae/continuous-attached-drag-20261108-review/continuous-attached-drag.svg)

The next reference must check distributed forces and moments as well as total
drag. A resolved finite-chord or consistently coupled section formulation is
needed before applying these ideas to SA-11's offset and branching winglet
roots. This study supplies a continuous drag identity for that verification;
it is not a proposed global-drag override or a production force-law change.
