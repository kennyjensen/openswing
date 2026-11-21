# SA-11 extended wing: remaining pre-stall drag discrepancy

The new force budget narrows the mesh sensitivity to **near-field vortex
drag**. Across eight mesh pairs, that term accounts for **93.76–97.14%** of
the total-drag change. Profile drag changes by at most **0.449%**. The checked
points are well inside the section lift limits, and the stall-leakage drag
coefficient stays below **1.08e-12**.

This explains where the computed mesh dependence occurs. It does not identify
the unrecorded native force samples or prove that the supplied airfoil parameters
match the producing ASWING run. The primary score remains **1,060/9,184**;
these replays and alternative-setting controls add no comparisons.

![Verified drag budget](../../artifacts/isae/sa11-extension-drag-budget-r2-20261108/extension-drag-budget.png)

[SVG](../../artifacts/isae/sa11-extension-drag-budget-r2-20261108/extension-drag-budget.svg).
The figure uses the application color order and was visually inspected.

## Fixed comparison

Retain the original extension file, section properties and reference dimensions.
Use the preceding full-suite minimum spacing, **16.4659927 mm**, unchanged.
The cosine 64/128 requests produce **60/108 actual intervals**. Prescribed
angles are 0°, 1°, 3° and 5° at 240 and 272 m/s: sixteen primary-setting
replays. Four additional controls change only `freeze_influences` at 1°/3°,
on the 60-interval mesh, at both speeds.

All sixteen primary replays reproduce the preceding seven-field results
exactly in the saved floating-point values. All twenty states complete with
maximum normal Mach **0.81523**, maximum circulation residual **5.08e-16**,
and minimum stall margin **11.83 transition widths**. No post-stall repair is
attempted.

| Speed | Alpha | CD error, 60 intervals | CD error, 108 intervals |
|---|---:|---:|---:|
| 240 m/s | 0° | −2.855% | −1.452% |
| 240 m/s | 1° | −4.498% | −2.472% |
| 240 m/s | 3° | −7.249% | −4.236% |
| 240 m/s | 5° | −8.851% | −5.195% |
| 272 m/s | 0° | −3.374% | −1.711% |
| 272 m/s | 1° | −5.278% | −2.907% |
| 272 m/s | 3° | −8.411% | −4.965% |
| 272 m/s | 5° | −10.251% | −6.135% |

Frozen influences reduce the discrepancy by only **2.78–7.14% of its
magnitude** in the four controls, with no gained passing checks. At 272 m/s
and 3°, for example, CD error changes from −8.411% to −7.810%. Thus this
toggle does not explain the discrepancy at the checked points. The historical
startup choice is still unverified.

## Force equations and interpretation

The [authoritative index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) were consulted, and
all eight PDF/text pairs were authenticated. Drela's steady formulation
**Eqs. 64–70, pp. 15–16** specifies bound-point velocity for circulation force
and the separate friction, pressure and stall-leakage terms. The saved strip
forces reproduce these terms independently to **2.85e-14 force units**.
The separate Trefftz definition is in **Eqs. 207–211, p. 49**. The test retains
the production convention: near-field total force and a frozen straight-wake
Trefftz diagnostic are distinct quantities.

The exact bookkeeping identity used in the right-hand plots is:

```text
CD_OpenSwing − CD_archive
  = (CDi_near − CDi_Trefftz)
  + (CDi_Trefftz − CDi_archive)
  + (CDp_OpenSwing − [CD_archive − CDi_archive]).
```

Other force terms are zero for these steady rigid cases. The last bracket is
an **archive remainder**, not an independently measured native profile-drag
coefficient. It includes any native near-field/Trefftz difference. It cannot
be used as an airfoil-drag target or fitted correction.

At 272 m/s, 5°, on the 108-interval mesh, the three terms are
**−0.00632187 + 0.00036222 + 0.00430276 = −0.00165690**. This large partial
cancellation is why agreement in Trefftz CDi does not settle total drag.
Replacing near-field vortex drag with Trefftz would make total drag
**5.26–17.28% too high** across the sixteen primary replays; it is not an
evidenced correction.

The archived extension itself has `CD < CDi` at 10°: the remainders are
−0.0003760 and −0.0007821 at 240 and 272 m/s. These source values further
rule out identifying `CD−CDi` as a positive profile-drag coefficient. This is
a source check only; no higher-angle solve or post-stall adjustment was made.

ISAE Part I **p. 35** says MSES supplied reasonable section parameters but
does not publish their full numerical setup. Its comments about transonic
limitations concern agreement with experiment; they do not excuse a mismatch
against the archived ASWING results. The existing source/setup uncertainty
remains explicit.

## Verification and execution

- [Frozen plan](../../artifacts/isae/sa11-extension-drag-budget-r2-20261108/plan.json)
  and [serial driver](../../scripts/verify-sa11-extension-drag-budget.py).
- [Independent reduction and mesh/toggle analysis](../../artifacts/isae/sa11-extension-drag-budget-r2-20261108/analysis.json)
  authenticates 229 source/artifact pins and all case files. Scalar force,
  moment, normal-Mach, source-token and acceptance reductions pass. Maximum
  coefficient difference is **1.07e-15**; budget closure is **2.69e-17**.
- [Interpretation calculations](../../artifacts/isae/sa11-extension-drag-budget-r2-20261108/interpretation.json)
  retain the hypothetical Trefftz replacement separately from solver outputs
  and preserve the original 10° archive values.
- Twenty unique physical calls, one process at a time, one BLAS thread,
  512 MiB address-space limit, 15 CPU / 25 wall seconds per invocation.
  Peak RSS is **254.18 MiB**; the longest revised invocation is **4.03 s**.
- The first accepted solve completed its reconstruction assertions and saved
  its fields before a NumPy-integer JSON recording error. Its evidence remains
  in [the retained attempt](../../artifacts/isae/sa11-extension-drag-budget-20261108/recording-interruption.json).
  The revised plan authenticates and reuses that solution; only nineteen new
  solves were performed afterward. No completed solve was repeated to repair
  the recorder. Browser/build tests remain under the existing hold.

## Follow-up: curved-beam receiver construction

Four saved 3° states, at both speeds and both meshes, now check the force
receiver against **Drela Eqs. 151–155, pp. 31–32**. The independent construction
starts from endpoint material arc lengths, recomputes the Glauert-angle
average and Eq. 154's weighted endpoint interpolation, and then applies the
quarter-chord offset. It agrees with the production receiver within
**4.45e-16 m**. The published construction is retained.

Three alternative sampling probes keep the vortex endpoints, circulation,
section properties, force measures and control-point leakage fixed:

| Force-point probe | Maximum movement | Change in CD error |
|---|---:|---:|
| Evaluate the exact beam spline instead of Eq. 154's position interpolation | 9.562 μm | 0.123–0.131 percentage points worse |
| Interpolate the bound endpoints with the same Glauert weight | 3.347 μm | 0.0331–0.0347 points worse |
| Arithmetic midpoint of the bound endpoints | 4.352 mm | 1.378–1.832 points worse |

These are fixed-circulation partial-force evaluations, not new equilibria or
complete moment predictions. Each alternative worsens the drag discrepancy
in all four states. The small curved-offset ambiguity cannot explain the
observed several-percent drag error, and an arithmetic-midpoint replacement
would also discard the explicit published Glauert rule.

An independent segment/ray calculation, using the retained AVL algebra in
extended precision with **zero core** and the exact Biot–Savart constant,
reproduces all sixteen sampled velocity fields within **7.73e-15 times
freestream**. Coordinates are rotated into the actual wind frame before the
PG mapping. This is an independent kernel evaluation, not a new native AVL
run; AVL's distinct finite-core law is not silently substituted.

At the unchanged published receivers, **67.81–70.23%** of the near-field
vortex-drag change between meshes comes from the main-wing region, with the
remaining **29.77–32.20%** from the extension. Thus the mesh dependence is not
confined to the small curved tip. Both regions remain part of the force sum.

All four bounded foreground audits completed, with **zero new circulation
solves**. Scalar saved-force reductions close within **3.47e-18 in CD**;
245 source/artifact pins pass verification. The longest audit took 5.83 s
and peak RSS was 258.19 MiB. Primary counts, source files and production
equations are unchanged.

Evidence: [plan](../../artifacts/isae/sa11-extension-receivers-20261108/plan.json),
[field-audit driver](../../scripts/audit-sa11-extension-receivers.py),
[verified results](../../artifacts/isae/sa11-extension-receivers-20261108/verification.json).

This rules out the tested receiver substitutions as a repair. The next
comparison should separate circulation discretization from the unrecorded
native mesh/settings while keeping the minimum spacing and published force
law fixed. The report's recommended circulation-variable range provides an
independent basis for such a test; it does not identify SA-11's historical
mode count. Profile drag, stall parameters and force definitions should not
be adjusted to compensate for the unresolved discrepancy.
