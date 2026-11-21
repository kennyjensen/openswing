# SA-4 solver audit and primary circulation Jacobian

The ordinary cold direct circulation solve now uses the existing analytic
Jacobian, as the seeded and fallback paths already did. The physical residual,
stall law, local Mach limit and convergence gates are unchanged. Cases with
circulation-dependent engine feedback retain numerical differentiation because
the available analytic operator does not include that feedback.

Across 100 direct solves in a fresh SA-1–SA-5 rerun, recorded residual evaluations
fell from **20,811 to 912 (95.6% fewer)**. This is a function-call reduction,
not a measured wall-clock speedup. Matrix construction and other solver paths
still contribute to runtime. The maximum change among saved CL, CD, CDi and Cm
values was **2.22e-16**.

| Case | Current passing outputs at 3% | Primary-direct states | Residual calls before → after |
|---|---:|---:|---:|
| SA-1 | 146/154 | 14 | 4,494 → 159 |
| SA-2 | 50/70 | 10 | 1,562 → 97 |
| SA-3 | 308/308 | 38 | 7,031 → 312 |
| SA-4 | 528/588 | 18 | 1,620 → 161 |
| SA-5 | 154/168 | 20 | 6,104 → 183 |

All 184 registered jobs were rerun on their default meshes: 178 computed and
six failed. Acceptance remains **1,186/1,288**, with no numerical or acceptance
gains or regressions. All six failures retain their preceding SA-4 error
messages. No common valid response changed beyond its original printed
precision. The standard adapter does not retain full circulation vectors, so
this comparison establishes saved-response consistency, not identical branches.
The earlier modified-cosine results remain separate.

## Derivative and implementation verification

Before editing, two actual SA-4 setups were audited at zero, linear-seed and
saved preceding converged circulation states, with tip-localized and asymmetric
directions. Each of **42 state/direction pairs** resolves below the predeclared
2e-6 limit at one of five predeclared centered-difference steps. The worst
best-step scaled discrepancy is **4.11e-8**; larger finite-difference steps
reach discrepancies of about 0.03034. No derivative defect was found in the
existing analytic operator.

An eight-call diagnostic supplied that operator whenever the previously
numerical primary path was entered, without changing production code. Only two
calls entered that path; the other six bypassed it and already used analytic
fallback derivatives. The passing 160-interval, 0.29-degree
control used 12 residual evaluations instead of 332, with outputs identical
to roundoff. All seven failing states remained failures. This showed that
using the available derivative improves efficiency but does not fix the
difficult SA-4 solutions. The production change then connected this same
operator to the ordinary direct call.

All **88 focused tests pass**, including pointwise and Fourier directional
derivatives, circulation-rate terms, comparisons with numerical-Jacobian roots,
powered engine feedback, initialization, continuation, fallback and polishing.
The application builds successfully; all 130 native/public/dist modules agree,
and the local-app ZIP contains the updated kernel.

Two fresh cold direct cases in offline WASM demonstrably invoke the analytic
Jacobian. All **550 physical scalar comparisons** agree with native Python
within **1.78e-12**, against a 1e-9 scaled limit, with zero network fetches.
Residual and fresh prescribed-circulation replay checks pass. The Fourier
case's nonzero local defect is reported separately from its converged projected
residual. These are packaged-runtime witnesses, not a browser UI benchmark or
proof of ASWING parity.

## Remaining SA-4 geometry question

The [technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
Eqs. 154–157, specifies the Glauert structural position and chordwise force/control
offsets. It calls the force location a bound-vortex segment midpoint, but does
not explicitly specify how the completed quarter-chord position is interpolated
on a curved interval. Current nodal endpoints and midpoint offsets are evaluated
independently, so that force point can lie off its own straight bound segment.

![SA-4 tip receiver construction](../../artifacts/isae/sa4-tip-field-20261029/geometry.svg)

The figure projects the first 12 intervals into stream/span coordinates with
unequal axis scales. Blue circles show the separate diagnostic construction;
orange crosses show the production force points. Neither the figure nor the
word “midpoint” alone authenticates a different native ASWING construction.

A predeclared ten-call diagnostic placed the force point on its own unchanged
bound segment using the same Glauert material fraction, then shifted the control
point by the same amount to preserve its downstream offset. All other settings
and gates were fixed. This alternative was **not adopted**:

- At 160 intervals, 4.06° recovers all seven 3% output checks, but local Mach
  reaches **0.99517**. The low-angle control also computes.
- The 4.60° state still exceeds the Mach limit (**1.09437**); 5.13–6.55° still
  fail circulation. The previously computed 7.06° state becomes a solver failure.
- At 320 intervals, both the original and relocated constructions fail at
  4.06°, with normalized residuals about 0.209 and 0.187 respectively.

Only two of the ten calls return valid solutions. All processes were reaped,
with no retries or timeouts. Recovery of one state therefore does not establish
an improved or convergent discretization.

Saved-field reconstruction identifies trailing wakes as the dominant source of
the large tip velocities. In the recovered 4.06° state, the wake contribution
at the worst receiver is approximately `[6.91, -343.98, -97.35] m/s`; one wake
node contributes 363.42 m/s in magnitude. Five earlier accepted modified-grid
fields also replay exactly and show strong wake contributions. The issue
survives relocation onto the bound segment.

The theory explicitly warns of breakdown when a lifting beam aligns with the
freestream. It also restricts finite vortex cores to interactions with other
surfaces; adding a same-surface core would change the documented model. The
present evidence does not justify that change or identify the native root.

The [ISAE report](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/blob/f62943df20e9e4d7d9f50e070477b22426b5f865/5%20-%20Technical%20Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf)
provides more setup information than the earlier Fourier audit stated: SA-2
uses 40 circulation nodes, and SA-3/4 use the same count. That supports a
reported count of 40, while the wording and archived driver differences leave
its correspondence to a particular Fourier `K` setting unresolved. The earlier
[Fourier study](isae-sa4-fourier-refinement-20261029.md) already found that 40
modes alone do not remove the tip-Mach/refinement failures.

Evidence: [fresh paired regression](../../artifacts/isae/sa1-sa5-analytic-newton-20261029/paired-summary.md),
[derivative audit and diagnostic](../../artifacts/isae/sa4-jacobian-audit-20261029/report.json),
[implementation/tests](../../artifacts/isae/sa4-jacobian-audit-20261029/implementation-receipt.json),
[offline WASM verification](../../artifacts/isae/primary-circulation-jacobian-20261029/wasm/README.md),
[build receipt](../../artifacts/isae/primary-circulation-jacobian-20261029/build-receipt.json),
[receiver-geometry diagnostic](../../artifacts/isae/sa4-bound-midpoint-diagnostic-20261029/report.json),
and [saved tip-field replay](../../artifacts/isae/sa4-tip-field-20261029/report.md).
