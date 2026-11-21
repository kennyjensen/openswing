# AE-3 saved-output integration sensitivity

Changing only the output integration reduces the descriptive 20O-05 mesh difference from **7.14354% to 7.13741%**. The reduction is only **0.0877265% of the original signed discrepancy**. Under the declared saved-state assumptions, this integration choice has a small effect. It does not establish a solver defect or replace the original mesh comparison. The original coupled mesh changes remain **2.0773% and 7.1435%**, both above the unchanged 1% criterion. AE-3 remains pending.

This diagnostic reuses the full coupled circulation derivatives from the existing 160- and 286-interval meshes. It treats circulation as constant within each interval and analytically integrates the centerline force lever arm, quarter-chord couple and direct section moment. It makes no new equilibrium, aerodynamic-kernel, derivative, linear-system or mesh calculation.

| Existing mesh | Original sampled Cl derivative | Alternative integrated Cl derivative | Integrated minus sampled |
|---|---:|---:|---:|
| 160 intervals | -0.000241414230842 | -0.000241395701383 | +1.852946e-08 |
| 286 intervals | -0.000225318510512 | -0.000225314101265 | +4.409247e-09 |

Values use the literal file-control setting and original coefficient normalization. The sampled absolute coarse/fine difference is 1.60957203e-05; the alternative is 1.60816001e-05. Relative to the respective fine result, these descriptive differences are **7.14354%** and **7.13741%**. The change in the signed mesh difference is -1.41202123e-08, or -0.0877265% of the original signed difference. This measures sensitivity to the output functional alone; it does not partition the complete aerodynamic or coupled discretization error.

| Contribution to Cl change | Coarse integrated minus sampled | Fine integrated minus sampled | Change in fine-minus-coarse difference |
|---|---:|---:|---:|
| Centerline force lever arm | +1.75799951e-08 | +4.1723643e-09 | -1.34076308e-08 |
| Quarter-chord couple | +3.90252129e-11 | +9.26208477e-12 | -2.97631282e-11 |
| Direct section Cm | +9.1043892e-10 | +2.27620591e-10 | -6.82818329e-10 |
| Total | +1.85294593e-08 | +4.40924697e-09 | -1.41202123e-08 |

The force integral is unchanged within arithmetic bounds. The sampled gross-to-net roll-moment cancellation ratios are 1.048715 and 1.052201; the alternative ratios are 1.048727 and 1.052204. Signed components are retained because a small net response can magnify relative changes.

The special-case checks require zero base circulation and section Cm, zero angles and rates, no control drag, planar straight intervals, linear chord on each half, constant interval frames, and explicit root and control-break nodes. The actual local normal Mach (0.153620827) is retained in the direct-Cm correction even though the fixed influence PG Mach is zero. The original sampled strip contributions and serialized force, moment and coefficient derivatives are reconstructed before the alternative integral is interpreted. The saved centered-derivative remainders remain in the raw results.

For interval endpoints r0 and r1, the alternative centerline arm uses (r0+r1)/2. The quarter-chord couple uses the average endpoint chord. Direct Cm uses the exact mean chord squared, (c0²+c0*c1+c1²)/3. The original Glauert sample remains the comparator. Arithmetic allowances scale with the absolute physical contributions and the operation count; they are consistency bounds, not continuum error estimates.

Drela explicitly specifies Glauert-angle samples and interval-constant pointwise circulation in §4.2, equations 150–155. Overall force and moment integrals appear in §8.6, equations 220–223. These support the stated sensitivity diagnostic; they do not establish that the production sample should be moved to a centroid. See the [ASWING steady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf). The alternative output is evaluated on circulation solved with the original sampled coupled equations, so it is not a self-consistent alternative discretization or a reference ASWING comparison.

Both analytic integrations completed. The independent audit separately recomputes both integrals using an equivalent chord-square identity and passes 827/827 checks. No production code, runtime bundle or hosted release changed. No original ASWING executable is available. Coverage stays **17 partial / 24 pending / 0 fully validated**.

Next: Check aerodynamic discretization with the saved coarse/fine circulation operators and bound the fixed control-boundary patch error. The saved-output integration sensitivity changes only the output functional and does not resolve the original 2.0773% and 7.1435% mesh failures. Establish convergence, resolve experimental amplitude/incidence/sign, section-control provenance and fixture/stiffness matching, and complete driven-roll and reversal comparisons.

[Machine-readable results](isae-ae3-output-integration.json) · [Previous component checks](isae-ae3-component-checks.md) · [Evidence archive](isae-ae3-output-integration-20261024-evidence.zip)
