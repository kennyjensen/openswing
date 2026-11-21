# SA-11: transferring minimum spacing to upper and lower winglets

2026-11-08 UTC. The same minimum spacing that completed the upper-only check
has now been applied to the upper/lower-winglet configuration at six prescribed
conditions. **Five states compute complete moments, but only 11/42 scalar
comparisons pass at 5%.** The faster 5° state rejects local normal Mach.
This result identifies remaining input/stall and lower-root issues; it does
not invalidate the separate upper-only **294/294** result or establish a
universal spacing value. The primary SA-11 suite remains **163/9,184**.

## Fixed inputs and reference evidence

The [authoritative index](aswing-authoritative-references.md) and checksummed
source catalog were consulted before preparation. Jan Part I **p.35** qualifies
the transonic comparison and omits detailed MSES parameters. **Figure 22,
p.39** distinguishes ASWING predictions from experiment; the earlier
[paper audit](isae-sa11-reassessment-20261108.md) verifies the .70/.80 archived
tables against its ASWING curves. **Figure 40, p.68**, inspected again in this
[rendering](../../reference/sa11-paper-review-20261108/isae-figure40-p68.png), gives
upper root/tip twist −4° and lower root/tip twist −7°/−11°.

The prepared model uses the existing bundled Joint-station correction and
changes only the four upper-winglet twist entries from +4° to the report's
−4°. Lower geometry, the 70 μm root-height offset, section properties, force
references and physical index 1 remain unchanged. The saved original and
report-derived inputs are distinct. No source file or browser example was
replaced. Drela's User Guide, **Joint** and **Physical index**, remains the basis
for attachment scaling and zero mutual core; no core was introduced.

The mesh transfers the exact prior value **0.0164659927127284 m**, with uniform
32-interval requests on all four winglets and the same 32 explicit main-wing
intervals. Actual counts are **32 + 16 + 16 + 5 + 5 = 74**. Minimum lower-winglet
interval is 19.058766 mm; upper minimum is 16.465993 mm. The shorter lower
beams are coarsened automatically. All main/upper source endpoints and receiver
coordinates reproduce the earlier upper-only geometry within 2e-12 m.

The six points are 0°, 1° and 5°, each at **240 and 272 m/s**, declared before
solving. Density 1.2256, sound speed 340.21, PG Mach V/a, frozen body-x influences,
whole-beam receivers, stall strength 40 and width 0.05 are unchanged. Original
scripts and output tokens were authenticated; both force/coefficient pairs
agree with the literal reference normalization within their printing intervals.
The .75/.78 normalization conflicts remain separate, unmodified work.

## Results

Errors below are absolute relative errors. Rejected states cannot add a pass,
even when a finite force-only diagnostic is available.

| Speed | Alpha | Passing fields | CL error | CD error | CDi error | Cm magnitude error | Maximum normal Mach |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 240 m/s | 0° | 5/7 | 2.81% | 7.22% | 4.90% | 4.42% | 0.70337 |
| 240 m/s | 1° | 1/7 | 5.50% | 9.45% | 10.51% | 8.07% | 0.79984 |
| 240 m/s | 5° | 1/7 | 36.42% | 7.50% | 58.58% | 41.30% | 0.91027 |
| 272 m/s | 0° | 3/7 | 3.28% | 8.91% | 6.08% | 5.10% | 0.83942 |
| 272 m/s | 1° | 1/7 | 7.58% | 10.08% | 14.86% | 10.75% | 0.95416 |
| 272 m/s | 5° | 0/7, rejected | Unavailable | Unavailable | Unavailable | Unavailable | 1.07488 |
| **Total** | | **11/42** | | | | | |

The seven fields are dimensional lift/drag, CL, CD, CDi, origin-referenced Cm
and span efficiency. CL, CDi and moment magnitude are low; total drag is high.
All five accepted efficiency comparisons pass. At the rejected point the
retained force-only diagnostics have CL 40.14% low and CD 5.77% high; these
are explicitly unavailable as complete-state comparisons.

![Archived curves and the six production samples](../../artifacts/isae/sa11-two-winglet-spacing-20261108/two-winglet-spacing.svg)

## A distinct stall-input issue

The source upper/lower file explicitly sets **CLmax = 0.8 on every beam**.
The upper-only file omits that column and parses to **CLmax = 2.0**. Both have
CLmin = −2 and lift slope 6.34/rad. This is an actual input difference, not a
newly selected tuning parameter. The report does not give the numerical
section limits needed to authenticate the producing model.

Independent evaluation of Drela steady **Eqs. 202–204, pp.40–41** on the saved
states confirms substantial transition leakage before the returned section CL
crosses 0.8. The table gives the maximum `Ks * fstall / dCLda`, converted from
radians to degrees: an equivalent tangency leakage, not an aircraft incidence.

| Alpha | Equivalent leakage, 240 m/s | Equivalent leakage, 272 m/s | Leakage contribution to CD, 240 / 272 m/s |
|---:|---:|---:|---:|
| 0° | 0.0381° | 0.0780° | 0.000000169 / 0.000000668 |
| 1° | 0.4722° | 0.7627° | 0.00002865 / 0.00007543 |
| 5° | 5.1685° | 5.6573° | 0.00801448 / 0.00974987 |

The largest 1°/5° leakage is on the main wing. Every section's final CL is
below 0.8, so the existing `stalled` flag is false; that flag alone does not
establish negligible stall-model influence. The smooth Eq.204 transition and
its pressure-drag term are active. The faster 5° drag decomposition is a
force-only diagnostic because its moment is undefined.

At 240 m/s, archived CL slopes are 0.09322/degree between 0°–1° and
0.09357/degree between 1°–5°. The corresponding production secants are
0.08121 and 0.03245. At 272 m/s the archive is 0.10030/0.10037, versus
0.08086/0.02946 in production. This is evidence of a possible producing-input
or stall-setting discrepancy, not proof of which historical setting was used.
No stall parameter was changed and no post-stall repair was attempted.
The 0° drag discrepancy remains when leakage is negligible and needs a
separate explanation.

## The remaining root failure is dominated by the lower strip's own wake

At 272 m/s, 5°, two lower-root sections reject. At the worst left root:

- The root ray belongs to that lower strip itself, rather than a nearby
  main-wing ray. Its normal distance is **4.054150 mm**; the receiver lies
  2.222411 mm downstream of the ray origin.
- That ray contributes **333.3774 m/s**. Total wake contribution has magnitude
  341.3224 m/s, and the total bound-vortex contribution is 66.2505 m/s.
  These vector magnitudes must not be added as scalar velocities.
- The closed-form, zero-core semi-infinite-vortex expression, with the same
  PG coordinate stretch, reproduces the recorded ray velocity within
  **2.85e-14 m/s**. The code is evaluating this close encounter consistently;
  the local result is not a reliable physical supersonic-flow prediction.

Minimum material spacing limits node crowding on each beam. It does not
guarantee a specified Cartesian distance from a swept strip's wake, nor
authenticate the historical discretization. The transferred spacing value
therefore does not by itself complete the upper/lower case. No automatic
64-strip requirement, vortex-core change, root translation or Mach bypass
has been added.

## Verification and next work

All six serial foreground jobs finished normally, each with one BLAS thread,
512 MiB address-space, 15 CPU-second and 25 wall-second limits. Recorded work
totaled 15.15 seconds, longest 3.46 seconds; peak RSS was 235.09 MiB.
The first preparation attempt had a field-count assertion corrected before
the plan was frozen or any solve ran; no numerical result was discarded.

The independent checker authenticates **185 source pins**, original table
Git/SHA identities, the four explicit model edits, all saved artifacts, and
all comparison decisions. Scalar force coefficients agree within 2.23e-16,
Cm within 1.68e-14, normal Mach within 1.12e-16. Reconstructed section-force
vectors agree within 2.28e-13, and control-point normal velocity minus the
independently evaluated stall leakage has a normalized residual below
2.03e-13. Rejected moments remain unavailable with NaN arrays, not zero loads.

The next useful comparison is the **0° upper/lower case**, where leakage is
negligible: audit lower-root force/receiver treatment and the documented
section inputs against the archive. Resolve the CLmax/linear-polar conflict
before using higher-angle errors to change aerodynamic equations. The user's
post-stall deferral remains in effect. No production equation, default,
reference target, primary comparison scope or count changed in this study.

- [Plan and source pins](../../artifacts/isae/sa11-two-winglet-spacing-20261108/plan.json), [prepared model](../../artifacts/isae/sa11-two-winglet-spacing-20261108/model.asw), [exact mesh](../../artifacts/isae/sa11-two-winglet-spacing-20261108/mesh-import.json).
- [All six results](../../artifacts/isae/sa11-two-winglet-spacing-20261108/analysis.json), [independent verification and decomposition](../../artifacts/isae/sa11-two-winglet-spacing-20261108/verification.json).
- [Serial driver](../../scripts/verify-sa11-two-winglet-spacing.py), [saved-field checker](../../scripts/check-sa11-two-winglet-spacing.py), [plot generator](../../scripts/plot-sa11-two-winglet-spacing.py), [PNG](../../artifacts/isae/sa11-two-winglet-spacing-20261108/two-winglet-spacing.png).
