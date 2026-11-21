# SA-6–SA-10: stall strength and force-law investigation

Follow-up: [SA-6 with frozen influences and strength 20](isae-sa6-frozen-stall-20261031.md)
passes 528/528 static checks. The SA-6 deterioration described below applies
to current influences. This combined hypothesis still leaves the native
coefficient and derivative comparisons unresolved; defaults are unchanged.

The complete SA-7 aircraft polar reaches **404/406 checks at 3%** when the
existing stall-strength parameter is set to 20, compared with the registered
**395/406 at 40**. All 29 archived angles and both declared meshes are covered.
The remaining two checks are span efficiency at -5°, 3.54% high on both meshes.
All lift, drag, induced-drag and pitching-moment checks pass in this diagnostic.

**This is not a production correction or recovered native setting.** The
technical description recommends strength approximately 40 in section 5.7.
The factor-of-two test was declared before running it; no strength was fitted.
Reducing it to 20 worsens the SA-6 sample substantially. Registered comparison
counts, default settings, section limits, smoothing width and numerical gates
remain unchanged.

## Completed work

The [local-field pilot](../../artifacts/isae/sa7-sa8-force-law-20261031/report.md)
completed 60/60 states: 29 paired archived conditions and two analytic controls.
The [complete SA-7 follow-up](../../artifacts/isae/sa7-sa8-force-law-20261031/sa7-full/report.md)
completed all 58 states, with 52 new calls and six exact pinned pilot reuses.
It recovers nine scalar checks and loses none relative to the registered
full-aircraft baseline. Maximum residual is 1.81e-13, below the unchanged
1e-8 gate. This covers the complete aircraft, not either SA-7 fore-only pairing.

| Predeclared finest-mesh sample | Strength 40 | Strength 20 hypothesis |
|---|---:|---:|
| SA-6, four paired models at controls 4/44° | 28/48 | 8/48 |
| SA-7 full aircraft, six angles | 38/42 | 41/42 |
| SA-8, eleven full/fore-wing conditions | 47/77 | 64/77 |
| SA-10 wing alone, four angles | 21/28 | 24/28 |

Across the pilot there are 23 scalar gains and 20 losses. The table must not
be substituted for full-family counts. It supports investigating native
stall-law/setup differences, but rules out adopting strength 20 as a universal
solution.

## Force equations and SA-8 drag

A separate standard-library reader reconstructs equations (67), (69), (70),
(72), (73), (203) and (204) from saved geometry and velocity fields. All
10,848 lifting-strip states agree: maximum normalized force and moment errors
are 7.02e-18 and 1.74e-18. The maximum local circulation-equation defect is
4.03e-13. The reader also separates circulation, friction, pressure and
stall-pressure forces by beam. Captured velocities are inputs to this check;
it does not independently validate the vortex operators.

For SA-8's literal isolated wing, disabling stall at alpha=-3.9° gives zero
circulation. Its constant section coefficients then require
`CD=(0.006+0.014)*(2*1.09025*0.129)/0.544767=0.0103267819`.
OpenSwing reproduces that value, with negligible lift and zero induced drag.
The separate stall-on control retains the asymmetric leakage tails; it is
not expected to have exactly zero circulation at that angle.

The archived fore-wing drag discrepancy persists with strength 20. At 0°,
CD remains 9.03% low although CDi differs by only 0.18%. At -4°, changing
strength makes CL error fall from 32.3% to 1.14%, and CDi error from 55.0% to
0.054%, while total CD stays about 14.5% low. Thus the lift/stall and total-drag
discrepancies are distinct in these conditions.

The nonzero `radius` in the fore-wing file is not a missing fuselage term:
the user guide explicitly ignores `radius` for a surface beam. Its zero
stiffness entries also denote infinite stiffness under the documented input
convention, so this isolated-wing comparison does not omit a finite elastic
deformation.

## Native-column identity check

The [independent identity audit](../../artifacts/isae/sa7-sa8-force-law-20261031/native-identities.md)
verifies the literal fore-wing geometry directly, including the documented
reflection of the positive-side geometry table. For this single straight,
untwisted wing with zero section Cm and zero moment reference, the published
force and moment formulas give

`CL_circulation=(-4 CM-CDi sin(alpha))/cos(alpha)`.

The reported span efficiency also gives
`abs(CLi)=sqrt(pi Bref²/Sref * CDi * efficiency)`.
With the same circulation quadrature, these magnitudes should agree. They
agree within 5.56e-16 in all 16 retained OpenSwing fore-wing states. In all
18 native rows, their rounding intervals are disjoint; the magnitude difference
is 0.262–0.362%. This is smaller than the provisional 3% acceptance tolerance
and does not itself explain the larger total-drag error.

This conditional discrepancy is not proof that ASWING's solver is wrong.
Different force/Trefftz quadrature, reference conventions or unretained
settings could explain it. It identifies another quantity whose native
definition needs reconciliation. Archived targets and pass criteria are intact.

## Next work

The [SA-7 wake follow-up](isae-sa7-wake-convergence-20261031.md) retains the
non-stalled -5° error under refinement and independent field/wake checks.
For SA-8, reconcile the
fore-only drag and native output identities before changing force equations.
SA-6 needs its own control-region comparison; the opposite response to the
strength change argues against a shared parameter correction. SA-10's moment
reference and tip-junction validity issues remain separate.

The full project goal and validation of the available requested families
remain unfinished; SA-9 remains absent from the upstream archive.
