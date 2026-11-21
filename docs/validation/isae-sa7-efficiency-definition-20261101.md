# SA-7: efficiency reporting and mutual-core counterfactual

2026-11-01. A different output calculation can make the remaining two
strength-20 full-aircraft checks pass, but passing those checks does not establish
that calculation as physically correct. The documented Trefftz result and all
registered counts are retained.

## Why the two efficiency checks fail

Independent scalar summation of the saved circulation and near-field forces
checks all 58 states in the complete strength-20 polar. The published definition
in steady equations (207–211) is

`e = (CLi² + CYi²) / [pi (Bref²/Sref) CDi]`.

At −5° on the 128-interval mesh, the circulation-lift magnitude is **0.59535%**
high and CDi is **2.26552%** low relative to the native values implied by this
definition. Their effects compound to an efficiency **3.53997%** high. Both
primitive errors lie within 3%; their ratio need not. The native circulation
lift is inferred from its efficiency/CDi columns and symmetry, not measured
independently or recovered as a circulation distribution.

Using total force lift instead of circulation lift slightly worsens this case.
Using the near-field circulation-force ratio instead gives a smaller error:

| Output calculation | Efficiency at −5°, N128 | Error | Efficiency matches across the 58 saved states |
|---|---:|---:|---:|
| Documented Trefftz definition | 0.382432109 | +3.53997% | 56/58 |
| Total lift with Trefftz CDi | 0.382714546 | +3.61643% | 56/58 |
| Near-field circulation lift and drag | 0.379697410 | +2.79957% | 58/58 |
| Trefftz calculation with mutual cores, below | 0.375838917 | +1.75492% | 58/58 |

The [ASWING steady description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
specifies Trefftz-plane forces for span efficiency. Better agreement alone does
not justify replacing that definition with a near-field ratio.

## A concrete native-output hypothesis

Drela's retained JVL source first computes an inter-surface vortex core, then
explicitly resets it to zero before evaluating the Trefftz wake. See
[jtpforc.f](../../reference/third_party/jvl/src/jtpforc.f), lines 304–318. This is evidence
for JVL's actual calculation, not authenticated ASWING source. ASWING's
description does not state the core handling in its reporting step as explicitly.

The counterfactual carries the existing `max(chord/4, interval length)` core
into infinite wake-filament velocities only between different physical surfaces.
It preserves the saved circulation, geometry, forces, section properties and
all tolerances. No parameter is fitted. A declared three-angle pilot at −5°,
0° and 20° gains a check without losses, triggering the full saved-polar check.
At −5°, CDi changes from 0.0002518393 to 0.0002562572; native CDi is
0.000257677, so the error becomes −0.5510%.

Changing only the reported CDi and efficiency this way gives **406/406** scalar
matches instead of **404/406** in the complete strength-20 diagnostic. An
independent scalar-product quadratic form reproduces the vector-form pilot and
all saved zero-core baselines. Exact rational scoring verifies all 406 decisions.
This is a possible explanation to investigate in the native reporting algorithm;
the native core rule has not been recovered.

## Why this is not adopted

Two identical far-wake traces carrying equal and opposite circulation have zero
net vorticity and must cancel. The receiver-dependent mutual-core rule gives
the same physical point different velocities depending on its surface label:
own-sheet influence is unregularized, while the opposite sheet is regularized.
The far-wake energy therefore no longer depends only on the combined wake.

A 16-strip-per-sheet control gives **CDi = 0.08415514** under this rule despite
exactly zero net circulation. The zero-core result is zero to roundoff. An
independent scalar velocity sum verifies the control. For a simpler one-strip
pair, the spurious coefficient has the closed form

`CDi = 4 Gamma² epsilon² / [pi U² Sref (b² + epsilon²)] > 0`,

where each strip has half-span `b`. The scalar computation agrees with this
formula. This prevents interpreting the alternative as the energy of the actual
combined vortex wake. The numerical agreement is retained as diagnostic
evidence; it is not promoted into production or accepted ISAE counts.

The original full-aircraft registration stays **395/406** at strength 40; the
separate strength-20 diagnostic stays **404/406**. The current fore-only pairing
problem remains separate, so the registered SA-7 family stays **395/812**.
The next investigation must resolve the native circulation/output conventions
without weakening the wake-cancellation requirement.

No aircraft solves, browser tests or full builds were launched. All 42 ISAE
table rows remain unchanged. The full project remains incomplete.

[Definition audit](../../artifacts/isae/sa7-efficiency-definition-20261101/analysis.json),
[declared pilot](../../artifacts/isae/sa7-efficiency-definition-20261101/wake-core-plan.json),
[full counterfactual results](../../artifacts/isae/sa7-efficiency-definition-20261101/wake-core-full.json),
[independent scoring and cancellation verification](../../artifacts/isae/sa7-efficiency-definition-20261101/verification.json).
