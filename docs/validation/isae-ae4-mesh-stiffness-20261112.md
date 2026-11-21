# AE-4: node placement and stiffness-jump sensitivity

Eight bounded diagnostic solves isolate two documented setup questions. **Node
placement has the larger effect on the two audited modes.** Modified cosine
reduces both discrepancies, but neither reaches the 5% allowance. The published
1989 spacing does not resolve them either. No production default, equation,
reference target or acceptance gate changes; the primary score remains
**122/1,200**.

![AE-4 setup sensitivity](../../artifacts/isae/ae4-spacing-20261112/mesh-stiffness-readable.png)

All alternatives use 40 base intervals with the existing required station at
`t = 0.52`, giving 41 physical intervals and 42 nodes. Original geometry,
distributed mass and inertias, stiffness values, offsets, wall, gravity,
circulation, lag, local mode count and complex shift remain fixed. The
stiffness diagnostics change only sampling at the duplicated station; the
spacing diagnostics retain the original sided stiffness sampling.

## Results

| Diagnostic | Flutter-mode Re(λ), IAS 69 (1/s) | Native error | Candidate slow Re(λ), IAS 103 (1/s) | Conditional native error |
|---|---:|---:|---:|---:|
| Archived ASWING | −0.1780785 | — | +0.033334177 | — |
| Original cosine | −0.091160898 | 48.809% | +0.093297390 | 179.885% |
| Cosine, both GJ traces take left value | −0.091141144 | 48.820% | +0.093297986 | 179.887% |
| Cosine, both GJ traces take right value | −0.113369878 | 36.337% | +0.092304783 | 176.907% |
| Modified cosine, original GJ traces | −0.206277471 | 15.835% | +0.013291335 | 60.127% |
| Drela 1989 spacing, original GJ traces | −0.246078207 | 38.185% | −0.029498473 | 188.493% |

The IAS 69 value is the critical high-frequency oscillatory mode in the primary
native export. The IAS 103 value uses the separate NN10 native continuation
diagnostic from the [preceding comparison](isae-ae4-transition-coverage-20261112.md).
Its printed imaginary part, `3.6546462e−7 /s`, remains in the data. Native mode
identity is still unverified. The NN4 primary table's candidate real root is
slightly different, `0.033334576 /s`; neither table is substituted for the other.

No alternative repairs these two sensitive components. The two main
oscillatory roots at IAS 103 remain close: their largest conditional component
errors are **0.934%** for modified cosine and **2.538%** for 1989 spacing.
The interpolated mechanical fields retain high overlap with the original
cosine modes: minimum assigned MAC **0.999974** and **0.999949**, respectively.
The stiffness alternatives have minimum MAC above **0.99999986**. Thus the
changes are consistent with the same computed branches moving with the
discretization, rather than an ordinal swap. This does not prove native mode
identity or spatial convergence.

## What the documentation says about the GJ jump

The authoritative [reference index](aswing-authoritative-references.md), source
catalog, Jan Part IV §3.4 and original AE-4 model/driver/table were consulted.
The original [user guide](../../reference/aswing_doc.txt), section
“Considerations for Data Discontinuities,” lists the variables whose doubled
input stations enable native computational breaks by default. `GJ` is absent.
For a value jump in other variables, the guide warns that coincident nodes
can receive either side's value depending on evaluation roundoff. Native builds
can change `KBREAK` in `INDEXB.INC`; the archived build's flags are unavailable.

The literal Pazy model has a `GJ` jump from **6.5 to 16.9 N m²** at `t=0.52`.
OpenSwing already reports this native-compatibility issue through
`model.compatibility_notes`. The same doubled input row contains geometry and
chord fields, so this is not evidence that native ASWING necessarily omitted
the computational break altogether.

OpenSwing evaluates the left and right material limits separately, then forms
the endpoint-averaged stiffness used by steady Eqs.49–54, pp.12–14. Four tests
sample the original left value on both traces or the original right value on
both traces, at 69 and 103 m/s. The sampler override exists only within each
diagnostic worker and is restored afterward. It changes no interior sample or
other property. Original model bytes remain intact; the altered interpretation
is explicitly recorded in each request and report.

On the original cosine mesh, using the left value changes the averaged GJ of
only `[0.52, 0.5200267941518012]`, from 16.9 to 11.7. Using the right value
changes only `[0.5094780690348375, 0.52]`, from 6.5 to 11.7. The highly
unequal adjacent interval lengths explain the unequal sensitivity. These are
endpoint stiffness averages, not fitted replacement material values.

The right-trace alternative removes **25.55%** of the original critical-real
gap at IAS 69, but only **1.66%** of the slow-root gap at IAS 103. This makes
the documented ambiguity relevant to damping precision, but insufficient to
explain the main slow-mode discrepancy on this mesh. Neither trace is adopted
as the historical native convention.

## The two spacing rules and their limits

The existing [modified-cosine option](modified-cosine-option-20261030.md) was
checked against printed SA-2 coordinates. For `u = sin((2j/N−1) asin(q))`, it
uses `η = 0.7u + 0.3u³`, with the existing binary32 endpoint convention. This
is an available source hypothesis, not an authenticated universal native
default. No coefficient was adjusted for AE-4.

Drela's [1989 paper](../../reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf),
printed p.326, Eqs.37–38, provides the other rule. With `u=2j/N−1`, the material
fraction is `(1 + sin(πu(1+|u|)/4))/2`. The independent cosine expression,
endpoints and monotonicity are checked before the plan is recorded. The
current material arc inverse maps these fractions into the literal beam's
parameter domain. Mandatory-station insertion remains unchanged. The original
guide associates this paper with **ASWING 3.x**; it does not establish the
archived 5.x mesh generator. See the
[source supplement](isae-st4-node-placement-sources-20261109.json).

Both alternatives move the sensitive real components across the native values,
but the 1989 rule gives the opposite sign for the candidate slow root at
103 m/s. Their coefficients were selected from existing sources before solving,
not by fitting outputs. A closer coarse-grid result alone is not evidence for
changing OpenSwing's default. Exact `I 40` counting, local node adjustment and
native coordinates remain unknown.

## Execution, accounting and next work

All **180 numerical checks** pass: 92 in the stiffness study and 88 in the
spacing study. They include fresh coupled-base residuals, independent residual
actions for both matrices, every retained left/right eigenpair, mass pairing,
root clamps, exact sampling restrictions and node counts. Complete sparse
pencils, all four modes and base reports are retained. This workload omits UI
modal-output recovery; its timing is not a browser performance benchmark.

All eight workers are terminal and reaped. Maximum child CPU, supervised wall
and RSS are **2.76 s, 3.10 s and 91.7 MiB**. Each uses one BLAS thread and
unchanged **512 MiB /15 CPU /25 wall-second** caps; library preload is separately
bounded. Production source hashes are unchanged. Both assessments retain their
own UTC observations: 2026-11-12T14:24:04.248079+00:00 and
2026-11-12T14:30:01.052943+00:00.

Primary accounting stays **122/1,200**: 128 paired components, six mismatches,
16 unmatched, 12 unknown initial values and 1,044 unrun. Median failed paired
error remains 11.47%, range 5.91–48.81%. All primary tiny/real-root requirements,
the 9,480 historical modal components and later branches remain open. These
alternative settings receive no new acceptance scope or primary votes.

Next, refine the modified-cosine diagnostic at the same two speeds and compare
its convergence trend with the existing cosine sequence. This can distinguish
finite-grid sensitivity from a different limiting formulation. Recovering
native node placement would still be needed to authenticate `I 40`. The
[prescribed-frame block argument](isae-ae4-frame-constraints-20261105.md) remains
relevant: adding stationary prescribed-acceleration integrators alone cannot
move nonzero wing roots under its assumptions. Actual wall-frame support and
unknown native restraint masks remain separate open work.

- [Stiffness study plan, source pins and four cases](../../artifacts/isae/ae4-stiffness-trace-20261112/plan.json)
- [Stiffness assessment](../../artifacts/isae/ae4-stiffness-trace-20261112/assessment.json)
- [Spacing study plan and source pins](../../artifacts/isae/ae4-spacing-20261112/plan.json)
- [Spacing assessment](../../artifacts/isae/ae4-spacing-20261112/assessment.json)
- [Standalone comparison SVG](../../artifacts/isae/ae4-spacing-20261112/mesh-stiffness-readable.svg)
