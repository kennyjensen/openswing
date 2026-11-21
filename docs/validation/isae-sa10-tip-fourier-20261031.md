# SA-10 tip sails: Fourier circulation does not resolve the junction failures

2026-10-31. Thirty-six new cold runs finish for the literal `TS_60_40_80`
and `TS_80_60_40` models. The tested 20/40-mode representations lose native
output matches and retain, or worsen, excessive local junction velocities.
No production setting or acceptance gate changes. Registered SA-10 remains
**1,256/2,268**, including the earlier origin-moment correction.

## What the documentation requires

The ASWING guide's “Physical index” section specifies zero mutual vortex
cores for logical beams sharing a physical index. It warns about numerical
noise when another beam's trailing legs approach a control point. This
does not specify an additional circulation-continuity constraint at a branch.
The retained ISAE report's SA-10 discussion explicitly describes local lift
divergences and missing circulation continuity at the three-tip junction.

OpenSwing therefore retains the seven supplied logical beams, their shared
physical index 1, and the corresponding zero mutual cores. We do not merge
their circulation unknowns or add a junction constraint to improve matching.
This agrees with the documented model limitations; it does not prove which
native node array or circulation representation produced the archived values.

Steady equations 63, 150 and 201 provide an alternative Fourier circulation
representation and its weighted residual. This investigation tests that
published representation on the tip-sail geometries, complementing the
earlier [Louvered study](isae-sa10-louvered-basis-20261031.md).

## Predetermined comparison

The plan contains:

- Both literal tip-sail models at 10°, 20° and 25°, with 128 intervals per
  logical beam and either 20 or 40 Fourier modes per logical beam.
- Both default stall strength 40 and the previously studied, unconfirmed
  strength-20 hypothesis.
- Corresponding 64-interval runs at 25° to test refinement.
- Four fresh pointwise controls at 25°/128 intervals.

These are 32 Fourier runs plus four pointwise controls. Current influences,
geometry, section properties, cores and the 3%/original-absolute policy are
unchanged. Native CM is compared with the corrected body-origin output.
The archived drivers do not authenticate either tested mode count.

Each fine-mesh scope below contains the same six conditions and seven native
outputs per condition. Physically rejected states contribute zero passes.

| Stall strength | Representation | Passing checks | Valid states | Local-Mach rejections | Gains / losses vs pointwise |
|---|---|---:|---:|---:|---:|
| 40, default | Pointwise | 20/42 | 5/6 | 1/6 | — |
| 40, default | 20 modes | 10/42 | 3/6 | 3/6 | 0 / 10 |
| 40, default | 40 modes | 12/42 | 3/6 | 3/6 | 0 / 8 |
| 20, diagnostic | Pointwise | 26/42 | 4/6 | 2/6 | — |
| 20, diagnostic | 20 modes | 11/42 | 3/6 | 3/6 | 0 / 15 |
| 20, diagnostic | 40 modes | 13/42 | 3/6 | 3/6 | 0 / 13 |

The pointwise 10°/20° controls reuse pinned saved results with the corrected
moment translation; 25° controls are fresh. These overlapping samples do not
replace the complete registered SA-10 result.

## Refinement exposes the local-flow failure

Every 25° coarse Fourier run is subsonic, and every corresponding fine run
is rejected. At default strength 40:

| Model | Modes | Peak normal Mach, N64 | Peak normal Mach, N128 |
|---|---:|---:|---:|
| TS_60_40_80 | 20 | 0.746737 | **1.812685** |
| TS_60_40_80 | 40 | 0.551845 | **1.549918** |
| TS_80_60_40 | 20 | 0.560586 | **1.115844** |
| TS_80_60_40 | 40 | 0.556700 | **1.089963** |

The problem also appears at 20° in `TS_60_40_80`: its fine Fourier maximum
Mach is 1.380–1.612 at strength 40, whereas the saved pointwise state was
subsonic. At strength 20, fine 25° peaks extend to **1.862604**.

The `TS_80_60_40`, strength-20, 40-mode, N64 result passes **7/7** native
outputs at 25°, but its N128 counterpart reaches Mach **1.117382** and is
rejected. Selecting that coarse pass would conceal the failed refinement.

## Verification

All 36 calls solve their declared circulation equations. There are **21
computed states and 15 local-Mach rejections**, with no worker failures;
all processes terminate and are reaped. The largest independently rebuilt
weighted residual is **6.63e−14**, normalized by flight speed.

This is a modal convergence result. The largest unprojected local tangency
defect is **9.53 times flight speed** near the junction. A small weighted
residual does not imply pointwise tangency, benign local velocities or mesh
convergence for a truncated series.

For all valid new states, independent section-force integration reproduces
the resultant force exactly and the origin moment within **1.25e−15** after
coefficient normalization. The verifier reconstructs the circulation from
the stored Fourier coefficients within **2.14e−14 m²/s**.

A separate 60-digit Biot–Savart calculation checks **24 peak velocity
vectors** across both models, both strengths, both mode counts and the
coarse/fine samples. Its largest discrepancy is **1.20e−10 times flight
speed**; it independently reproduces the Mach classifications. It preserves
own-bound exclusion and the specified zero mutual cores.

The four new pointwise controls reproduce the previous evidence: one valid
wrench agrees within **3.09e−16** scaled error, and the three rejected states
have identical retained circulation and velocity arrays. A separate verifier
also reads the two original full-variable export tables, checks all **252
native scalar entries** used by the 36 requests, and verifies every gain/loss.

Two postprocessing type errors and an initial verifier assumption about the
export's column layout were corrected; their failed logs are retained. They
required no physical reruns, changed no reference values and affected no
solver inputs. Final analysis and independent verification both complete.

## Remaining question

A later [bound-point geometry check](../../artifacts/isae/sa10-tip-fourier-20261031/bound-point-geometry.json)
examines the four retained pointwise 25° controls, representing two distinct
geometries. Every force receiver lies inside its own bound segment: maximum
distance **3.84e−17 m**. The bound endpoint vector agrees with section span
times strip length within **1.32e−16 m**. The receiver's fractional position
ranges from 0.250009 to 0.749991, consistent with Glauert-angle interpolation
rather than an arithmetic midpoint. Thus an off-segment force receiver is
not present in these tip-sail conditions. This does not authenticate native
junction geometry or remove neighboring-source singularities.

These results reject the tested mode counts as a standalone remedy. The
remaining source question is the producing ASWING discretization and its
near-junction source/receiver geometry. The guide and report establish the
interaction hazard, but do not supply the native station arrays or local
fields needed to identify their exact treatment. The original conflicting
`TS_60_45_30` joint records also remain unresolved.

Artifacts: [predeclared plan](../../artifacts/isae/sa10-tip-fourier-20261031/plan.json),
[all comparisons](../../artifacts/isae/sa10-tip-fourier-20261031/analysis.json),
[independent velocity verification](../../artifacts/isae/sa10-tip-fourier-20261031/field-verification.json),
[verification receipt](../../artifacts/isae/sa10-tip-fourier-20261031/receipt.json),
[run log](../../artifacts/isae/sa10-tip-fourier-20261031/run.log).

No new registered pass is claimed. SA-6–SA-10 and the full project remain
unfinished.
