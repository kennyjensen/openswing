# SA-11: fixed uniform-32 winglets across two pre-stall polars

2026-11-08 UTC. **31 of 42 operating points produce complete solutions and match
all seven archived outputs within 2.22%.** This extends the successful 1°
[spacing diagnostic](isae-sa11-winglet-spacing-20261108.md) without changing the
mesh between operating points or increasing its resolution.

The other eleven states converge in circulation but still reject the local
section-moment law at the winglet roots. These failures occur at larger loads
on the same 32-strip grid; they are separate from the earlier 64-strip
refinement check. No additional mesh-convergence gate is imposed on the
successful comparisons.

## Results

All quarter-degree rows from 0° through 5° were declared before solving at both
archived speeds. The main wing has 32 intervals and each winglet has 32 uniform
intervals: 96 total. No spacing, model property or equation changes with alpha.

| Archived label / actual speed | Complete matching points | Matching alpha range | Local-Mach rejections | Diagnostic scalar checks |
|---|---:|---|---|---:|
| 0.70 / 240 m/s | 17 of 21 | 0°–4°, every 0.25° | 4.25°–5°: four points | 119/147 |
| 0.80 / 272 m/s | 14 of 21 | 0°–3.25°, every 0.25° | 3.5°–5°: seven points | 98/147 |
| **Total** | **31 of 42** | | **Eleven points** | **217/294** |

Each point has the seven retained targets: lift, drag, CL, CD, CDi, Cm about
the body origin, and span efficiency. Dimensional force and its coefficient
are related outputs, not independent physical experiments. Every rejected
point keeps all seven targets in this diagnostic denominator. Finite force
sums from those states are not accepted complete solutions or extra passes.

| Quantity | Maximum absolute error among accepted 240 m/s points | Maximum absolute error among accepted 272 m/s points |
|---|---:|---:|
| CL | 0.506% | 0.513% |
| CD | 1.061% | 0.410% |
| CDi | 1.093% | 1.058% |
| Cm about origin | 0.465% | 0.443% |
| Span efficiency | 2.215% | 2.217% |

Dimensional lift/drag errors differ from the respective coefficient errors by
less than 0.001 percentage point because the archive prints them separately.
The fresh 240 m/s, 1° result exactly reproduces the earlier circulation,
velocity and section CL arrays. The sampled geometry is identical across
all 42 calls.

![Fixed uniform-32 polar comparison](../../artifacts/isae/sa11-uniform-polar-20261108-v2/uniform32-polar.svg)

The shaded intervals in the first two panels have unavailable complete moments;
no valid-result error curves are plotted there. Open markers in the final panel
denote rejected states. The green background is the user's unchanged ±5%
comparison allowance.

## Remaining failure mechanism

At 240 m/s, maximum section-normal Mach rises from 0.669 at 0° to 0.986 at 4°,
then exceeds one at 4.25° and reaches 1.082 at 5°. At 272 m/s it rises from
0.742 to 0.992 at 3.25°, exceeds one at 3.5°, and reaches 1.162 at 5°.
Each rejected state has exactly two invalid receivers, one at each winglet root.

Increasing circulation strengthens the root-wake encounter even on the fixed
mesh. At the worst receiver, summed wake-induced speed grows from 126.6 to
321.9 m/s over the 240 m/s polar, while the bound contribution grows from
3.42 to 8.89 m/s. At 272 m/s the corresponding ranges are 133.9–340.4 m/s
and 3.30–8.60 m/s. These vector norms are not speeds to add arithmetically.
They identify the wake as the dominant source of the large local velocity;
they do not establish physical supersonic flow around the real winglet.

Every circulation residual is below 4.53e-15. Every section stays at least
7.91 configured stall-transition widths inside its lift limits. Stall and
incomplete circulation convergence do not explain these eleven rejections.
Their formal force totals remain close to the archive, but Drela's local-Mach
section-moment expression is undefined at these root velocities. No guard is
removed and no missing moment is replaced with zero.

The 32-strip comparisons are successful over the ranges listed above. The
subsequent [minimum-spacing implementation](isae-sa11-minimum-spacing-20261108.md)
now checks the already prescribed uniform-16 spacing across this same whole
interval at both speeds: all 294 comparisons pass with complete moments.
One minimum and one applied mesh cover every angle; no angle-specific mesh or
fitted core radius is used.

## Source and scope qualifications

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Jan Part I **p. 35, Figure 22 p. 39 and Figure 40 p. 68**
govern the case, published curves and upper-winglet incidence. Drela steady
**Eqs. 64–74 and 150–161**, together with the User Guide's **Joint** and
**Physical index** sections, govern the retained loads, sampling and zero-core
interaction of this shared physical surface.

The model remains the disclosed report-minus4 upper-winglet alternative, with
the earlier Joint multiplier correction. The archived input instead has +4°
twist and an unresolved Joint multiplier row. This comparison uses original
section data, frozen influences, whole-beam Glauert receivers, density 1.2256,
sound speed 340.21 and global PG Mach equal to actual speed divided by 340.21.
The actual speeds 240/272 m/s come from both the source scripts and output
columns; filename Mach labels are not substituted for them. The scripts are
read as data, never executed. The paper's additive drag plotting allowances are
not applied to raw coefficient comparisons.

All selected lift/coefficient and drag/coefficient pairs admit the literal
dynamic-pressure/reference-area normalization within their printed rounding
intervals. Both source tables match the retained Git blob and SHA-256 manifest.
The native producing mesh and full startup settings remain unavailable.

These are separately labeled comparisons against documented ASWING outputs,
not matches to experiment. The primary SA-11 suite retains its original
models, all sixteen polars, 0°–10° rows, fields and declared mesh requests:
**163/9,184 at 5%** remains unchanged. The 217 diagnostic matches are not added
to that total or its progress curve. Other configurations, 5.25°–10° rows and
the conflicting 0.75/0.78 normalizations remain outstanding.

## Verification and execution

The independent checker re-reads the literal 82-column tables, authenticates
172 source pins, and recomputes forces, moment about the origin, normal Mach
and comparison errors from saved arrays. Maximum differences are 5.56e-16 in
force coefficients, 2.96e-14 in Cm, and 3.34e-16 in normal Mach. Production
bound/wake replay agrees with the saved relative velocity within 4.55e-13 m/s.

All fourteen corrected batches completed normally, three serial calls each,
with one BLAS thread, 512 MiB address-space, 15-second CPU and 25-second wall
limits. Batch work took 1.76–3.11 seconds each, 27.89 seconds combined, with
peak RSS at most 226.23 MiB. Recorded solve sections total 0.874 seconds;
these are Python diagnostics, not browser timings.

The first attempt completed one accepted solve but stopped while serializing a
NumPy boolean in the comparison report. Casting that flag to a Python boolean
fixed the diagnostic driver. The original attempt and its data are retained;
the corrected run uses a fresh plan and directory. No solver equation or
reference changed. No browser, Vite, build or background job was launched.

- [Serial driver](../../scripts/verify-sa11-uniform-polar.py), [frozen plan](../../artifacts/isae/sa11-uniform-polar-20261108-v2/plan.json), [aggregate results](../../artifacts/isae/sa11-uniform-polar-20261108-v2/analysis.json).
- [Independent checker](../../scripts/check-sa11-uniform-polar.py) and [verification receipt](../../artifacts/isae/sa11-uniform-polar-20261108-v2/verification.json).
- [PNG plot](../../artifacts/isae/sa11-uniform-polar-20261108-v2/uniform32-polar.png), [plot generator](../../scripts/plot-sa11-uniform-polar.py) and [plot provenance](../../artifacts/isae/sa11-uniform-polar-20261108-v2/plot-provenance.json).
- [First-attempt failure record](../../artifacts/isae/sa11-uniform-polar-20261108/terminal-attempt.json).

Rejected-state NPZ files contain zero placeholder `section_moment` arrays for
storage shape only; the accompanying JSON explicitly marks the moment
unavailable. The independent checker never uses these placeholders as loads.
