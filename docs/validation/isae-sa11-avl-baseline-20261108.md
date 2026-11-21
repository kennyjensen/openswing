# SA-11: native AVL independently reproduces the baseline loading bias

2026-11-08 UTC. At the archived speed of 240 m/s and incidence 0°/1°, native
AVL and current OpenSwing both overpredict the archived baseline lift and
Trefftz induced drag when using the supplied `wing_alone.asw` section slope.
Changing only that slope from **7.0 to 6.34/rad**, the value independently
specified in the other SA-11 files, brings both quantities within **0.5%** of
the archived values in both solvers.

This is independent support for the earlier
[section-input finding](isae-sa11-section-inputs-20261107.md). It strengthens
the case for a mismatch between the supplied baseline input and the archived
producing configuration. It does not prove which input generated that output.
No original file, production equation or registered comparison changes;
**SA-11 remains 163/4,592 at 5%**.

## Conditions and matching

Four predeclared cases use two angles and two section-slope choices. The only
alternative input is `dCLda`, taken from `wing_extension.asw`; geometry, twist,
zero-lift angle, profile coefficients, section moments and lift limits retain
the baseline values. Native `.avl` files differ only in their `CLAF` entries.
No coefficient is fitted to the archived answer.

The [verified geometry conversion](isae-sa11-avl-conversion-20261108.md) uses
normal-to-streamwise chord conversion, projected zero-lift incidence and one
uniform chord row. There are 64 native span strips, split at the original
property/sweep breaks. Production uses those exact native endpoints and bound/
control sampling stations. All four geometry comparisons agree within
**3.34e-16 m**.

Both solvers use a frozen body-x wake and PG Mach `240/340.21`, approximately
**0.7054466**, rather than the rounded filename label 0.70. The production
case retains density 1.2256, all original profile properties, the default
stall law and the section-normal Mach guard. Native AVL omits profile drag
and section pitching moment; its lift below is consequently vortex lift.
The OpenSwing/reference columns use total CL, including profile-force lift.

All four production cases converge with zero stalled strips. Their minimum
distance to a stall limit exceeds **41.94 transition widths**, their maximum
local section-normal Mach is **0.97659**, and their maximum circulation
residual is **1.07e-15**. These are pre-stall comparisons, unlike some of the
previous linear winglet diagnostics.

## Comparison with the archived ASWING output

Errors are signed percentages relative to the original `wing_alone_Ma_0_70.txt`
rows. CL/CDi targets are 0.236767/0.00283307 at 0° and
0.319483/0.00509469 at 1°.

| Section slope | Incidence | Native AVL CL error | OpenSwing total CL error | Native AVL CDi error | OpenSwing CDi error |
|---|---:|---:|---:|---:|---:|
| Original 7.0 | 0° | +7.894% | +7.359% | +14.500% | +14.522% |
| Extension 6.34 | 0° | +0.405% | −0.115% | −0.225% | −0.207% |
| Original 7.0 | 1° | +7.959% | +7.515% | +14.587% | +14.585% |
| Extension 6.34 | 1° | +0.469% | +0.044% | −0.228% | −0.230% |

The small native/OpenSwing CL difference includes the profile-force lift
absent from AVL. Comparing vortex forces directly, the solvers agree within
**0.0141% in CL and 0.0254% in near-field CD**. Their Trefftz CDi agrees within
**0.0191%**. Relative circulation differences are at most 0.0187%.

Using the exported native tangency normals with OpenSwing's PG influence
operator reproduces native circulation within **6.66e-13 relative error**
after accounting for the previously documented native rounded `1/(4*pi)`
constant. This extends the direct operator comparison to the actual baseline
geometry at nonzero Mach. It does not require changing the production normal
or force definitions to AVL's conventions.

## What this does not resolve

**Total drag still disagrees.** The slope-only alternative deliberately
retains the original baseline's unusual `Cdp=0.01818`, `Cdf=0` inputs. It does
not address the separate profile-property mismatch. Across the four cases,
total CD is still **48.3–67.0% high** on this diagnostic grid. This diagnostic also
uses native section-by-section span sampling, whereas the registered
comparison uses the declared OpenSwing cosine mesh and its generated
receivers. Near-field drag is sensitive to that change: these diagnostic
total-CD results must not replace the registered ones or the earlier
combined-property-transfer results.

The subsequent [sampling isolation](isae-sa11-drag-sampling-20261108.md)
separates endpoint placement from receiver coordinates. On identical native
endpoints, the receiver change accounts for about 94% of the near-field drag
increment. This explains the higher diagnostic-grid total without changing
the previous registered-grid result or establishing the archived sampling.

The scripts prescribe speed and angle but do not retain the original mesh
or startup settings. Their `kk`/`mm` commands occur after defining the
operating-point sequence and before `xx`; the exact original command/parser
state remains unresolved. Frozen body-x influence is the controlled choice
for this native AVL comparison, not a recovered historical setting.

There is also a provenance qualification: the scripts invoke a path named
`ASWING_ISAE_ENAC/bin/aswing`, while the report's Figure 22 and MATLAB legends
label the curves ASW-5.96. A directory name does not identify the executable's
contents. The targets remain the published ASW-5.96 curves; the exact binary
and any enabled ISAE modifications are unverified. The report states that
PG was enabled but does not supply every numerical airfoil parameter.

This evidence supports investigating the archived inputs and discretization
before altering the shared vortex/PG operator. The native generating inputs,
total-drag discrepancy, upper/lower winglet local flow, and Mach 0.75/0.78
normalization conflict remain open. No stall tuning or post-stall repair was
performed.

## Evidence and verification

- [Driver](../../scripts/verify-sa11-avl-baseline.py),
  [saved-evidence checker](../../scripts/analyze-sa11-avl-baseline.py).
- [Predeclared cases and source pins](../../artifacts/isae/sa11-avl-baseline-r1-20261108/plan.json).
- [Complete checked results](../../artifacts/isae/sa11-avl-baseline-r1-20261108/analysis.json).

Four native and four production calls ran serially with one BLAS thread.
Native solves totaled 0.710 s; production aerodynamic calls totaled 0.323 s,
excluding import/setup/provenance overhead. The checker verifies all retained
case artifacts, 149 source/production/status pins, unchanged native input
fields apart from CLAF, geometry correspondence, convergence, stall margins
and Mach validity. An earlier preparation-only directory is retained; its
output-label lookup was corrected before any solve was started there.
