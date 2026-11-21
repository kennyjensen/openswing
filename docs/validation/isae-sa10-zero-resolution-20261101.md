# SA-10 zero-incidence outputs and numerical resolution

2026-11-01. The six zero-incidence states admit a zero-circulation state
inside the existing `1e-8` residual gate. Its **42/42 outputs match the
original printed precision**, including drag and origin CM. This supplies
a numerical-resolution explanation compatible with the archived zeros;
it does not authenticate ASWING's historical stopping rule.

No fully converged solution is replaced. Production equations, stopping
criteria, returned values and registered counts remain unchanged.

## Why the fully converged solutions are slightly nonzero

The three literal models have zero twist and zero section zero-lift offset.
At zero incidence, zero circulation therefore gives exactly zero normal
velocity at the control points. Their stall limits are asymmetric:
`CLmin=-2`, with `CLmax=1.1` for wing alone or `0.9` for the extension and
Louvered. For the documented width 0.05, equation 204 gives

```
f(0) = width * log((1 + exp(-CLmax/width)) /
                   (1 + exp(CLmin/width))) > 0
R(0) = -Ks / dCLda * f(0)
```

The published smooth law consequently has a small nonzero residual at zero
circulation. Solving it more tightly produces a very small negative lift.
The six saved strength-20 solutions have residuals below `5.8e-23`.

| Model | `abs(R(0))`, Ks20 | `abs(R(0))`, Ks40 | Saved fine-mesh lift, N | Saved fine-mesh efficiency |
|---|---:|---:|---:|---:|
| Wing alone | 4.5395e-11 | 9.0790e-11 | −6.9980e-8 | 0.983268 |
| Wing extension | 2.4785e-9 | 4.9569e-9 | −5.6864e-6 | 1.802162 |
| Louvered | 2.4785e-9 | 4.9569e-9 | −5.4480e-6 | 1.609907 |

Both 100- and 200-interval requests give the same zero-state residual for
each model. The Ks40 values follow exactly from the linear strength factor
at fixed zero circulation; they are not additional solver runs.

Efficiency is proportional to `(CLi²+CYi²)/CDi`. Scaling a nonzero circulation
distribution scales its numerator and denominator by the same square, so
efficiency need not approach zero as the load becomes small. Here the saved
CDi values range from `1.86e-21` to `6.88e-18`. Exactly zero circulation has
the existing unloaded-wake reporting convention `efficiency=0` instead.
Clipping small nonzero circulation or efficiency would change the calculation.

## Controlled zero-state evaluation

All six zero-incidence states from the complete three-model strength-20
scope are retained. The only intervention is to prescribe zero circulation
through the existing evaluator API; no circulation iteration is performed.
Literal inputs, geometry, stall law, width, force laws and reference outputs
are unchanged. Every evaluation reports method `prescribed`, zero solver
evaluations, and a residual below the unchanged `1e-8` gate.

| Scope | Native matches at 3% | Matches at original printed precision |
|---|---:|---:|
| Saved fully converged solutions | 32/42 | Not used for this diagnostic claim |
| Prescribed zero circulation | 42/42 | 42/42 |

The ten saved failures are exactly four dimensional-lift checks and six
efficiency checks. The four lift magnitudes just exceed the archive's
`5e-6 N` half-digit tolerance. Lift coefficients pass their own printed
tolerances. The zero-state drag and origin CM also match their original
printed intervals; this is not merely a comparison of zero-valued fields.

This establishes that a solver can stop at the archived zero-load outputs
within the present residual gate while a tighter solve of the same smooth
equations returns the retained small load. It does **not** establish that
the native solver actually did so: its stopping rule, precision and internal
implementation remain unknown. Neither output clipping nor a looser solve
is introduced to gain passes. The substantial nonzero-incidence drag and
junction discrepancies are separate issues.

## Verification

Six prescribed evaluations complete serially in **0.55 seconds after imports**,
with one BLAS thread, no nonlinear solves and no browser jobs. Independent
scalar profile-force and origin-moment integration reproduces the outputs.
Seventy-digit evaluation of equation 204 reproduces the normalized residual
within `1.25e-24`; a separate 100-digit ratio-log evaluation verifies it.
The verifier reparses all seven output tokens from each original 82-column
native row and uses exact rational gates.

Two new regressions compare the small asymmetric leakage value and its
derivative against independent 450-digit arithmetic using a relative-only
tolerance. Four existing Trefftz checks verify the exact-zero convention
and scale-invariant efficiency for very small nonzero circulation. These
**six tests pass in 4.35 seconds**. No production calculation changes.

The qualified complete strength-20 scope stays **1,088/1,134**, including
these ten failures and 36 coarse Louvered drag/CD failures. Registered SA-10
stays **1,256/2,268**. The full project goal remains incomplete.

Evidence: [plan](../../artifacts/isae/sa10-zero-resolution-20261101/plan.json),
[results](../../artifacts/isae/sa10-zero-resolution-20261101/analysis.json),
[native-token verification](../../artifacts/isae/sa10-zero-resolution-20261101/verification.json),
[receipt](../../artifacts/isae/sa10-zero-resolution-20261101/receipt.json).
The equations used are 70, 73, 203–204 and 207–211 of the retained
[ASWING Technical Description](../../.reference/asw_theory.txt).
