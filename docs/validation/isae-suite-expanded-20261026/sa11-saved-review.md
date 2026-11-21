# SA11 saved-result audit

Read-only audit of 656 completed SA11 jobs. No production imports, solves, reruns, repository edits or gate changes.

- 47 computed: all numerically valid; **0/47 reference matches**, **0/329 passing field comparisons** at original printed precision.
- 281 errors: all `AnalysisError`, all the local section-normal Mach >= 1 guard; 281 distinct messages differ in numeric details.
- 328 unsupported: all `ARCHIVED_NORMALIZATION_CONFLICT` (0.75/0.78); zero physical calls.

| Table | Nominal grid | Computed | Error | Unsupported | Computed rows (zero-based) |
|---|---:|---:|---:|---:|---|
| wing_alone_Ma_0_70 | 64 | 14 | 27 | 0 | 0–13 |
| wing_alone_Ma_0_70 | 128 | 0 | 41 | 0 | — |
| wing_alone_Ma_0_75 | 64 | 0 | 0 | 41 | — |
| wing_alone_Ma_0_75 | 128 | 0 | 0 | 41 | — |
| wing_alone_Ma_0_78 | 64 | 0 | 0 | 41 | — |
| wing_alone_Ma_0_78 | 128 | 0 | 0 | 41 | — |
| wing_alone_Ma_0_80 | 64 | 7 | 34 | 0 | 0–6 |
| wing_alone_Ma_0_80 | 128 | 0 | 41 | 0 | — |
| wing_extension_Ma_0_70 | 64 | 16 | 25 | 0 | 0–15 |
| wing_extension_Ma_0_70 | 128 | 2 | 39 | 0 | 0–1 |
| wing_extension_Ma_0_75 | 64 | 0 | 0 | 41 | — |
| wing_extension_Ma_0_75 | 128 | 0 | 0 | 41 | — |
| wing_extension_Ma_0_78 | 64 | 0 | 0 | 41 | — |
| wing_extension_Ma_0_78 | 128 | 0 | 0 | 41 | — |
| wing_extension_Ma_0_80 | 64 | 8 | 33 | 0 | 0–7 |
| wing_extension_Ma_0_80 | 128 | 0 | 41 | 0 | — |

The guard is in frozen `openswing/aero.py:559–575`: it divides force-point normal relative speed by atmospheric sound speed and rejects `M_perp >= 1` before the local section-moment square root. It occurs after circulation residual acceptance; the saved errors are not circulation-nonconvergence messages. The caught exception is saved as type/string, with empty numerical/reference checks; process exit 0 therefore does not mean the physical calculation succeeded.

Representative earliest failures for each executable table/grid:

| Job | M_perp | t | Normal speed |
|---|---:|---:|---:|
| SA-11:wing_alone_Ma_0_70:row014:n64 | 1.015248 | -1.242226 | 345.3974 |
| SA-11:wing_alone_Ma_0_70:row000:n128 | 1.000849 | -1.242506 | 340.499 |
| SA-11:wing_alone_Ma_0_80:row007:n64 | 1.026227 | -1.242226 | 349.1326 |
| SA-11:wing_alone_Ma_0_80:row000:n128 | 1.246495 | -1.242506 | 424.0701 |
| SA-11:wing_extension_Ma_0_70:row016:n64 | 1.009711 | -1.317807 | 343.5138 |
| SA-11:wing_extension_Ma_0_70:row002:n128 | 1.050334 | 1.318102 | 357.3342 |
| SA-11:wing_extension_Ma_0_80:row008:n64 | 1.007129 | -1.317807 | 342.6354 |
| SA-11:wing_extension_Ma_0_80:row000:n128 | 1.18086 | 1.318102 | 401.7404 |

All 281 messages report sound speed 340.21; maximum local Mach ranges from 1.000849 to 4.652922. These are rounded saved values, not recomputed diagnostics.

The original request/model/table/driver pin checks and literal alpha/speed/beta/output-token checks show 0 inconsistencies. Nominal 64/128 panels differ from actual meshes because mandatory nodes are added. Only extension 0.70 rows 0 and 1 computed on both grids; this is insufficient for a family-wide mesh-convergence claim.

The literal model supplies density 1.2256, sound speed 340.21, and Sref 0.9329. The runnable tables use speeds 240 and 272, so dynamic PG Mach is respectively 0.705446635901355 and 0.7995061873548691. Original drivers contain no NODE grid declaration; 0.70/0.80 drivers contain KK/MM. Historical parser/startup state is unresolved. No literal input-mapping mismatch was found, but current mesh/interpolation/influence geometry, atmosphere and cold rigid sequence are reconstruction choices rather than proof of historical setup.

Four 0.75/0.78 tables imply area about 97.67 at literal density, compared with literal Sref 0.9329; this preserved conflict accounts for all 328 unsupported jobs. Baseline 0.70 row23 drag and row37 lift also lie outside strict literal qS intervals.

Actionable next step: recover historical PG/K/F, KK/MM and mesh/influence/stall settings from original source/documents or archived startup artifacts. Inspect the near-tip force-point/local-flow mechanism with the guard intact; do not fit inputs, rescale outputs or relax precision. All saved computed fields fail their reference gates, so the present suite does not establish SA11 validation.

`audit.json` contains per-job guard details, comparisons, table/grid groups and source checks. `pins.json` pins every inspected request/result/log/original/static-source file. `audit_saved_sa11.py` is the standard-library-only audit implementation.

Saved error maxima are localized next to the source-model endpoints (scaled `t` half-span 1.2426 baseline, 1.3182 extension). All 281 maxima are on beam 1. Stations below are the rounded values retained in the error strings; endpoint distances are approximate.

| Variant | Grid | Errors / attempted | Maximum station(s) | Distance to nearest tip | Fraction of half-span |
|---|---:|---:|---|---:|---:|
| wing_alone | 64 | 61/82 (74.39%) | -1.242226 | 0.000374 | 0.03010% |
| wing_alone | 128 | 82/82 (100.00%) | -1.242506 | 9.4e-05 | 0.00756% |
| wing_extension | 64 | 58/82 (70.73%) | -1.317807 | 0.000393 | 0.02981% |
| wing_extension | 128 | 80/82 (97.56%) | 1.318102 | 9.8e-05 | 0.00743% |

Across executable tables: n64 errors 119/164 (72.56%); n128 errors 162/164 (98.78%). The tip distance decreases about fourfold on refinement; all 119 rows that errored on both grids report a larger maximum local Mach on n128. This supports examining the discrete tip sampling mechanism.

The guard establishes local-normal Mach >= 1 in this discrete lifting-line solution. It does not prove physical transonic flow: increasingly near-tip force-point velocities under grid refinement can reflect circulation/geometry discretization sensitivity. Archived physical flow cannot be classified from these saved exceptions alone.

Concrete next diagnostic: Read-only source audit of tip circulation representation and geometry sampling: compare force-point versus collocation locations, endpoint spacing and mandatory-node insertion, swept bound-vortex/self-influence and wake treatment, section-normal projection, and PG/current-geometry transforms. Trace how these definitions produce the saved endpoint-localized maxima, and compare the same mechanism with other swept-line finer-grid guard failures (SA14 context supplied by owner, outside this SA11 audit). Recover historical PG/K/F, KK/MM, mesh/influence, stall/continuation and startup settings from original sources in parallel. Keep the Mach guard, original inputs and precision gates fixed; do not clamp Mach or fit parameters. No fresh solve is required for this proposed source diagnostic.

`enrich_saved_geometry.py` adds this localization to the base audit using saved files only.
