# SA-10 aerodynamic moment output reference

2026-10-31. The native polar `CM` comparison now uses an explicit body-origin
pitching moment. This corrects a reporting-reference mismatch, without changing
circulation, section loads, the input reference point or moment constraints.

The registered default-setting scope improves from **1,083/2,268 to
1,256/2,268**, gaining 173 CM checks with no losses. Typical failed fine-mesh
CM error falls from approximately 112% to **3.96%**, maximum **9.92%**.
These counts reanalyze the complete saved scope; twelve new cold solves verify
the corrected production output and parity of the unchanged physical loads.
They are not a new 324-state solve campaign.

## Documentary basis

The [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
equations 220–225, defines aerodynamic moments by integrating local couples
plus `r × force`, where `r` is position from the body origin. Its separate
moment constraint, equation 187, translates to the specified reference point:

```text
M_reference = M_origin + F × r_reference
M_origin    = M_reference + r_reference × F
```

The [user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
“Reference-Parameter Listing,” also distinguishes internal origin moments
from reference-location quantities. Its displayed moment-translation sign
conflicts with equation 187; the implementation uses the physical force-arm
identity above, independently tested against exact distributed first moments.
The guide's Reference-block description still applies to moment constraints.

The original straight-wing deck provides an additional check: its axis is
`x=z=0`, chord is 0.178 m, quarter-chord section moment is zero, and
`Xmom=0.05 m` lies behind quarter chord (0.0445 m). At 5 degrees the archive
prints `CL=0.365220`, `CD=0.0169002` and `CM=-0.0911577`. The native moment
has the sign and approximately quarter-chord magnitude expected about the
origin. Interpreting that CM about Xmom would imply a normal profile-force
coefficient of about −0.410, versus +0.000672 about the origin. This supports
the documented origin interpretation; it is not a fitted reference offset.

The native executable is unavailable, and these decks' archived CG is also
zero. Their numbers alone cannot distinguish origin from CG. The selected
mapping follows the published equations; it does not authenticate the native
build, hidden settings or output code. The older comparison's origin-moment
hypothesis is superseded by this documented output convention.

## Implementation

The analytic rigid state/control API now also returns
`distributed_aero_wrench_origin`, `coefficients_origin`, and
`base_coefficients_origin`. Its existing outputs remain about the file reference.
For these fixed-geometry responses, equation 223 reduces the translation to
`dM_origin = dM_reference + r_reference × dF`; this is applied in body axes
before the stability rotation and separate span/chord normalizations. Metadata
identifies both references and the distributed aerodynamic load scope. All
columns still share one physical evaluation and one circulation factorization.

Four [native regressions](../../tests/test_rigid_derivative_moment_origin.py)
pass for state/control responses on wing-only and wing–body fixtures. Eight
analytic calls check a general three-coordinate reference shift; eight fresh
nonlinear perturbation solves independently check the resulting origin columns.
The [test receipt](../../artifacts/isae/rigid-origin-derivatives-20261031/test-receipt.json)
records the completed 20.49-second run. This is output verification, not a new
native-ASWING comparison. The [SA-6 reference audit](../../artifacts/isae/rigid-origin-derivatives-20261031/sa6-reference-audit.json)
checks all four paired decks and all 44 native export headers: every moment
reference is zero. Consequently this translation cannot explain its remaining
derivative errors and changes none of its 88 saved comparison states.

Browser verification remains [pending after host disconnects](../../artifacts/isae/sa10-browser-origin-20261031/HANDOFF.md);
automatic Vite/Chromium test retries remain suspended. Packaged builds have not
been refreshed by this native-output follow-up.

- `moment` and `Cm` retain their existing file-reference meanings. Trim,
  custom constraints and structural load assembly therefore retain their
  reference-point wrench.
- `moment_origin`, `distributed_aero_moment_origin` and `Cm_origin` expose
  the corresponding origin quantities, with reference, axes and load-scope
  metadata. They are available as physical ROM outputs as well.
- The native polar comparison maps its archived `CM` column to `Cm_origin`.
  The stored comparison retains both referenced and origin moments. Other
  required outputs, archived values and tolerances are unchanged.
- Moment-response integration includes both force changes and moving force
  arms about each origin. No stall coefficient, mesh or core radius changes.

The total-wrench origin fields have the same aerodynamic/apparent-mass/
point-drag/engine scope as their existing reference-wrench counterparts.
The distributed field excludes apparent mass, engines and point objects.
SA-10's steady, unpowered decks do not introduce a difference between these
scopes. This change does not redefine the separate stability-derivative API.
The browser runtime bundle was not rebuilt during this validation task.

## Complete retained comparison

| Literal model | Default strength 40, old CM mapping | Default strength 40, corrected CM | Strength 20 diagnostic, corrected CM |
|---|---:|---:|---:|
| wing_alone | 246/378 | 282/378 | 376/378 |
| wing_extension | 174/378 | 194/378 | 374/378 |
| Louvered | 174/378 | 203/378 | 338/378 |
| TS_60_40_80 | 210/378 | 247/378 | Not rerun in this complete scope |
| TS_80_60_40 | 279/378 | 330/378 | Not rerun in this complete scope |
| TS_60_45_30 | 0/378 | 0/378 | Original joints remain blocked |
| Total default scope | 1,083/2,268 | **1,256/2,268** | — |
| Three-model strength-20 scope | — | — | **1,088/1,134** |

The 54 blocked original-joint states and one failed tip-sail solve remain
counted. For the strength-20 diagnostic all 162 CL, CDi and CM checks pass.
Its remaining 46 failures are 36 coarse louvered drag/CD checks (median
4.94%, maximum 5.80%), four strict zero-lift checks and six strict
zero-efficiency checks. Native stall strength is still unverified; the
production default remains 40. This is not a fully passing SA-10 family.

The prior louvered and tip-sail mesh-refinement/local-Mach problems remain.
An additional review of the guide and literal beam domains found no basis
for bypassing the original TS_60_45_30 joint error: rigid beams retain joint
constraints, and each disputed signed station is outside its named beam.

## Verification and retained evidence

- 138 targeted tests pass across exact profile moments, new origin outputs,
  polar adapters and physical ROM outputs. The final label-only edit is
  followed by 16 focused passing checks (overlapping the initial 138).
- Twelve cold solves: three models, 5 and 20 degrees, strengths 40 and 20,
  all on the 200-interval mesh. All numerical gates pass. The maximum
  saved-versus-fresh wrench difference divided by qS is **3.86e−17**;
  origin CM matches the independently translated saved result exactly.
- The complete 324-state default and 162-state diagnostic reanalyses preserve
  original row IDs, repeated incidence, failed outcomes and source hashes.
  Native source bytes remain unchanged. The deliberately changed comparison
  adapter has an explicit old/new code-hash record.
- A preparation check and a postprocessor receipt check each stopped before
  completion and were corrected. Neither caused a repeated physical solve
  or a changed acceptance gate; details are retained in `preflight.json`.

Artifacts: [plan](../../artifacts/isae/sa10-moment-origin-20261031/plan.json),
[cold-run log](../../artifacts/isae/sa10-moment-origin-20261031/run.log),
[complete comparisons](../../artifacts/isae/sa10-moment-origin-20261031/analysis.json),
[verification receipt](../../artifacts/isae/sa10-moment-origin-20261031/receipt.json).

The full project remains incomplete. SA-6 rate derivatives, SA-7 low-lift
efficiency, SA-8 drag/setup differences and SA-10 stall/junction issues remain
open. SA-9 is absent from the public repository.
