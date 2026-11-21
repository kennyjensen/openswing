# SA-10 near-field and Trefftz drag comparison

2026-11-01. A saved-field diagnostic raises the retained three-model comparison
from **1,088/1,134 to 1,124/1,134** by calculating reported total CD as
`CDp + CDi_Trefftz`. It recovers 18 dimensional-drag and 18 CD checks, with
no losses. These are two outputs from the same 18 states, not 36 independent
flow solutions. **This reporting replacement is not adopted.**

Registered SA-10 remains **1,256/2,268**. The separate strength-20 physical
comparison remains **1,088/1,134**. The evidence identifies a useful drag
discrepancy to investigate; it does not authenticate native ASWING's output
convention, the strength-20 assumption, or the unresolved tip-sail cases.

The subsequent [strip-pair decomposition](isae-sa10-drag-pairs-20261101.md)
localizes the coarse Louvered gap to central-wing/bent-tip interactions and
measures their sensitivity to the wind-parallel quarter-chord offsets. It
supplies no justification for adopting this reporting replacement.

## Fixed scope and results

All 162 saved states are retained: Louvered, wing_alone and wing_extension,
all 27 archived rows including the repeated 12° entry, and both requested
100/200 meshes. The original inputs, reference tokens, numerical-validity
gates and 3%/strict-zero policy remain fixed. Actual saved stall strength is
20; the inherited task settings also contain an older value of 40, so the
audit explicitly verifies the applied strength against the saved raw field.
Moment comparisons use the already-established body-origin convention.

| Model | Retained physical calculation | Reporting diagnostic |
|---|---:|---:|
| Louvered | 338/378 | 374/378 |
| wing_alone | 376/378 | 376/378 |
| wing_extension | 374/378 | 374/378 |
| Total | 1,088/1,134 | 1,124/1,134 |

Both drag channels become 162/162. CL, Trefftz CDi and origin Cm remain
162/162 each. Dimensional lift remains 158/162 and efficiency 156/162.
The recovered coarse Louvered CD errors fall from median **4.944%**, maximum
**5.801%**, to median **1.857%**, maximum **2.251%**.

The ten remaining failures all have native zero references. Four dimensional
lift values have magnitude 5.447–5.686e−6 N against an absolute tolerance of
5e−6 N. Six efficiency values are approximately 0.983–1.802 against printed
zero. No clipping, changed zero convention or relaxed tolerance is applied.
The earlier [root-refinement study](isae-sa10-stall-junction-20261031.md)
remains relevant to these zero-incidence comparisons.

## What the calculation establishes

For these configurations, the current integrated total is
`CD = CDp + CDi_near`. The diagnostic replaces only its induced component:
`CD_diagnostic = CD - CDi_near + CDi_Trefftz`.
Dimensional drag follows from the same dynamic pressure and reference area.
All circulation, local velocities, physical loads and other reported outputs
are retained. No aircraft solve or source modification is required.

The [steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
defines local lift/profile forces in equations (67)/(70), and separate
Trefftz outputs in equations (207)–(211). Section 8.1 explicitly distinguishes
the Trefftz forces from integrated local forces. It does not establish this
replacement as the native total-drag output rule. A better numerical match
alone is insufficient grounds to change the force equations or output.

The new result narrows the issue to the relationship between the near-field
induced force and the Trefftz output. It does not distinguish a native
reporting convention from differences in source geometry, force sampling or
finite-mesh integration. Those remain the next mathematical questions.

## Bound-vortex and wake decomposition

For six saved Louvered states, a separate finite-filament calculation splits
the near-field induced force into bound and trailing-wake contributions.
An independent replay using the current production kernels then evaluates
both components directly and reconstructs the saved total velocity.

| Incidence | Requested intervals | Bound CDi | Wake CDi − Trefftz CDi | Near CDi − Trefftz CDi |
|---|---:|---:|---:|---:|
| 5° | 100 | 0.000483820 | −0.000433105 | 0.000050715 |
| 5° | 200 | 0.000572514 | −0.000584899 | −0.000012385 |
| 15° | 100 | 0.006764678 | −0.003746803 | 0.003017875 |
| 15° | 200 | 0.009082273 | −0.008703300 | 0.000378973 |
| 25° | 100 | 0.013908504 | −0.005928767 | 0.007979736 |
| 25° | 200 | 0.017519435 | −0.016634473 | 0.000884962 |

The bound and wake terms partly cancel. Neither a zero-bound-force assumption
nor identifying the wake-only force with Trefftz drag is supported by these
saved discretizations. Removing an individual term would not be a correction.
This is consistent with the earlier [bend and endpoint investigation](isae-sa10-louvered-basis-20261031.md),
which also shows that passing drag on the finer mesh is not mesh convergence.

The scalar finite-filament formula and production's cylindrical-coordinate
formula agree in bound velocity within 6.40e−14 m/s. Direct bound-plus-wake
reconstruction matches the saved velocity within 2.56e−13 m/s and near-field
CDi within 1.88e−16. The calculation retains zero mutual core for physical
surface 1 and exclusion of each receiver's own bound segment.

An initial diagnostic used an algebraically equivalent cross-squared formula
that subtracts nearly identical endpoint unit vectors. It lost accuracy at
nearly collinear receivers and is preserved as `bound_split_cross_squared.py`
with its output. The rationalized calculation supersedes those component
values. **This was a diagnostic arithmetic issue; the production kernel
already uses a stable rationalized expression.** No production fix follows.

## Verification and execution

The 18-state pilot gains four checks without losses and satisfies its recorded
extension rule. The extension processes 54 saved states per model in three
serial standard-library batches, each taking under 1.5 seconds after startup.
It reconstructs all 162 profile/near-field force contributions and checks all
1,134 original native scalar comparisons. The component replay uses one BLAS
thread. No new nonlinear solves, browsers, builds or background workers run.

All 42 registered status rows and 136 production source hashes are checked
unchanged in the final receipt. The full project remains incomplete.

- [Pilot plan and extension rule](../../artifacts/isae/sa10-drag-reporting-20261101/plan.json)
- [Full saved-state plan](../../artifacts/isae/sa10-drag-reporting-20261101/full-plan.json)
- [All comparisons and remaining failures](../../artifacts/isae/sa10-drag-reporting-20261101/full-analysis.json)
- [Scalar bound decomposition](../../artifacts/isae/sa10-drag-reporting-20261101/bound-split.json)
- [Direct production-kernel component replay](../../artifacts/isae/sa10-drag-reporting-20261101/bound-verification.json)
- [Final verification receipt](../../artifacts/isae/sa10-drag-reporting-20261101/receipt.json)
