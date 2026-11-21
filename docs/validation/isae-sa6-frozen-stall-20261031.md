# SA-6: complete static comparison with frozen influences and strength 20

The combined diagnostic passes **528/528 static checks** at the existing 3%
tolerance: all 44 paired archived operating points, each on 64 and 128 requested
cosine intervals. Every nonzero relative error is below **0.946%**. This uses
frozen jig-geometry influences and the existing stall-law coefficient set to 20.

This is a qualified setup hypothesis, not authenticated historical settings.
The technical description recommends approximately 40 for the stall coefficient;
the paper's equations and the production default remain unchanged. Derivative
and inertia comparisons, and three models without paired exports, are outside
this static result. The registered baseline remains 290/528.

## Complete comparison

| Influence geometry | Stall strength | Static passing checks |
|---|---:|---:|
| Current wind and geometry, registered baseline | 40 | 290/528 |
| Frozen zero-wind jig geometry | 40 | 388/528 |
| Frozen zero-wind jig geometry | 20 | **528/528** |

The [strength-40 frozen comparison](../../artifacts/isae/sa6-frozen-static-20261031/report.md)
recovers 148 scalar checks but loses 50: drag, lift, pitch and yaw improve,
while every roll comparison fails. The remaining fine-mesh roll errors have
median magnitude 5.44% and maximum 8.25%. This confirms the direction of the
earlier frozen-influence study on the current kernel.

Strength 20 had already been tested as a factor-of-two hypothesis in the
[cross-family investigation](isae-sa6-sa10-stall-strength-20261031.md).
With current influences it worsens SA-6's fixed eight-state sample from
28/48 to 8/48. Crossing the same coefficient with frozen influences gives
48/48, and the [complete follow-up](../../artifacts/isae/sa6-frozen-strength20-20261031/full/report.md)
confirms 528/528. No search over intermediate strengths or angle-dependent
parameters was performed. The full run adds 80 calls and reuses eight exactly
matching pinned pilot captures.

| Channel | Passing checks | Median absolute relative error | Maximum absolute relative error |
|---|---:|---:|---:|
| CX, stability-axis axial force | 88/88 | 0.2225% | 0.4308% |
| CY, side force | 88/88 | All native zeros meet the strict absolute gate | — |
| CL, lift | 88/88 | 0.3577% | 0.8783% |
| Cl, roll | 88/88 | 0.8131% | 0.9453% |
| Cm, pitch | 88/88 | 0.3428% | 0.8107% |
| Cn, yaw | 88/88 | 0.1380% | 0.1909% |

These percentages cover all finite nonzero references on both meshes, not
just failed checks. Each of the four chordwise variants passes 132/132.
Native tokens, literal section properties, smoothing width, numerical gates
and comparison tolerance are preserved.

## Source evidence and limits

The [source audit](../../artifacts/isae/sa6-frozen-strength20-20261031/source-audit.json)
retains the relevant manual and theory passages and verifies the original
model, driver and output hashes. The user guide's K menu shows F enabled;
its explanation defines influences frozen at undeformed geometry and zero
wind angles. Steady theory section 4.6 describes the same approximation.
The only original SA-6 driver invokes the 35%-chord model and never toggles F.
The other three chordwise associations use the earlier exact MATLAB/fmat
token bindings. No historical startup trace is recovered.

The native stall strength is not recorded. Agreement across the complete
static set supports the combined hypothesis, but does not identify that
coefficient uniquely or establish that ASWING used exactly 20. In particular,
the full static comparison does not validate the archived derivative exporter.

Independent scalar readers check the published local circulation, force and
moment equations using the retained geometry and velocity fields. The frozen
strength-40 run checks 8,624 strips, with maximum local residual 3.31e−13.
The [complete strength-20 field audit](../../artifacts/isae/sa6-frozen-strength20-20261031/full/local-verification.json)
also checks 8,624 strips: maximum local residual 3.17e−13, normalized force
error 9.65e−18, moment error 2.31e−18, and total wrench error 9.03e−16.
These checks verify the equations for those inputs, not an independent
induced-flow solution or the native setup.

All completed processes are reaped. The first strength-40 supervisor was
stopped after seven results to replace repeated interpreter startup with
persistent workers; two interrupted attempts and their unknown physical-call
counts are explicitly retained. The numerical plan did not change. The
remaining 81 strength-40 and 80 strength-20 calls use persistent batches.

## Next comparison

The [complete derivative follow-up](isae-sa6-frozen-derivatives-20261031.md)
passes 528/528 F1 and 2,780/3,168 state checks across all 44 paired operating
points and both meshes. Pitch-rate discrepancies remain.
These outputs were not used to select the coefficient and can distinguish
a consistent native setup from a static-only agreement. Keep the registered
baseline and the separate diagnostic visible until that qualification is
resolved. SA-7's low-lift efficiency, SA-8's isolated-wing drag and SA-10's
moment/reference and tip-junction issues remain separate work.
