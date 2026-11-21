# SA-6 force-output and stall-Jacobian audit

2026-10-31. Neither adding rotational apparent-mass loads to the reported
aerodynamic derivatives nor omitting local-speed chain-rule terms explains
the complete native SA-6 derivative set. The complete equations remain in
production. No registered comparison is promoted by this investigation.

The scope is all 88 saved states: four paired models, eleven controls, and
both meshes, using the separately qualified frozen-influence / stall-strength-20
setup. Its result remains **2,780/3,168 state checks**, including **282/528
pitch-rate checks**. Static and F1 results remain 528/528 each under that setup;
native stall strength is still unverified.

## Apparent-mass output convention

Steady theory equations 84–85 contain a rotational contribution involving
`(V × Omega) · n`, evaluated at the beam axis. It is distinct from the
distributed lift/profile wrench in equations 220–223. The audit independently
integrates the apparent-load derivative at zero base rates, including its
intrinsic couple and force arm. Both relevant acceleration conventions are
checked:

- Hold absolute reference acceleration fixed.
- Hold the body-coordinate velocity derivative fixed; then the absolute
  acceleration changes by `delta_Omega × U`, where `U = -V_freestream`.

The second convention cancels much of the freestream apparent force, but
does not cancel the apparent pitching couple. Consequently, matching one
force derivative more closely does not resolve the moment mismatch.

| Output convention | Raw native matches / 3,168 | Pitch-rate matches / 528 | Gains | Losses |
|---|---:|---:|---:|---:|
| Published distributed aerodynamic wrench | 2,780 | 282 | 0 | 0 |
| Include apparent loads, absolute acceleration fixed | 2,674 | 176 | 7 | 113 |
| Include apparent loads, body-coordinate velocity derivative fixed | 2,762 | 264 | 36 | 54 |

These comparisons do not establish which internal routine produced the
native files. They show that neither proposed output-scope substitution
explains the full archive. Apparent loads remain available separately in
OpenSwing's existing load outputs.

## Complete stall derivative

For fixed chord, differentiating the leakage term in equations 202–203 gives

```text
cl = 2 Gamma / (c Vperp)
d[Vperp f(cl)] = (2/c) f'(cl) dGamma
                + [f(cl) - cl f'(cl)] dVperp
```

The complete implementation retains both the direct change in local speed
and its induced-flow change through circulation. Five intentionally incomplete
linearizations were evaluated only to determine whether an approximate native
Jacobian might explain the discrepancy. Their resulting circulation responses
were then tested against the complete physical Jacobian.

| Linearization | Raw native matches / 3,168 | Pitch-rate matches / 528 | Gains / losses | States failing the complete tangent / 88 |
|---|---:|---:|---:|---:|
| Complete chain rule | 2,780 | 282 | 0 / 0 | 0 |
| Omit all leakage-speed dependence | 1,678 | 352 | 136 / 1,238 | 88 |
| Omit direct speed dependence | 1,655 | 352 | 140 / 1,265 | 88 |
| Omit induced speed dependence | 2,786 | 296 | 16 / 10 | 88 |
| Omit the speed-prefactor derivative | 2,491 | 276 | 4 / 293 | 88 |
| Omit the lift-coefficient speed-denominator derivative | 1,655 | 352 | 132 / 1,257 | 88 |

The six net raw matches from omitting induced-speed dependence are **not
accepted passes**. That response violates the complete tangent at every
state, with maximum dimensionless defect 0.129 versus the unchanged `1e-8`
gate. It also violates the exact fractional-speed scaling `dGamma/du=Gamma`
by up to 2.075%. The complete response satisfies that scaling to 1.21e−13
relative to maximum circulation. The other omissions produce still larger
defects. These results provide no basis for weakening the production Jacobian.

## Verification

The independent straight-wing calculation imports no OpenSwing modules and
reproduces the saved complete coefficient matrices within **1.96e−14**.
The audit covers 25,344 scalar variant/reference comparisons; these are
repeated comparisons against the same 3,168 native targets, not new targets.
A separate verifier checks every original native token, gate, transition,
complete-Jacobian defect and fractional-speed invariant.

Sixteen fresh production solves check the apparent-load calculations at the
15%-chord/4-degree and 35%-chord/44-degree endpoint states, on the finer mesh.
Both acceleration conventions use centered normalized pitch-rate steps
`2e-5` and `1e-5`. All eight derivative comparisons pass for all three output
scopes: distributed, apparent and their total (144 scalar checks).
The maximum derivative error is **3.49e−8**, and the largest fraction of the
predeclared absolute-plus-relative gate is **0.093**. The maximum fresh
circulation residual is **1.77e−14**. All calls return and processes are reaped.

Sources: the retained ASWING steady theory, equations 84–85 and 202–204,
the derivative definitions in 220–229, and the frame-acceleration distinction
in the unsteady extension. Source, implementation and result hashes are
retained with the plans. Physical loads, native targets, settings and
acceptance gates are unchanged.

Evidence: [declared sweep](../../artifacts/isae/sa6-rate-output-audit-20261031/plan.json),
[complete analysis](../../artifacts/isae/sa6-rate-output-audit-20261031/analysis.json),
[fresh perturbation plan](../../artifacts/isae/sa6-rate-output-audit-20261031/fd-plan.json),
[perturbation results](../../artifacts/isae/sa6-rate-output-audit-20261031/fd-summary.json),
[verification receipt](../../artifacts/isae/sa6-rate-output-audit-20261031/receipt.json).

SA-6's native local stall/rate response remains unresolved. SA-7 efficiency,
SA-8 drag and SA-10 stall/junction issues remain open; SA-9 is absent upstream.
The full project goal remains incomplete.
