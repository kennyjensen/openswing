# SA-10 stall and junction follow-up

Update: the [moment-output correction](isae-sa10-moment-origin-20261031.md)
now adopts the published body-origin convention for native CM and exposes it
explicitly in production. The strength-20 scope below therefore gives
**1,088/1,134** under the corrected comparison; its physical results and
unverified stall-strength qualification are unchanged. Older origin-hypothesis
wording below is retained as investigation history.

2026-10-31. The five-model pilot, complete three-model comparison
and junction follow-up have finished. Registered acceptance remains
1,083/2,268; no physical inputs, solver equations or validity gates change.

Follow-up: the [Louvered Fourier/refinement audit](isae-sa10-louvered-basis-20261031.md)
shows that the passing 200-interval drag results below do not establish mesh
convergence. Louvered has nonplanar tips; “planar” in the retained artifact
paths was an inaccurate scope label, not a change to its geometry.

## Complete three-model comparison

All 162 states complete: three literal models, 27 archived rows each,
including the repeated 12° row, on both registered 100/200-interval meshes.
This is 151 new solves and 11 exact pinned reuses.

| Model | Registered strength 40 | Strength 20 | Strength 20, separate origin-CM diagnostic |
|---|---:|---:|---:|
| Wing alone | 246/378 | 324/378 | **376/378** |
| Wing extension | 174/378 | 322/378 | **374/378** |
| Louvered | 174/378 | 286/378 | **338/378** |
| Total | 594/1,134 | **932/1,134** | **1,088/1,134** |

Strength 20 passes **all 162 CL and all 162 CDi checks**. All 162 pitching
moments pass when the computed wrench is translated to the origin. The
input Xmom=0.05 m remains the acceptance reference; origin translation is
reported separately. Neither the native stall coefficient nor the native
moment convention is authenticated. In particular, the ISAE report's
equation (13) explicitly states KS=40 and width 0.05. These results therefore
identify a consistent reproduction hypothesis, not a supported default change.

![Complete three-model comparison](../../artifacts/isae/sa10-stall-junction-20261031/full-planar/comparison.svg)

With the origin-moment diagnostic, 46 checks remain outside tolerance:

- 36 louvered drag/CD checks on the **100-interval mesh only**, covering
  18 archived rows from 9° through 25°, including the duplicate 12°.
  CD errors are 3.28–5.80% high, median 4.94%. Every 200-interval drag/CD
  check passes; the coarse failures remain counted.
- Four zero-incidence dimensional-lift checks: the extension and louvered
  models retain approximately −5.69e−6 N and −5.45e−6 N on the fine mesh,
  while the archive prints zero. Their CL values pass their own original
  absolute tolerances; force and coefficient tolerances are not interchanged.
- Six zero-incidence efficiency checks. Small nonzero circulation from the
  asymmetric stall limits gives finite efficiency, whereas the native output
  is zero. The strict zero-reference policy remains unchanged.

The fine-mesh, origin-moment scope passes **562/567**: wing alone 188/189,
extension 187/189, louvered 187/189. This does not replace the complete
two-mesh score. Independent scalar reconstruction checks all 24,408 captured
lifting strips, with maximum force/moment/wrench discrepancies
5.15e−18 / 1.70e−18 / 1.15e−15 and local equation defect 4.62e−13.

## Tip-sail pilot

The fixed-strength-20 pilot covers all five runnable literal models at
10°, 20° and 25° on the finest registered meshes. It gives **76/105**,
versus 41/105 at strength 40. The separate origin-moment diagnostic gives
89/105. Thirteen states compute; two remain physically rejected.

For TS60/40/80 at 10°, induced drag is 7.72% high and efficiency 7.59% low.
Its 20° state passes all outputs under the origin-moment diagnostic. At 25°,
it is rejected at local Mach **1.005745**. TS80/60/40 passes its 10° and 20°
samples under the same moment diagnostic, but reaches Mach **1.113987** at
25°. These are sampled results; no complete tip-sail polar claim is made.

## Verified junction failure

The registered `TS_80_60_40`, 25°, 128-interval state is reproduced with the
published stall strength 40. Its circulation residual is **2.20e−14**, but
the local section-normal Mach number reaches **1.0867087** on beam 2,
t=0.559001329. It is rejected as physically outside the subsonic model.
This is a converged circulation solution with invalid local flow, rather
than a circulation solve that failed to terminate.

The worst force point lies **6.95 micrometres** from the beam's root trailing
ray. That ray alone contributes 624.12 m/s; other rays partly cancel it.
The resulting section-normal speed is 369.71 m/s, versus the input sound
speed 340.21 m/s. An independent 60-digit Biot–Savart implementation
reconstructs **12 peak force-point velocity vectors across all three rejected
states** within **2.00e−10 of flight speed** and reproduces their peak Mach
numbers. The independent local stall-equation defect is at most 4.49e−14.
No invalid coefficient output is accepted from this diagnostic.

Two additional cold solves measure the original strength-40 case under
refinement. The 64-interval force and moment reproduce the registered result
within 2.95e−14 scaled error.

| Intervals per beam | Peak local Mach | Distance to closest wake ray | Status |
|---:|---:|---:|---|
| 32 | 0.301416 | 111.17 micrometres | Computed |
| 64 | 0.555625 | 27.80 micrometres | Computed |
| 128 | 1.086709 | 6.95 micrometres | Rejected |

Every circulation solve converges. Refinement strengthens the singular local
flow; a converged or finer discretization is not evidence of local physical
validity. No successful coarse state replaces the failed fine state.

![Junction refinement and velocity components](../../artifacts/isae/sa10-stall-junction-20261031/junction-comparison.svg)

All seven beams explicitly share physical index 1. Drela's user guide says
that matching physical indices require zero mutual vortex cores, and warns
that a trailing leg close to another beam's control points can produce
serious numerical noise. The ISAE report's SA-10 discussion also describes
local lift divergences at the three-tip junction and missing circulation
continuity there. These sources and the independent calculation support
retaining the local-flow rejection. Relabeling physical indices or enlarging
the cores to obtain a pass would change the supplied model.

## Source audit correction

All six SA-10 shell drivers toggle K/F **before their first XX execution**.
The preceding `+` commands insert operating points; the guide specifies that
XX converges the complete stack. Earlier SA-10 prose incorrectly described
the toggle as occurring after the final solve; that sentence is corrected.
The guide's displayed F=T initial setting supports current influences after
one toggle. Producing executable defaults and saved settings remain unavailable.

The blocked `TS_60_45_30` input still refers to t=+0.559 on a negative-t beam
and t=−0.559 on its positive-t counterpart. The existing explicit reconstruction
changes only the two opposite beam references. Its geometry and archived
targets are not silently substituted into the registered comparison.

## Recorder and process accounting

The first diagnostic recorder exceeded its 64 MiB derivative-cache budget
on seven seven-beam requests before solving circulation. Those attempts are
preserved as instrumentation failures. A capture-only observer retries them
without duplicate cache copies. Its valid-state parity control has exactly
identical captured fields and reference checks. Physical convergence and
Mach checks remain active. All worker processes terminate successfully;
rejections are recorded outcomes, not worker crashes.

There are 175 new evaluator invocations: seven recorder-budget failures,
165 valid solves and three converged-but-invalid local-Mach outcomes.
This includes the parity control and two coarse refinement solves. Exact
pilot and full-polar reuses are recorded separately; overlapping scopes
are not counted as independent new solves.

Artifacts:

- [Literal command and index audit](../../artifacts/isae/sa10-stall-junction-20261031/source-audit.json)
- [Independent rejected-junction calculation](../../artifacts/isae/sa10-stall-junction-20261031/junction-audit.json)
- [Pilot plan](../../artifacts/isae/sa10-stall-junction-20261031/plan.json)
- [Completed pilot comparison](../../artifacts/isae/sa10-stall-junction-20261031/report.md)
- [Complete three-model comparison](../../artifacts/isae/sa10-stall-junction-20261031/full-planar/report.md)
- [Root-refinement audit](../../artifacts/isae/sa10-stall-junction-20261031/refinement/analysis.json)

The SA-6 derivative, SA-7 low-lift efficiency and SA-8 drag/setup differences
remain open. SA-9 is absent upstream. The full project goal remains incomplete.
