# SA-11: fixed-PG and normalization candidates

2026-11-08 UTC. The baseline .75/.78 archive is consistent with a source-backed
alternative using zero global Prandtl–Glauert (PG) Mach, a different reference
area, and section lift slope 6.34. At alpha 0° and 1°, native AVL and OpenSwing
lift/CDi errors are below 0.4%; OpenSwing origin-referenced Cm errors are below
0.2%. **This does not resolve the upper-winglet case or total drag.** The exact
producing model remains unverified, and the primary result stays **163/9,184
at 5%**. SA-11 remains the priority; SA-2 stall work is deferred.

## Independent sources and limits

The [preceding source audit](isae-sa11-allocation-and-speed-20261108.md) found
that the baseline, extension and upper-winglet .75/.78 polars retain
CL/CD/CDi/efficiency within printed precision while Cm changes with true speed.
Their drivers omit `KK`/`MM`. This supports fixed global PG, without proving
its value or recovering the command parser/startup state.

Drela's [user guide](../../reference/aswing_doc.txt:2413) explicitly separates
fixed global PG from speed-dependent global PG, and always applies local
normal-Mach scaling to section Cm independently of that selection. Zero is
the displayed fixed value in the guide; the display does not authenticate the
archived runs. Part I, [p. 35](../../reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf#page=35),
says PG was activated for its discussion and plots, which show .70/.80. Do
not silently extend that statement to the additional .75/.78 files when their
commands and speed dependence differ. The report also omits detailed MSES
section inputs. Original ASWING, modified ASWING and experiment remain distinct.

The original, separate `Wing_tip_up_cant0/wingtip_up_cant0.asw` supplies reference
dimensions **97.67 m², 3.7874 m, 24.852 m**, and main-wing slope **6.34**.
The area agrees with the value inferred from the .75/.78 dimensional outputs
at the supplied density. This study uses those dimensions at one-tenth length:
**0.9767 m², 0.37874 m, 2.4852 m**, with the existing small-scale geometries.
Only coefficients are compared. This neither establishes the historical
geometry/scale/density nor substitutes the distinct cant0 winglet geometry.

Five alternatives were declared before solving: original baseline slope 7.0;
baseline with donor slope 6.34; original extension; upper winglet with file
+4° twist; upper winglet with report −4° twist (Part I, Appendix D, Fig. 40).
The upper cases retain the separately disclosed bundled Joint correction.
Original files are unchanged. No coefficients, vortex cores or parameters were
fitted to the reference output.

## Results at the predeclared two angles

The fixed-PG cases use alpha 0°/1°, true speeds 255/266 m/s, frozen body-x
influences, and normal production stall and local-Mach checks. Each valid
geometry conversion has 64 native horseshoes and identical OpenSwing source
endpoints and control/force receivers. Native AVL supplies vortex loads;
its absent profile/stall/section-moment models are not used to judge total CD/Cm.

Signed percentage errors below compare native AVL with the .75/.78 archived
ASWING coefficients. Ranges cover the two angles; they are not convergence
estimates or full-polar validation.

| Zero-PG alternative | Native CL error | Native CDi error | Production outcome at both speeds |
|---|---:|---:|---|
| Baseline, slope 7.0 | +8.18 to +8.24% | +15.31 to +15.38% | Four computed states |
| Baseline, slope 6.34 | +0.344 to +0.393% | −0.314 to −0.302% | Four computed states |
| Upper winglet, +4° | +8.51 to +11.43% | −13.02 to −9.20% | Four local-Mach rejections |
| Upper winglet, −4° | +4.73 to +6.29% | −27.71 to −17.83% | Four local-Mach rejections |
| Extension | Not admitted as a matched comparison | Not admitted as a matched comparison | Geometry conversion blocked |

For the donor-slope baseline, production absolute errors are at most **0.214%
CL, 0.320% CDi, 0.192% Cm**, and 0.723% efficiency. **Total CD remains
42.70–46.82% high** with the retained baseline profile inputs and native force
receivers. At alpha 0°/1°, respectively, CDp is 0.008855/0.008859 and near-field
vortex CD is 0.002760/0.005024; Trefftz CDi is 0.001935/0.003475. These are
different force definitions, not interchangeable corrections. The archived
moment comparison uses `Cm_origin`, not the alternate moment-reference output.

Two additional alpha-1° controls retain the same alternative geometry and
normalization but set global PG to 255/340.21. Baseline donor-slope native
CL/CDi errors become **+22.07%/+47.27%**; upper +4° errors become
**+33.04%/+38.00%**. Both production states reject local Mach. This is stronger
support for the baseline zero-PG hypothesis, not a recovery of all historical
settings or a winglet repair.

All **nine winglet states** reject local normal Mach, with peaks **1.422–2.192**
at the winglet root. All remain pre-stall: the smallest margin is 11 transition
widths and no strip crosses its lift limits. Their circulation agrees with
native AVL within **0.124%**. These invalid local speeds are a failure of the
tested discrete model, not trustworthy physical supersonic-flow predictions.
No valid production force totals are taken from rejected states.

The earlier [report-twist comparison](isae-sa11-winglet-polar-20261108.md)
matched .70 upper-winglet CL/CDi closely; the same sign plus the present
normalization/zero-PG hypothesis does not explain the additional .75/.78 pair.
The baseline setup finding therefore cannot be transferred to every archive.

![Native AVL errors for the fixed-PG candidates](../../artifacts/isae/sa11-fixed-pg-candidate-20261108/fixed-pg-candidate.png)

[SVG](../../artifacts/isae/sa11-fixed-pg-candidate-20261108/fixed-pg-candidate.svg).
The plot was visually checked and follows the application's color order.

## Conversion blocker and numerical verification

Both predeclared extension cases stop before any production call. Their ASW
position/chord distributions have three ordinary stations and use cubic
interpolation; the exporter joins its sections with straight segments. The
[guide's spline rule](../../reference/aswing_doc.txt:1064) does not make an
ordinary third station a sharp break. Endpoint, force-point and control-point
differences reach **0.866, 0.834 and 0.162 mm**, exceeding the exact-geometry
gate. The native runs and failed mapping are retained. This is an exporter
limitation, not evidence of an OpenSwing aerodynamic error or an archived pass.
The native-field reconstruction discrepancy for these blocked exports is also
retained (up to 1.27e-5 at unit speed); they are excluded from matched-field claims.

All **12 native processes** completed successfully. Of **22 planned production
calls**, four are conversion-blocked; **18 ran**, with eight computed and ten
local-Mach rejections. None timed out. Recorded aerodynamic evaluation time is
0.76 seconds, excluding startup and source checks; this is not browser timing.
All jobs were serial foreground processes with one BLAS thread.

The analyzer verifies all 195 frozen source pins, saved artifact hashes, native
process outcomes, geometry, reference-token mapping, guards and load definitions.
Independent use of the exported native normals reproduces circulation within
6.87e-9 relative error. On the ten matched geometries, exported native velocities
are reconstructed within 1.39e-7 at unit speed and native force coefficients
within 1.67e-16. Production saved velocities reconstruct within **8.42e-10 m/s**.
Native/Python kernel arithmetic is not claimed to be bit-identical.

At fixed PG, the 255→266 pairs reuse the frozen matrices and scale initial
circulation. Changes in Gamma/U and velocity/U are at most 3.13e-17 and
1.65e-14. Computed CL/CD/CDi/efficiency remain invariant within 1e-12, while
local Mach and Cm retain their true-speed dependence. Production equations,
original inputs, primary counts, scope and progress history remain unchanged.

Evidence: [plan](../../artifacts/isae/sa11-fixed-pg-candidate-20261108/plan.json),
[results and verification](../../artifacts/isae/sa11-fixed-pg-candidate-20261108/analysis.json),
[driver](../../scripts/verify-sa11-fixed-pg-candidate.py),
[analyzer](../../scripts/analyze-sa11-fixed-pg-candidate.py).

## Remaining work

Prioritize the pre-stall winglet-junction velocity/force treatment and the
producing input for each archived speed pair. The close circulation agreement
does not justify changing the circulation kernel, bypassing local Mach, or
promoting the candidate to a default. Reconcile the upper .75/.78 geometry and
normalization independently of the .70 result. A future extension comparison
must represent its curved geometry explicitly before claiming matched AVL
conditions. Further global-PG or interval-count sweeps alone will not resolve
the demonstrated junction failure.
