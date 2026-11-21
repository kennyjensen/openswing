# SA-11: the tested practical circulation counts do not remove the local failure

2026-11-08 UTC. Eighteen fixed production checks test pointwise counts of
20/30/40 requested intervals per logical beam, then Fourier counts of
20/30/40 modes per logical beam on two independently refined structural
meshes. **All eighteen exceed the local section-normal Mach limit.** No
accepted load-convergence comparison is available from this sweep.

The published sine-weighted residual projection reproduces the saved results.
A separate linear tangency solve also reproduces all six current-wind
Fourier circulation states within **2.9e-12 relative error**. Thus the large
local field in these states is not explained by failure of the nonlinear
iteration to converge. No default, production equation, original/bundled
input, Mach guard or tracked comparison scope changes. **SA-11 remains
163/4,592 at 5%.** The complete application remains unfinished.

## Source basis and the scope of this check

ISAE Part I **§5, p. 21** recommends 20–40 circulation variables or Fourier
coefficients based on an elliptical-wing study. It reports numerical
instabilities at much higher structural resolution after useful results
have converged. The extended manual **§1.3.5, Figure 1.13, p. 21** illustrates
19 Fourier modes on a wing with 180 structural nodes. Neither source identifies
the original SA-11 discretization or mode count.

These sources motivate varying structural nodes and circulation variables
independently. They do not establish that 20–40 variables should be assigned
to each logical beam of SA-11. This study explicitly tests that interpretation
in the current implementation; it does not claim to recover the native setup.

All calls use the report-derived **−4° upper-winglet twist**, aircraft angle
1°, speed 240 m/s, density 1.2256, automatic PG Mach, the existing stall law
and the local Mach guard. Original files are preserved. Each representation
is tested with both frozen and current-wind influences. Nodes use the normal
whole-beam cosine distribution and Glauert sampling, retaining mandatory
property/sweep/attachment stations. No mesh is selected by its archived error.

The per-logical-beam basis/domain qualification matters: Fourier coefficients
currently belong to each logical lifting beam. The exact native mode domain
for physically connected surfaces has not been independently established.

## Pointwise results

The requested count is applied to each of the three logical beams. Mandatory
stations add six intervals to the main wing, so total unknowns are larger
than three times the requested count. Nodes are counted per logical beam.

| Requested intervals/beam | Actual structural nodes | Actual intervals and circulation unknowns | Maximum Mach, frozen | Maximum Mach, current-wind |
|---|---:|---:|---:|---:|
| 20 | 69 | 66 | 2.12525 | 2.41421 |
| 30 | 99 | 96 | 4.41356 | 3.53300 |
| 40 | 129 | 126 | 7.60384 | 2.56250 |

All six pointwise states converge below the 1e-8 residual gate, and no section
exceeds its declared lift limits. Their smallest stall-limit margin is 9.73
transition widths. They still fail local Mach, including at the smallest
tested count. This is not solely a problem of the denser Fourier meshes.

## Fourier results

| Requested structural intervals/beam | Actual total intervals | Modes/beam | Total circulation unknowns | Maximum Mach, frozen | Maximum Mach, current-wind |
|---|---:|---:|---:|---:|---:|
| 64 | 198 | 20 | 60 | 46.404 | 2.72796 |
| 64 | 198 | 30 | 90 | 56.119 | 2.73858 |
| 64 | 198 | 40 | 120 | 36.485 | 2.87166 |
| 128 | 390 | 20 | 60 | 96.114 | 4.50408 |
| 128 | 390 | 30 | 90 | 177.453 | 3.67272 |
| 128 | 390 | 40 | 120 | 269.943 | 4.52915 |

The two meshes contain 201 and 393 structural nodes in total. All twelve
projected circulation systems converge. The frozen, 64-interval/20-mode
case has two sections outside their lift limits; its state is retained as
a diagnostic without a post-stall repair. The other eleven Fourier states
have no such sections.

The maximum unprojected local residual, normalized by the 240 m/s flight
speed, ranges from **47.78 to 543.90** for frozen influences and **0.822 to
1.705** for current-wind influences. These local residuals are not expected
to vanish in a truncated Fourier formulation. They are recorded to expose
what the converged projection does and does not constrain; no new local-
residual acceptance threshold is imposed. The independent Mach rejection
is unchanged.

## Projection, conditioning and solver checks

Drela's steady description **equations 150–153 and 200–204, pp. 31 and 40**
defines the sampled circulation and sine-weighted residual. The analyzer
constructs both directly from retained node angles and coefficients:

```
theta_a = (theta_i + theta_(i+1))/2
Gamma_i = sum_k A_k sin(k theta_a)
R_k = (2/pi) sum_i R_i sin(k theta_a) |Delta theta_i|
```

The constant normalization factor does not change the zero-residual
constraint. Reconstructed projected residuals match the saved vectors
exactly in this check; reconstructed circulation differs by at most
**1.28e-13 m²/s**. Thus the observed projection/local-residual distinction is
consistent with the published weighted formulation, not an indexing or
weight-normalization error found by this audit.

The analyzer also assembles the linear tangency matrix at the retained
geometry, normal, PG transform and wake direction, before applying the
reconstructed basis and projection. Its unscaled 2-norm condition numbers
range from approximately **796 to 3,841**. The six current-wind Fourier
states have at least 22.20 transition widths to a lift limit, and their
circulation agrees with the separately solved linear system within
2.9e-12 relative L∞ error. This is evidence against a nonlinear-solver or
floating-point failure as the cause of their excessive local velocity.

The frozen 64-interval/20-mode state differs by 5.92% from the linear solve
and includes two sections beyond the lift limits. The linear comparison is
diagnostic only; it is never substituted into a nonlinear physical result.
Rejected states produce no accepted CL, total drag or moment values.

## Consequence for the investigation

The planned practical-count sweep is complete. It supplies no supported
default change and no successful resolution range for the current SA-11
setup. Further count changes chosen solely to avoid a rejection would not
establish the requested ASWING fidelity.

The remaining questions are native treatment of the connected surface/mode
domain and of local velocity at the offset junction. The former is especially
relevant to the Fourier results, but cannot alone explain the pointwise
failures. The earlier [independent field integration](isae-sa11-winglet-current-wind-20261108.md)
and [matched native AVL comparison](isae-sa11-winglet-polar-20261108.md) remain
applicable evidence. A native producing mesh or a documented junction rule
would distinguish interpretations; no such evidence is claimed here.

## Reproduction and retained evidence

- [Fixed-case driver](../../scripts/verify-sa11-practical-resolution.py).
- [Predeclared cases and source pins](../../artifacts/isae/sa11-practical-resolution-20261108/plan.json).
- [Saved-state projection/matrix audit](../../scripts/analyze-sa11-practical-resolution.py).
- [Complete checked results](../../artifacts/isae/sa11-practical-resolution-20261108/analysis.json).

All eighteen production calls completed in small serial pairs with one BLAS
thread, a 45-second outer timeout per pair and a 768 MiB address-space limit.
They totaled **3.220 s** of aerodynamic-call time, excluding setup/imports and
provenance checks. There were no solver timeouts. The analyzer performs no
new nonlinear aerodynamic solves; its linear tangency systems are separate
diagnostics. Verification covers 164 unchanged input/production/status pins,
all eighteen result artifacts, exact applied settings and counts, residuals,
local Mach, stall margins, circulation reconstruction and projection weights.
