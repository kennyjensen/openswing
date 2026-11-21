# AE-2: conditional low-aspect-ratio wing pilot

All six independent cold solves complete with the unchanged literal uncoupled
wing. The prior initial wall-contact rejection is no longer reproduced with the
current steady wall-root implementation. All four displacement mesh checks pass
the predeclared 1% limit; the largest change is **0.0221242%**. This establishes
numerical consistency for these two conditions, not experimental validation.

On the finest mesh, OpenSwing predicts **4.210403 mm** at the selected 1°,
9.05751146 m/s experimental point, versus the raw video-derived **1.581596 mm**
(+166.212%). At the separate 5°, 10 m/s archive-control condition it predicts
**26.122996 mm**, versus archived ASWING **25.820000 mm** (+1.17349%).
Agreement with the archived calculation does not resolve the measured difference.

| Reference | Nominal / actual elements | OpenSwing deflection (mm) | Reference (mm) | Difference (mm) | Native solve (s) |
|---|---:|---:|---:|---:|---:|
| experimental-point | 40 / 41 | 4.209873 | 1.581596 | +2.628276 | 0.996 |
| experimental-point | 80 / 81 | 4.210462 | 1.581596 | +2.628866 | 1.583 |
| experimental-point | 160 / 161 | 4.210403 | 1.581596 | +2.628807 | 2.452 |
| archive-control | 40 / 41 | 26.115690 | 25.820000 | +0.295690 | 1.014 |
| archive-control | 80 / 81 | 26.121469 | 25.820000 | +0.301469 | 1.544 |
| archive-control | 160 / 161 | 26.122996 | 25.820000 | +0.302996 | 2.725 |

The experimental point and archive control use different incidences and speeds;
they are separate comparisons. The experimental ordinate is the raw
`ALPHA_1_W` observation, CSV line 4, columns 3–4. No interpolation, zero shift,
averaging with the strain-derived series, or simultaneous twist target is used.
The archive control is line 14 of `[03_90]_A5.txt`, mapped to commanded indicated
speed 10 m/s by the operating script. Its printed `t=11` is a stack index, and
sensor speed 10.0115 m/s is not the command. Original NaN initial rows remain missing.

| Condition | Nominal mesh pair | Absolute change / finer displacement | 1% gate |
|---|---:|---:|---|
| experimental-point | 40 → 80 | 0.013993% | Pass |
| experimental-point | 80 → 160 | 0.001398% | Pass |
| archive-control | 40 → 80 | 0.022124% | Pass |
| archive-control | 80 → 160 | 0.005843% | Pass |

All six cases independently start from the public cold path, with no equilibrium
reuse. Each returned state is restored into a fresh network and checked once
against the full equations. Maximum fresh residual is 9.4843e-13 against 1e-8;
maximum relative force and moment imbalances are 2.7126e-11 and 5.8207e-10
against 1e-7. Root position and orientation satisfy 1e-10. These are equation and
mesh checks, not a continuum error bound, stability test or reference agreement gate.
The six native solves take 0.996–2.725 seconds each, totaling 10.314 seconds;
the sequential batch including startup, checks and file writing takes 42.242 seconds.
There are 876 public-network residual evaluations and six fresh checks, with no
timeouts or retries. All children and their supervisor were reaped.

The [independent saved-results audit](isae-ae2-pilot-audit.json) passes 869/869
checks, separately reconstructing residuals, global balances, sensor placement,
source references, all four mesh ratios and the execution accounting.

One actual offline browser solve of the nominal-160 archive control passes
1,057 checks. It takes **4.13 seconds after 29.32 seconds of runtime startup**;
the complete browser check takes 42.02 seconds. Startup is measured from harness
start to enabled Solve, including source checks and browser initialization. All
24,659 physical numeric fields
match the native result within 2e-8 absolute plus 2e-8 relative tolerance; the
largest absolute difference is 8.74e-12. Its full residual is 8.78e-14. Only
execution counters are excluded; explicit mesh settings and physical state
remain compared. This is one selected workflow check, not a browser sweep.

The [importable project](../../examples/isae-ae2-uncoupled-project.json) contains
both editable inputs and the actual computed browser solution. Open it through
the app's project import, then open the saved solution to inspect the result
without solving again. The tested import/export roundtrip preserves both project
and result bytes and makes zero additional solve requests. The
[browser report](isae-ae2-pilot-browser.json) records current source/build hashes,
conditions, timing and progress. The [fitted viewport](isae-ae2-pilot-browser.png)
visibly shows the vertical wing and wall using Canvas2D; it does not establish
WebGL rendering. No hosted deployment or new production change is claimed. The separate
[independent saved-browser audit](isae-ae2-pilot-browser-audit.json) passes
1,283 checks. Its two initial audit-only bookkeeping failures are retained;
the corrected checks compare the solve snapshot with its matching event prefix
and verify the later project-restore events separately. No physical case was rerun.

The literal vertical file has a 0.558 m span, 0.14 m chord, leading-edge reference
axis, a full root clamp at physical z=0, and one midchord tip sensor. Incidence
enters as beta. The compared displacement is minus that sensor's Earth Y
coordinate, measured from jig Y=0, with no extra gravity-baseline subtraction.
The diagnostic total tip angle is requested beta minus sensor heading. At the
archive control the fine result is 5.578445° versus 5.572223° archived; this is not
a comparison to a same-speed experimental twist observation. Fine sensor speed
and local beta differ from the archive by −0.041897 m/s and −0.152123°.

The declared reconstruction uses density 1.23 kg/m³, true speed equal to the
listed command, Mach U/340.21, gravity 9.81 m/s² along Earth −z, identity body/Earth
pose, updated influence matrices, pointwise circulation, zero F1, and an ideal
image wall with normal +z. Historical density, speed conversion, Mach flag,
influence choice, mesh, producing executable and complete startup state are
unknown. The 40/80/160 cosine requests yield 41/81/161 elements because the
literal interior material station is retained. No material property, production
default or numerical tolerance was changed.

The primary experiment and literal model are not yet proved to represent the
same specimen. In particular, literal uncoupled GJ=1 and EInn=2.5 N m² differ
from the secondary report's 1.2 and 18499 N m². Primary laminate plate rigidities
have different units and cannot be substituted directly. The finite experimental
pedestal cover also differs from an infinite ideal wall. Hollow/video and
solid/strain-derived points are distinct measurement methods; their differences
are not an uncertainty interval. These qualifications are retained in the
[source review](isae-ae2-pilot-sources.md), based on Dunn's primary thesis and the
pinned ISAE files. Both selected conditions are below the primary uncoupled
experimental flutter boundary, without certifying stability of this literal model.

The previous pre-residual wall failure remains in
[the retained ground-backtracking evidence](ground-backtracking.json).
The source-only readiness checks used six constructor/clearance requests and
no physics; their beta-5 Mach-zero setup is distinct from this pilot's declared
Mach U/340.21. The source review passes 701 checks and the final pilot plan
review passes 226. A reducer reporting correction before launch distinguishes
attempted children lacking reports from cases never launched; the first version
is retained. It did not change any physical input or solve.

The next comparison should map the other incidences and laminate variants to
their separate raw video and strain-derived observations, while preserving the
literal/report property alternatives. Recovering physical specimen properties,
speed/atmosphere, datum and measurement uncertainty remains necessary for an
experimental pass. This small pilot is supplemental evidence: AE-2's broader
comparison stays pending, and coverage remains **18 partial / 23 pending /
0 fully validated**. The user priority remains ISAE; Daedalus matching is deferred.

The [six-row CSV](isae-ae2-pilot.csv), [saved comparison](isae-ae2-pilot.json),
[frozen plan](isae-ae2-pilot-plan.json), [execution summary](isae-ae2-pilot-summary.json)
and [source mappings](isae-ae2-pilot-sources.json) retain the inputs and results.

The [raw evidence archive](isae-ae2-pilot-20261025-evidence.zip) retains the six
raw states, fresh residual arrays, exact source snapshot, plans, browser project,
reductions, audits and preparation history, alongside the saved Pazy observable
study. Its [integrity receipt](isae-ae2-pilot-archive.json) records CRC and extracted
hash verification. Full primary theses, reports and paper text remain local-only
source dependencies with hashes and primary links; they are not redistributed
in this archive. Previous raw archives remain immutable dependencies.
