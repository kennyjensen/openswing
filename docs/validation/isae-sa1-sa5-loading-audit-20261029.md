# SA-1/SA-5: circulation loading and independent section limits

The remaining high-incidence induced-drag differences mostly follow a deficit
in circulation-based lift. Modified cosine spacing does **not** remove that
deficit: in all 14 saved high-incidence pairs (at least 14°, both meshes),
Trefftz lift moves slightly farther from the archived inference. The small
CDi improvement comes from the accompanying efficiency change.

This analysis retains all 46 SA-1/SA-5 states, including four zero-incidence
states, and changes no reference tolerances or registered pass counts.
At the time of this loading audit, default SA-1/SA-5 passed **146/154** and
**154/168**; their separate modified-grid scores were **146/154** and
**162/168**. The later [exact-zero efficiency reporting correction](isae-sa5-zero-efficiency-20261029.md)
raises SA-5 to **158/168 default** and **166/168 modified**, without changing
the finite loading differences analyzed here. SA-1 remains **146/154**.

## Induced drag and loading

For these symmetric zero-sideslip models, the documented efficiency definition
(steady Eq. 211) gives the positive native lift magnitude as
`CLi = sqrt(pi * AR * efficiency * CDi)` at positive incidence. This inference
assumes native net Trefftz side force is zero and chooses the positive branch;
the archive does not contain native section circulations. Symmetry is checked
against the saved OpenSwing fields. Zero-incidence efficiency placeholders are
retained explicitly and do not provide a signed lift inference.

The exact factorization is
`CDi_ours/CDi_native = (CLi_ours/CLi_native)^2 * (e_native/e_ours)`.

| Fine mesh, highest incidence | Modified-grid CLi error | Squared-lift factor | Inverse-efficiency factor | CDi error |
|---|---:|---:|---:|---:|
| SA-1, 18.091° | −2.6620% | −5.2532% | +0.6142% | −4.6713% |
| SA-5, 18° | −1.8685% | −3.7022% | +0.3656% | −3.3501% |

The factors multiply, so their percentages cannot simply be added. Propagating
half-last-digit rounding intervals through the native inference changes these
CLi error estimates by less than 0.0001 percentage point in either direction.

Default-to-modified spacing changes high-angle fine-grid CLi errors from
−2.6547% to −2.6620% in SA-1 and from −1.8522% to −1.8685% in SA-5.
It therefore provides no evidence that the high-incidence circulation law is
now closer to native ASWING.

## Why SA-5 total lift looks closer

At 18°, modified-grid SA-5 total CL is only 0.8384% low, while Trefftz CLi is
1.8685% low. The saved force split is:

| Quantity | Value |
|---|---:|
| Total CL | 0.825253618 |
| Near-field circulation CL | 0.828259654 |
| Actual profile-force CL | −0.003006036 |
| Trefftz CLi | 0.732450245 |

Thus `CL−CLi` is **not profile lift** for this nonplanar wing. Its near-field
circulation contribution differs from the Trefftz value. The native profile
force cannot be recovered separately from the available archived columns.

Changing spacing raises total CL by 0.00494136 while lowering CLi by
0.00012210; the change in `CL−CLi` accounts for the difference. This directs
further work toward distinguishing circulation closure from near-field force
recovery. It does not establish which native discrete construction was used.

The subsequent [SA-5 root-loading investigation](isae-sa5-root-loading-20261029.md)
now makes that distinction more directly. At 18°, prescribed circulation
transfers attribute 98.58–100.01% of the induced-velocity lift spacing change
to the mesh/transfer term across both meshes, directions and reconstructions.
This term includes source geometry and resampling as well as force receivers.
Independent opposite-leg integrals confirm the strong root contribution.
It is not a total-drag attribution or evidence of a converged corner limit;
the fine modified state already reaches normal Mach 0.97923.

The [all-state loading decomposition](../../artifacts/isae/sa1-sa5-loading-decomposition-20261029/report.md)
and [paired mesh comparison](../../artifacts/isae/sa1-sa5-loading-decomposition-20261029/default-vs-modified.md)
retain source hashes, rounding intervals, algebraic force replay and every
original comparison. Neither performs a new aerodynamic solve.

## New independent section check

The [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
Eqs. 146–160 and 202–204, provides an infinite straight-wing limit with constant
circulation. Let `e` be actual wind, `w` influence wind, and `s` unit span.
Then `lambda_w = sqrt(1 − M_PG² |w × s|²)`, and the local closure is

```text
a0 sin(chi_e + alphaA) = lambda_w cl cos(chi_w + alphaA) + Ks f(cl)
```

Here `chi` is the local section incidence, `a0=4*pi*h` is the incompressible
section slope, and `alphaA` is its zero-lift offset. Current influences use
`w=e`; frozen influences use the body x direction. The equation follows by
integrating an infinite line vortex under the published PG transform. It
requires no additional compressibility multiplier on the input `dCLda`.

The new [verification script](../../scripts/verify-steady-section-limit.py)
checks this oracle against production residual evaluations with prescribed
circulation. It covers positive/negative stall branches, an interior lift
coefficient, asymmetric lift limits, sweep, dihedral, offsets, nonzero PG Mach
and frozen influences. Twelve synthetic states use two finite beam lengths
each: **24 evaluations, zero nonlinear solves**.

All 12 predeclared limit checks pass. Maximum fine-length scaled error is
**3.5632e-6**, measured as `abs(actual−reference)/(1+abs(reference))`.
Multiplying beam length by ten reduces the aggregate error by ten, consistent
with the retained finite-tip effect. These checks cover local cl, perpendicular
speed, bound-point velocity and the complete signed residual. They are not
global CL comparisons, equilibria, or additional ISAE passes.

The first input attempt omitted a required Unit block and was rejected before
any aerodynamic evaluation. Its script, protocol and failure receipt remain
separate. The corrected [complete witness](../../artifacts/isae/steady-section-limit-20261029-r2/report.json)
and [terminal receipt](../../artifacts/isae/steady-section-limit-20261029-r2/terminal-receipt.json)
retain all results. An inaccurate PG-transform code comment was corrected
afterward; the Python AST is unchanged, so no physical algorithm changed.

No new section-law defect was found. The discrepancy with the archived native
results remains open; the new evidence narrows which effects spacing explains.
