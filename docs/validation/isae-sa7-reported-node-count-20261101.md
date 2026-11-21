# SA-7: reported node count resolves the low-lift check, but not the full polar

2026-11-01. A bounded reconstruction of the report's mesh count brings the
full-aircraft −5° efficiency inside the existing 3% gate without changing the
equations. It does not reproduce the complete polar or authenticate the native
mesh. Production defaults and registered results are unchanged.

## Source and declared comparison

The ISAE Part 1 report, PDF page 32, says that each tandem platform used
“40 circulation nodes” with cosine clustering. It does not explicitly say
whether the count is per wing or for the complete platform. The retained
`Tandem_GAW2_L163_G05.sh` has no NODE request or saved node array. It specifies
29 angles, from −6° to 24°, omitting 1° and 22°.

The [pilot plan](../../artifacts/isae/sa7-reported-node-count-20261101/plan.json)
tests the direct total/per-wing and geometric-node/circulation-variable readings:
19, 20, 39 and 40 requested intervals per wing. Mandatory attachment stations
remain enforced. In this model they add a center node to the odd-count grids,
so 19/20 requests both produce 20 actual strips per wing, with different
positions; 39/40 requests both produce 40 strips per wing.

All runs retain the published strength 40, width 0.05, original section data,
current influence geometry, zero PG Mach and the documented inter-surface core.
No spacing, core factor or section parameter is fitted. The two predetermined
angles are −5° and 0°; all seven native fields are checked at each angle. A
candidate advances only if it gains checks without losses relative to the
retained N128 control.

| Requested intervals per wing | Actual strips per wing | −5° efficiency error | Pilot checks |
|---:|---:|---:|---:|
| 19 | 20 | −0.6402% | 14/14 |
| 20 | 20 | +0.4191% | 14/14 |
| 39 | 40 | +3.3554% | 13/14 |
| 40 | 40 | +3.5392% | 13/14 |
| Retained 128 control | 128 | +3.5400% | 13/14 |

The smaller meshes use interval length, rather than chord/4, for the core of
12 source strips on each wing. Their maximum interval/chord-quarter ratios
are 1.955 and 1.877. At 39/40 requested intervals every strip is chord-limited;
the ratios are below one. Thus changing the count also changes the documented
regularization of the **near field between distinct physical surfaces**. This
is not the rejected change to Trefftz reporting. The independent field audit
includes those source-dependent cores and preserves zero core on each own
physical surface. Mesh quadrature changes as well; this comparison does not
isolate their separate contributions.

## Full polar and operating-point continuation

Both qualifying counts were extended to all 29 archived angles. The first
comparison starts each angle independently. A second follows exactly the
script's angle order, using the preceding circulation as the next Newton seed.
No intermediate angles or target-dependent branch selection are introduced.

| Requested intervals per wing | Independent starts | Previous-state seeds | Failed-scalar error, median / maximum |
|---:|---:|---:|---:|
| 19 | 195/203 | 195/203 | 8.21% / 33.73% |
| 20 | 199/203 | 199/203 | 7.36% / 11.49% |

Every previous-state seed is accepted without a cold fallback. The maximum
cold/seeded circulation difference is 6.60e−12 in file circulation units.
Initialization therefore does not explain the observed differences on these
two meshes. This does not establish uniqueness or the native solver's branch.

For 20 requested intervals, **all lift, total drag, CL, CD and CM checks pass**.
The four remaining checks are:

| Angle | Quantity | Error |
|---:|---|---:|
| 18° | CDi | −11.0964% |
| 18° | Efficiency | +11.4935% |
| 23° | CDi | −3.2143% |
| 24° | CDi | −3.6322% |

The 19-request grid also fails CDi/efficiency at 17° and 18°, and CDi at
20°, 21°, 23° and 24°. Its worst CDi error is +33.73% at 18°.

These are finite-mesh diagnostics, not mesh-converged acceptance. Earlier
64/128/256 cosine checks retain the 3.54% low-lift error. A possible native
total-count interpretation can explain that scalar without fixing the whole
polar. The native node positions and circulation representation remain unknown.
The next useful numerical question is the coarse-mesh induced-drag behavior
near stall, including its circulation representation and wake quadrature.

## Verification and resource limits

Independent regularized Biot–Savart integration checks force- and control-point
velocities, with 16/32-point quadrature refinement. Independent calculations
also check the nonlinear leakage residual, complete section forces/moments,
and the Trefftz scalar-product quadratic form. Native fields are scored against
their original text tokens using exact rational arithmetic.

Across the pilot, full cold polar and seeded polar, 2,480 velocity vectors are
checked, including reused states. Maximum normalized field error is 7.99e−15;
maximum normalized residual is 5.67e−13. Reconstructed moments agree within
8.90e−16 in coefficient units. All computed local normal Mach numbers are
subsonic.

The work makes 118 new small physical calls: 8 pilot, 54 full-polar extension,
and 56 seeded calls. Six stored states are reused across the extensions.
Each stage runs in one foreground process with one BLAS thread; no pool,
browser, Vite server or build is launched. The three numerical stages take
7.40, 35.84 and 3.10 seconds respectively, including their capture/hash work.
All process handles have terminal receipts.

The registered SA-7 family remains **395/812**, including **395/406** in the
registered full-aircraft scope. The earlier strength-20 fine-mesh result stays
separate at **404/406**. The new 199/203 diagnostic uses strength 40 and one
coarse mesh; these counts have different scopes and must not be combined.
The current fore-only pairing problem is unchanged. The full project remains
incomplete.

[Pilot verification](../../artifacts/isae/sa7-reported-node-count-20261101/analysis.json),
[full-polar results](../../artifacts/isae/sa7-reported-node-count-20261101/full/analysis.json),
[seeded results](../../artifacts/isae/sa7-reported-node-count-20261101/warm/analysis.json),
[receipt](../../artifacts/isae/sa7-reported-node-count-20261101/receipt.json).
