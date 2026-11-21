# SA-11: curved extension conversion and native core verification

2026-11-08 UTC. The new validation exporter samples the extension's original
curved geometry at every ASW mesh node. This removes the earlier source-endpoint
mismatch and permits six native AVL/production comparisons. Native lift and
induced drag are within **1%** of the selected archived coefficients. The four
zero-PG/alternative-normalization production states agree within **0.075% CL,
0.692% CDi, 4.049% total CD and 0.356% Cm**.

These are conditional diagnostics, not a primary setup correction. The original
Mach-.70 fine-grid production state still rejects local Mach at the swept tip.
SA-11 remains **163/9,184 at 5%**. Production equations, original inputs,
primary comparisons and progress history are unchanged. SA-2 remains deferred.

## Conversion and source evidence

The [authoritative index](aswing-authoritative-references.md) and its catalog
were consulted. Drela's user guide, **Distribution blocks**, specifies cubic
interpolation between ordinary stations; only doubled stations create separate
pieces. The extension's three ordinary geometry stations therefore cannot be
replaced by a single straight interval. The
[previous candidate study](isae-sa11-fixed-pg-candidate-20261108.md) correctly
retained its two extension conversions as blocked.

The new exporter uses every node from the ordinary production mesh and splits
AVL surfaces at the existing physical/property breaks. Each resulting interval
has one span strip and one chord row. Normal chord is converted to streamwise
chord using the local beam tangent; incidence and zero-lift offset are retained,
along with CLAF and physical-component identity. No original spline, joint,
section property or reference value is silently repaired.

Native AVL's `amake.f` interpolates its section coordinates and chord linearly.
Its section-specific span counts are documented in the retained user guide.
The exported source endpoints match production **exactly in the saved arrays**.
The maximum sampled leading-edge interpolation error drops from **11.82 to
2.95 micrometres** on refinement; streamwise-chord error drops from **14.49 to
3.63 micrometres**. Seven interior probes per strip measure these errors;
they are not rigorous global error bounds.

Nominal 64/128 requests contain **70/134 actual strips** after required breaks.
Native receivers are arithmetic midpoints of these one-strip intervals, while
production retains its Glauert/material-arc sampling. Maximum force-point
separation falls from **0.485 to 0.121 mm**; control-point separation falls from
0.453 to 0.113 mm. We measure those differences rather than overriding production
receivers or claiming identical discrete operators. Local circulation differences
are accordingly much larger than in the earlier identical-receiver winglet
checks: approximately 5.3% on the coarse mesh and 2.7% on the fine mesh.

## Native AVL's small core matters in this comparison

The first native run completed, but the zero-core field replay failed its
verification gate by **0.00480785 times freestream**. Its files and failed check
are retained under `artifacts/isae/sa11-curved-extension-20261108/`. The native
result was reused after exact input, command and binary checks; it was not rerun
or discarded.

AVL's `aic.f`, **VSRD**, always sets a same-component radius of
`0.0001 * transverse_strip_width`. **VORVELC** uses a quartic Leishman core.
The new [diagnostic transcription](../../scripts/avl_vorvelc_reference.py)
reproduces the saved native velocity fields exactly at binary64 precision.
Extended-precision evaluation differs from native by at most **1.80e-11**
times freestream; the corresponding zero-core formula agrees with OpenSwing's
stable kernel within **7.38e-14**. This isolates a real core-law difference
at nearly aligned bound segments, rather than a kernel arithmetic defect.

Across the six cases the core changes the velocity by up to 0.00481 times
freestream, while changing reconstructed circulation by at most **5.06e-8
relative**. This is a warning against assuming the tiny native core is always
negligible in force-field comparisons. It does **not** justify adopting it in
ASWING: Drela explicitly specifies zero mutual core for the same physical beam.
Nor does it repair the swept-tip wake peak; native local velocities still grow.

## Six predeclared comparisons

The literal .70 comparison retains the original extension, reference dimensions,
240 m/s, density 1.2256 and global PG Mach `240/340.21`. The .75 candidate uses
255 m/s and the previously declared zero-PG/reference-dimension hypothesis:
`Sref=0.9767`, `Cref=0.37874`, `Bref=2.4852`, independently supplied by the
separate cant0 file after consistent length scaling. Original geometry and
section properties remain fixed. This is not a recovered historical setup.

All comparisons use frozen body-x influences to match AVL. Production retains
its stall and local-Mach checks. Native AVL supplies inviscid loads here, so
its CD is not compared with archived total CD. Production Cm is evaluated about
the body origin, matching the selected archived moment convention.

| Setup | Alpha | Strips | Native CL error | Native CDi error | Production CL error | Production CD error | Production maximum normal Mach |
|---|---:|---:|---:|---:|---:|---:|---:|
| Literal .70 | 1° | 70 | +0.743% | −0.678% | +0.014% | −5.791% | 0.744 |
| Literal .70 | 1° | 134 | +0.447% | −0.633% | Rejected | Rejected | 1.162 |
| Conditional .75 | 0° | 70 | +0.595% | −0.929% | −0.074% | −2.620% | 0.650 |
| Conditional .75 | 0° | 134 | +0.311% | −0.817% | −0.053% | −2.463% | 0.823 |
| Conditional .75 | 1° | 70 | +0.635% | −0.980% | −0.030% | −4.049% | 0.695 |
| Conditional .75 | 1° | 134 | +0.359% | −0.851% | −0.0005% | −3.737% | 0.964 |

All six states converge in circulation and remain at least **26.72 stall
transition widths** inside the section lift limits. The sole production
rejection is a local-flow failure before stall. Its wake contribution dominates
the field, as in earlier swept-tip diagnostics.

Projecting native velocities onto the local ASW section plane also gives a
fine-grid maximum above unity: **1.377** for literal .70 and **1.110** for the
1° conditional .75 case. This is a diagnostic using the ASW section convention,
not a native AVL acceptance gate or a physical supersonic-flow prediction.
The tiny AVL core therefore does not remove this limitation. Close integrated
loading is insufficient to validate those local fields.

For the conditional production cases, refinement changes CL by at most 0.030%,
CDi by 0.054%, CD by 0.325% and Cm by 0.067%. These are two-grid observations,
not proof of a continuum limit or full-polar agreement. Native efficiency uses
its far-field definition; the analyzer separately retains values formed from
near-field CL rather than conflating those force conventions.

![Curved-extension comparison](../../artifacts/isae/sa11-curved-extension-r2-20261108/curved-extension.png)

[SVG](../../artifacts/isae/sa11-curved-extension-r2-20261108/curved-extension.svg).
The plot was visually checked and uses the application's color order.

## Verification and next action

Six unique native cases and six production calls completed serially with one
BLAS thread. One completed native case was reused in the revised verification;
five native runs were new there. Production evaluation totals 0.50 seconds,
excluding startup and source checks. Five production states computed and one
was rejected; none timed out.

Native circulation reconstructs within 3.52e-15 relative, and native body forces
within 2.23e-16. Saved production fields reconstruct exactly. The analyzer
checks **171 source pins**, including all **141 production modules**, and
**109 case artifacts**, original targets, input choices, geometry, convergence,
stall margins, validity outcomes and core formulas. Both failed and completed
evidence are retained.

Use this sampled conversion for curved ASW configurations and retain explicit
receiver/core distinctions in future AVL comparisons. The .75 extension now
supports the setup hypothesis already suggested by the baseline, including
total drag at these points, but authenticating the archived producing setup
remains necessary before changing the primary pairing. The upper-winglet .70
local-flow failure and the swept-tip field growth remain unresolved. Another
core or panel-count adjustment alone is not an evidenced repair.

Evidence: [plan](../../artifacts/isae/sa11-curved-extension-r2-20261108/plan.json),
[verified analysis](../../artifacts/isae/sa11-curved-extension-r2-20261108/analysis.json),
[export/serial driver](../../scripts/verify-sa11-curved-extension.py),
[saved-result analyzer](../../scripts/analyze-sa11-curved-extension.py).
