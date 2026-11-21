# SA-10 Louvered: Fourier circulation and bend refinement

Later results: the [origin-moment correction](isae-sa10-moment-origin-20261031.md)
updates registered SA-10 to **1,256/2,268**. The separate
[tip-sail Fourier comparison](isae-sa10-tip-fourier-20261031.md) also finds
that the tested mode counts do not resolve the multi-beam junction failures.
The counts and moment-reference qualification below describe the earlier run.

The later [drag-reporting and component audit](isae-sa10-drag-reporting-20261101.md)
recovers all remaining drag/CD checks in a saved-field reporting diagnostic.
It verifies the bound/wake contributions independently, but does not justify
changing production's integrated force or establish native reporting parity.

2026-10-31. The remaining coarse-mesh drag error is not resolved by the
published Fourier representation. Further refinement exposes invalid local
velocities beside the sharp bend, so the passing 200-interval drag checks
do **not** establish mesh convergence or native ASWING reproduction.

Follow-up: the [corner-interval audit](isae-sa6-sa10-corner-kinematics-20261031.md)
rules out adding an omitted zero-length horseshoe as a correction: its
complete bound/wake field cancels. A continuous sharp bound line still has
a singular neighboring-filament velocity.

This follows the [complete three-model comparison](isae-sa10-stall-junction-20261031.md).
Its historical artifact directory is named `full-planar`, but Louvered is
nonplanar: the literal file bends each outer tip upward by 45° at |t| = 0.559.

## Controlled comparison

The experiment predeclares incidence 5°, 15° and 25°, 20/40 Fourier modes on
100/200 requested intervals, and a pointwise 400-interval refinement.
The theory's equations (63), (150) and (201) supply the sine basis and
weighted residual; the ISAE report's numerical-convergence section discusses
20–40 circulation variables. These are sensitivity choices, not recovered
native mode counts. The fixed strength-20 hypothesis remains unverified;
the report specifies strength 40. All literal geometry, section properties,
current influences, moment reference, reference outputs and validity checks
are retained. No production or registered acceptance setting changes.

Fifteen new requests finish: thirteen valid states and two local-Mach
rejections. Six exact saved pointwise states supply the controls. Three
additional replays capture the rejected fields and reproduce the valid
400-interval control exactly. All processes terminate and are reaped.

| Representation | CD error at 5° | CD error at 15° | CD error at 25° |
|---|---:|---:|---:|
| Pointwise, 100 intervals | +0.980% | +5.801% | +3.485% |
| 20 modes, 100 intervals | +1.396% | +6.203% | +2.523% |
| 40 modes, 100 intervals | +1.242% | +6.108% | +3.132% |
| Pointwise, 200 intervals | +0.966% | +2.815% | +1.517% |
| 20 modes, 200 intervals | +1.389% | +3.250% | +0.525% |
| 40 modes, 200 intervals | +1.267% | +3.168% | +1.068% |
| Pointwise, 400 intervals | −0.803% | Rejected | Rejected |

The 20-mode coarse result recovers the two drag/CD checks at 25°, but both
mode choices lose the two passing 15° drag/CD checks on the 200-interval mesh.
Neither mode count supplies a general correction. Under the separate
origin-CM diagnostic, the sampled 200-interval pointwise scope is 21/21;
each Fourier scope is 19/21. These are diagnostic counts, not registered gains.

![Louvered drag errors and local Mach under refinement](../../artifacts/isae/sa10-louvered-basis-20261031/comparison.svg)

## Localized force and velocity evidence

At 15°, increasing the pointwise request from 100 to 200 reduces near-field
CDi by 0.00266270, while profile CD increases by 0.00019294. Thus the net
total-CD change, −0.00246976, comes predominantly from the near-field force.
The corresponding Trefftz CDi changes only from 0.03700162 to 0.03697782.

| Incidence | Peak normal Mach, 100 | 200 | 400 |
|---|---:|---:|---:|
| 5° | 0.25367 | 0.25497 | 0.81260 |
| 15° | 0.39957 | 0.40250 | **2.51724**, rejected |
| 25° | 0.51858 | 0.52433 | **3.17274**, rejected |

At the positive bend, the two one-sided quarter-chord endpoints differ
along the wind by 0.08475 mm at 5°, 0.76449 mm at 15°, and 2.13082 mm at
25°. The streamwise separation follows the distinct one-sided span vectors
in the implemented endpoint extension of equation (155). The corresponding
trailing rays leave a short connecting-filament contribution even for equal
circulation. At 15°/400 the nearest dominant ray is only 0.25048 mm from the
peak receiver. Its 2,707.9 m/s contribution partly cancels other filaments;
the total section-normal speed nevertheless reaches 856.39 m/s.

An independent 60-digit analytic integration of finite bound filaments and
semi-infinite trailing rays reproduces all 18 selected peak velocity vectors
across the nine pointwise conditions to 3.72e−12 of freestream speed. It
preserves self-bound exclusion and zero mutual cores for physical surface 1.
An independent scalar force/moment reconstruction checks 3,138 strips.
Reconstructed Fourier weighted residuals are at most 1.17e−14; local
residuals are retained separately and need not vanish for truncated modes.
The nonlinear solves converge; a converged circulation does not make the
supersonic states valid under the subsonic model.

This verifies the fields for OpenSwing's implemented source geometry. It
does **not** prove native ASWING uses the identical one-sided endpoint and
force-sampling convention at a doubled-point corner. The guide explicitly
preserves geometric discontinuities with zero-length computational
intervals (`aswing_doc.txt`, “Considerations for Data Discontinuities”).
That corner treatment remains the next specific source/documentation
question. A fitted core radius, relaxed gate, or cherry-picked mesh would
not resolve it.

## Evidence

- [Predeclared plan](../../artifacts/isae/sa10-louvered-basis-20261031/plan.json), [complete comparison](../../artifacts/isae/sa10-louvered-basis-20261031/report.md), [scalar audit](../../artifacts/isae/sa10-louvered-basis-20261031/analysis.json).
- [Independent velocity audit](../../artifacts/isae/sa10-louvered-basis-20261031/field-audit.json), [exact replay control](../../artifacts/isae/sa10-louvered-basis-20261031/replay/control-parity.json), [verification receipt](../../artifacts/isae/sa10-louvered-basis-20261031/receipt.json).

Registered SA-10 remains **1,083/2,268**. Native stall strength and moment
convention, strict zero-incidence outputs, tip-sail cases and the original
joint-domain conflict remain unresolved. The full goal is incomplete.
