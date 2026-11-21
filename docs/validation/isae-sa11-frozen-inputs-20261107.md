# SA-11: frozen influences do not explain the remaining pre-stall drag error

2026-11-07. Four fixed diagnostic solves test the interaction between the
documented frozen-influence setting and the preceding
[section-property diagnostic](isae-sa11-section-inputs-20261107.md).
With the extension's section properties, freezing influences changes the CD
error by only **0.139–0.190 percentage points**. CD remains **5.184–6.079% low**
at 1° incidence. No diagnostic acceptance decision changes.

The primary comparison remains **163/4,592 at 5%**. Original inputs, production
equations, validation settings and validity guards are unchanged.

## Source evidence and scope

The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
under OPER / Option selection, shows `Freeze VL matrices (fast): T`.
Its description specifies undeformed geometry and zero alpha/beta for the
influence coefficients. The [steady theory, §4.6, page 36](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf#page=36)
describes the same approximation. OpenSwing's general default is already true.

The pinned SA-11 drivers contain `kk` and `mm`, with no explicit `F` toggle
or retained startup sidecar. Their exact native command interpretation and
initial state remain unauthenticated. The registered comparison explicitly
declares evolving influences as a reconstruction; this diagnostic does not
silently replace that comparison or claim recovery of native settings.

Older original-model studies already examined frozen/evolving influences at
N25/50/100. This new experiment addresses their interaction with the independently
sourced section-property transfer at registered N64. Four fresh frozen calls
cover original and combined-transfer inputs at 240/272 m/s and 1°. Four saved
evolving results are reused without rerunning them. All other settings are fixed.

## Results

Signed error is `(prediction − reference)/abs(reference)`.

| Input | Speed, m/s | Evolving CD error | Frozen CD error | Matches per setting |
|---|---:|---:|---:|---:|
| Original | 240 | +20.654% | +20.839% | 1/7 |
| Original | 272 | +19.002% | +19.249% | 1/7 |
| Extension slope and drag properties | 240 | −5.324% | −5.184% | 5/7 |
| Extension slope and drag properties | 272 | −6.269% | −6.079% | 5/7 |

With the transferred properties and frozen influences, CL is within 0.317%,
CDi within 0.122%, and CM within 0.556%. Drag and CD still fail. These are
alternative-input diagnostics, not additions to the primary comparison.

At 240 m/s with transferred properties:

| Coefficient contribution | Evolving | Frozen |
|---|---:|---:|
| Near-field circulation drag | 0.00355628 | 0.00356941 |
| Skin-friction contribution | 0.00604789 | 0.00604954 |
| Section pressure contribution | 0.00083278 | 0.00083334 |
| Total CD | 0.01043694 | 0.01045229 |
| Separate Trefftz CDi | 0.00510143 | 0.00508851 |

The archived total CD is 0.0110238. The change to near-field circulation drag
accounts for most of the small frozen/evolving difference. Separation drag is
below 1e-30 in all eight outputs. The native table does not provide a matching
near-field/profile decomposition: subtracting its Trefftz CDi from total CD
would not identify native profile drag for this swept discrete model.

## Verification and implications

A separate saved-field reader reconstructs equations 67, 70, 72 and 73, including
friction/pressure directions, quarter-chord moments, profile-force moment arms,
and the section-normal Mach correction. It uses the parser/mesh and saved
velocity/circulation, but does not call the production aerodynamic force routines
or perform new physical solves. Maximum normalized equation error is
**3.33e-16** across eight outputs.

Maximum circulation residual is **8.23e-16**, maximum local normal Mach is
**0.93989**, and every section is at least **40.59 stall transition widths**
inside its limits. The four physical calls take 0.062–0.095 seconds each,
excluding imports and provenance checks. Both serial batches terminate normally
with one BLAS thread; all pinned production/input/previous-result hashes remain
unchanged.

This rules out frozen versus evolving influences as the explanation for the
remaining two donor-input drag failures. It supports implementation consistency
of the load laws for the saved fields, not accuracy of those velocity fields or
recovery of the native producing model. The next substantive issue remains the
documented swept-line force-point velocity treatment and native section inputs;
no further sweep of this influence toggle is warranted for these points.

Evidence: [predeclared plan](../../artifacts/isae/sa11-frozen-inputs-20261107/plan.json),
[driver](../../artifacts/isae/sa11-frozen-inputs-20261107/run.py),
[equation reader](../../artifacts/isae/sa11-frozen-inputs-20261107/analyze.py),
[complete results and hashes](../../artifacts/isae/sa11-frozen-inputs-20261107/analysis.json).
