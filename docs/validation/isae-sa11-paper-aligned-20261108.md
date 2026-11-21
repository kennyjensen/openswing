# SA-11: aligned operating settings and the remaining baseline confounder

2026-11-08 UTC. The same **48 paper-focused targets now pass 21/48 at 5%
(43.75%)**, up from 20/48. One missing upper-winglet drag bracket was filled;
no previous pass was lost. There are still 18 numerical mismatches, one
rejected solution and eight missing comparisons. The original archive remains
**1,060/9,184**, with all its unavailable values retained separately.

The [comparison page](../../public/isae-sa11-paper/index.html), served at
`/isae-sa11-paper/`, now includes both absolute lift/drag curves and a separate
plot of drag change relative to the bare wing at equal lift.

| Configuration | Pass / required | Mismatch | Rejected | Missing | Failed errors: median / maximum |
|---|---:|---:|---:|---:|---:|
| Bare wing | 2/12 | 10 | 0 | 0 | 7.12% / 18.90% |
| Planar extension | 8/12 | 4 | 0 | 0 | 7.41% / 8.76% |
| Upper winglet | 11/12 | 1 | 0 | 0 | 5.25% / 5.25% |
| Upper/lower winglets | 0/12 | 3 | 1 | 8 | 7.57% / 36.42% |
| **Total** | **21/48** | **18** | **1** | **8** | Computed mismatches only |

## What was run and why

The preceding [paper-focused assessment](isae-sa11-paper-suite-20261108.md)
identified mixed frozen/current influence settings as an obstacle to comparing
the configuration differences. The original baseline and extension have now
been run with **frozen influences**, retaining their original inputs and
fixed cosine-64/minimum-spacing meshes: 62 and 60 actual intervals respectively.
Each covers 0°–5.5° in quarter-degree steps at 240 and 272 m/s. Four identical
frozen extension states were authenticated and reused.

One additional upper-winglet state at 240 m/s, 5.25° extends its existing
report-derived −4°/Joint-corrected model, with the same 32 + 16 + 16 mesh.
Together with the accepted 5° state, it brackets CL = 0.7. The shared minimum
remains **0.0164659927127284 m**. No model coefficients, geometry, mesh,
equations, core or numerical validity gate were tuned.

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted; the report and steady PDF/text hashes were checked.
Drela's User Guide, **OPER / Option selection**, lists frozen VL matrices as
enabled and describes evaluation on undeformed geometry at zero alpha/beta.
Steady **§4.6, p.36**, describes the approximation. Jan Part I **p.35 / Figure
22, p.39**, remains the comparison basis. This alignment adopts a documented
setting without claiming recovery of the original native startup state.

The previous investigation already showed that this toggle cannot explain
the main drag discrepancy. These runs establish consistent operating settings
and complete curves for the paper's equal-lift comparison; they are not another
search for a favorable toggle setting. The baseline and extension pass counts
are unchanged. The new [v2 specification](sa11-paper-suite-v2.json) preserves
all 48 identities, reference targets and 5% gates, including the lower-winglet
missing/rejected comparisons.

## Upper-winglet result

At CL = 0.7:

| Mach label | Archived CD | OpenSwing CD | Error | Status |
|---|---:|---:|---:|---|
| 0.70 | 0.021222415 | 0.022111203 | +4.188% | Now passes; bracket 5°–5.25° |
| 0.80 | 0.020623418 | 0.021706706 | +5.253% | Still fails; bracket 4.5°–4.75° |

The upper-winglet lift checks all pass. Its original **294/294 same-incidence
comparisons remain recorded**; the new matched-lift drag comparison is a
different test. Filling the lower-speed bracket gives its sole new primary
pass. The faster high-lift discrepancy is retained without rounding it below
5% or relaxing acceptance.

## The source inputs change more than the wingtip

The aligned runs retain a roughly **6.81–7.23%** bare-wing lift bias. The
extension's six lift checks are within **0.444%**, but four equal-lift drag
checks still fail, with maximum error **8.76% low**.

A literal source/parsed-field audit at six shared main-wing stations confirms
these input differences:

| Main-wing section input | Original bare wing | Extension / upper winglet |
|---|---:|---:|
| dCLda, per radian | 7.0 | 6.34 |
| Skin-friction Cdf | 0, from the declared zero multiplier | 0.0055–0.0068 |
| Pressure-drag Cdp | 0.01818, from 2 × 0.00909 | 0.00133–0.00246 |
| CLmax | 3.0 | Parsed default 2.0 |

The zero-lift-angle and section-moment inputs agree at the sampled stations.
The upper/lower model shares the companion lift-slope/drag data but explicitly
sets CLmax = 0.8. Its stall-input and lower-root problems remain separate,
and post-stall repairs remain deferred. The sampled values are retained in
`shared_main_wing_input_audit` in the assessment; no coefficients were changed.

At equal CL = 0.5, the configured-model drag differences are:

| Configuration | Mach label | Archived ASWING ΔCD | OpenSwing ΔCD |
|---|---:|---:|---:|
| Planar extension | 0.70 | −0.00072622 | −0.00297151 |
| Planar extension | 0.80 | −0.00069303 | −0.00294776 |
| Upper winglet | 0.70 | −0.00276893 | −0.00353586 |
| Upper winglet | 0.80 | −0.00288372 | −0.00347805 |
| Upper/lower winglets | Both | Available in archive | Missing valid interpolation coverage |

Flight conditions and influence conventions now match. However, these
differences **also include the changed main-wing airfoil properties**. They
cannot be attributed solely to adding a wingtip device. For the upper winglet,
the predicted drag reduction is 27.7% / 20.6% larger in magnitude at CL = 0.5,
but that is a configured-model discrepancy with a documented baseline
confounder, not proof of an error in the winglet interaction alone. These
derived differences are not additional primary passes.

![Configured-model drag differences](../../artifacts/isae/sa11-paper-suite-aligned-20261108/wingtip-drag-benefit.svg)

The next controlled comparison should remove the winglets from the same
report-derived model while retaining its main-wing geometry, section data,
nodes and operating settings. That would isolate the device contribution.
It must be disclosed as a separate consistent-main-wing control, not silently
substituted for the original bare-wing archive input. The already tested
6.34 slope/profile transfers motivate this control; they do not establish the
historical producing input or justify parameter fitting.

## Verification

All **89 new physical solves** complete, plus four authenticated saved states:
93 valid states, no new rejection, timeout or interrupted job. Thirty-one
foreground batches contain at most three serial calls each, one BLAS thread,
512 MiB address-space, 15 CPU-second and 25 wall-second limits. Maximum
recorded batch work is **5.18 seconds**, total **109.75 seconds**, peak RSS
**281.86 MiB**. These are local Python measurements, not browser timings.

The largest circulation residual is **9.79e−16**, maximum normal Mach
**0.75848**, and minimum stall margin **8.82 configured transition widths**.
The independently evaluated zero-core segment/ray velocity agrees within
**7.26e−16 of freestream** across every aligned state. Force and moment
reductions agree within **3.34e−16 / 9.33e−15** in coefficient units.
The three per-configuration audits authenticate 251 input/source pins and
all saved reports. An initial checker assertion used a signed absolute-target
error for the recorder's negative Cm magnitude ratio; the convention was
reconciled without changing or rerunning any physical result.

The final paper-suite audit authenticates **875 pins**, independently reduces
the source forces and checks every interpolation and decision in Decimal
arithmetic. Its maximum force coefficient difference is **4.45e−16**, and
interpolation difference **6.94e−18**. Both plots were visually inspected.
Browser, Vite, build and background-solver tests remain unstarted under the
existing hold. No production solver or default changed.

- [Frozen solve plan](../../artifacts/isae/sa11-paper-aligned-20261108/plan.json),
  [driver](../../scripts/verify_sa11_paper_aligned.py),
  [verified aggregate](../../artifacts/isae/sa11-paper-aligned-20261108/analysis.json),
  [independent field checker](../../scripts/check_sa11_paper_aligned.py).
- [All 48 updated checks](../../artifacts/isae/sa11-paper-suite-aligned-20261108/analysis.json),
  [independent scoring verification](../../artifacts/isae/sa11-paper-suite-aligned-20261108/verification.json),
  [assessment updater](../../scripts/sa11_paper_suite_aligned.py).
- [Absolute-curve PNG](../../artifacts/isae/sa11-paper-suite-aligned-20261108/paper-comparison.png),
  [drag-benefit PNG](../../artifacts/isae/sa11-paper-suite-aligned-20261108/wingtip-drag-benefit.png).

`npm run test:isae:sa11:paper -- --output <new-directory>` now assesses the v2
saved evidence; it does not launch physical solves. The same independent
checker and plot generator documented in the v1 report accept that new output.
The progress scope records the frozen-setting alignment explicitly. Previous
observations and both the v1 and original-archive results remain intact.
