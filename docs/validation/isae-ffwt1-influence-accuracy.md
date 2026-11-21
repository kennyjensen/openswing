# FFWT-1 influence accuracy and geometry-specific reference roots

The two strict pointwise replay failures in the
[connected-wing study](isae-ffwt1-connected-circulation.md) are primarily
caused by tiny differences between the stored native and independently
reconstructed geometries. Higher precision preserves those differences.
Two new independently solved states satisfy their own equations and closely
match the native forces. The original prescribed-circulation failures remain
recorded; they have not been reclassified as passes.

A separate prototype reduces cancellation error when evaluating shared wake
lines. It preserves the physical vortex equations and passes the declared
accuracy controls. It is not yet integrated into the production solver.
Production source, defaults and the browser release are unchanged; ISAE
coverage remains **17 partial / 24 pending / 0 fully validated**.

## Distinguishing geometry from evaluation arithmetic

The audit keeps each saved circulation vector unchanged. It evaluates four
selected panels on both stored geometry paths at 80 decimal digits, converting
every binary64 input exactly. Crossed geometry/frame evaluations separate the
jig contribution from the frame contribution. No new root is solved in this
part of the study.

At the two disputed samples, the normalized residuals are:

| Saved state and sample | Native rounded geometry, MP80 | Independent rounded geometry, MP80 | Change due to geometry/frame path |
| --- | ---: | ---: | ---: |
| Fine pointwise, panel 202 | +8.52933e−14 | +2.49875e−12 | +2.41346e−12 |
| Finer pointwise, panel 401 | −3.93232e−13 | +1.51568e−11 | +1.55500e−11 |

The differences come almost entirely from the jig geometry. The frame-only
effect is approximately 8.35e−18 at the fine sample and zero at the finer
sample. All four selected native-geometry evaluations satisfy 1e−12; two of
the four independent-geometry evaluations fail it. This is a sampled-panel
diagnosis, not a full-vector high-precision certificate.

The local operator is sensitive enough near the junctions that geometries
agreeing within the earlier geometric comparison bounds still define
measurably different discrete equations at this strict residual scale. The
preceding study's result cannot be explained solely as summation error.

## Independent roots on the independent geometry

Two new solves use the independently reconstructed fine and finer geometries
and their previously built independent influence tensors. Each starts from
its own linear circulation solution. The native circulation is first decoded
after the independent nonlinear solve and its strict acceptance check.

Both solves use the unchanged independent reference algorithm and require a
full normalized residual maximum of 1e−12. Neither needs the reference
algorithm's bounded terminal correction. The same predeclared four panels
are then evaluated at MP80 with the new circulation vectors.

| Independent solve | Full binary64 residual maximum | Maximum selected MP80 residual on its own geometry | Maximum circulation difference from native, m²/s | Absolute lift difference, N |
| --- | ---: | ---: | ---: | ---: |
| Fine, 364 panels | 6.71049e−13 | 3.00807e−13 | 4.90052e−13 | 1.59872e−13 |
| Finer, 724 panels | 6.95502e−13 | 6.40271e−14 | 5.62217e−13 | 9.20153e−13 |

All sixteen declared field/load comparisons pass. The two-solves run,
including recording and selected MP checks, takes 5.754 seconds; this is not
a browser or coupled-equilibrium benchmark.

Applying these new circulation vectors to the native geometry produces
opposite-direction failures at the previously disputed samples. That is
consistent with distinct rounded discrete systems, rather than one universal
circulation vector satisfying both to 1e−12. The new full binary64 worst
panels are 116 and 215; they were not added to the predeclared MP sample set.
No full-vector MP certificate is claimed.

## Combining shared wake lines before velocity evaluation

Adjacent horseshoes have opposing wake legs at a common endpoint. The
prototype first sums their signed circulation strengths, then multiplies
that sum by the wake influence. Finite bound segments retain their separate
ownership and exclusion rules. This is an algebraic rearrangement, not a
change to cores, forces, circulation continuity or the physical model.

Rays merge only when their endpoint coordinates and effective core values
for every receiver are exactly equal, with a common wake direction,
Prandtl–Glauert mapping and image construction. No distance tolerance merges
nearby endpoints. The own-bound exclusion removes only the real finite bound
segment; image bounds and both wake legs remain. Geometry derivatives must
retain the original endpoint and core dependencies.

Fifteen control groups pass 66 assertions covering nonuniform and branched
circulation, orientation, unequal cores, own-bound exclusion, images,
compressibility, translation, rotation, unit scaling, circulation derivative
columns and an independent kernel reference.

The eight saved geometry/panel targets are also compared with their matching
MP80 evaluation. The accuracy limits were declared beforehand: maximum
velocity-component error 2e−12 m/s and normalized residual evaluation error
1e−13. These are evaluation-error limits, separate from the root residual
requirement.

| Evaluation method | Targets meeting both accuracy limits |
| --- | ---: |
| Expanded horseshoes, ordinary accumulation | 4 / 8 |
| Expanded horseshoes, compensated accumulation | 6 / 8 |
| Shared-ray factorization | 8 / 8 |

The factored method's largest velocity error is 6.17e−15 m/s and its largest
normalized residual evaluation error is 2.81e−16. A separate review reproduces
193 saved scalar/accounting checks. These selected results show an accuracy
benefit; they do not establish a universal error bound or a speedup. All three
methods still retain the two independent-geometry equation failures for the
old native circulation vectors.

## Remaining work

The independently solved pointwise controls now support force agreement
without requiring both implementations to round geometry identically.
Physical validation is still incomplete: connected-series local defects near
the hinges, general surface grouping, the experimental fixture and archived
configuration, flexible response, updated influences and dynamics remain open.

The factored evaluator needs general solver, cache and derivative integration,
memory/performance checks, and native/browser regression coverage before
production use. Its present tests cover values and circulation derivatives,
not derivatives obtained by treating independently moving endpoints as one
geometric degree of freedom.

The [recorded summary](isae-ffwt1-influence-accuracy.json),
[selected evidence archive](isae-ffwt1-influence-accuracy-evidence.zip) and
[verification receipt](isae-ffwt1-influence-accuracy-evidence.json) preserve
both the original failures and the new controls. Archive checks verify saved
bytes; they do not claim additional scientific runs or a browser build.
