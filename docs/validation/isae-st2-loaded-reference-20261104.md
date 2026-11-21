# ST-2 gravity-loaded modal reference

**14/14 independent mode comparisons pass**: the first seven positive modes of the original horizontal Pazy modal model in vacuum and in still air. Maximum fine frequency error is **0.020398%**, maximum production mesh change **0.071195%**, and every mode-shape comparison passes. This establishes the stated independent-reference scope; the registered native ASWING score remains **0/490**.

Together with the earlier [upright study](isae-st2-independent-refinement-20261104.md), both original ST-2 modal orientations now have seven-mode independent comparisons in vacuum and still air: **28/28 mode comparisons** across the two studies. This does not validate all ST-2 attachments, static cases or native historical settings.

## Full loaded comparison

The literal `02_Modal_Gravity/Pazy_wing.asw` file is unchanged, including both null Weight rows at t=0.558. The production requests use fixed-frame gravity [0,0,-9.81], nominal cosine counts 160/320 plus the required property break, and the full source descriptor operator. Each cold solve retains 20 roots at shift [-0.01,0], all left/right vectors, physical outputs and complete sparse A/M matrices. Still-air density is the original 1.23 kg/m³.

The independent rod uses 384/768 elements on two uniform material intervals meeting exactly at s=0.52 m. The declared frequency, production-mesh and reference-mesh gates are each 0.1%; the shape-assurance gate is 0.999. All settings and gates were fixed before the eight numerical jobs.

| Ordinal | Vacuum reference, Hz | Vacuum OpenSwing N320, Hz | Error, % | Still-air reference, Hz | Still-air OpenSwing N320, Hz | Error, % | Largest N160→N320 change, % |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.70919640 | 4.70920236 | 0.000127 | 4.67608863 | 4.67609477 | 0.000131 | 0.000554 |
| 2 | 29.35452669 | 29.35561980 | 0.003724 | 29.15011703 | 29.15120960 | 0.003748 | 0.013169 |
| 3 | 43.31842321 | 43.31847993 | 0.000131 | 43.22187077 | 43.22192772 | 0.000132 | 0.000545 |
| 4 | 81.57103168 | 81.57944324 | 0.010312 | 81.01137554 | 81.01977848 | 0.010373 | 0.036264 |
| 5 | 116.47597172 | 116.47674787 | 0.000666 | 116.38374511 | 116.38452986 | 0.000674 | 0.002622 |
| 6 | 147.52790486 | 147.52983779 | 0.001310 | 147.24724787 | 147.24917185 | 0.001307 | 0.004734 |
| 7 | 158.15897640 | 158.19105449 | 0.020282 | 157.09638491 | 157.12842967 | 0.020398 | 0.071195 |

Frequency ordinals select the seven positive roots without using native target values. A separate one-to-one shape assignment uses all six physical components: CG-axis displacement and spatial rotation. Its positive kinetic-energy metric includes the section rotary and still-air inertia. All four assignments per medium (coarse/reference, fine/reference, production mesh and reference mesh) agree with the frequency ordinals. The smallest assurance is **0.9999996198**; the largest independent-reference mesh change is **0.009980%**.

The fine equilibrium differs from the independent reference by at most **5.088e-8 m** in CG position and **3.375e-7 rad** in rotation. The coarse comparisons also pass the predeclared 1e-6 m / 1e-5 rad limits. The reference uses the actual gravity-loaded shape, including its approximately 17.295 mm tip sag.

## Independent equations and controls

The new [continuous-rod reference](../../scripts/isae_st2_loaded_reference.py) imports no OpenSwing code. It translates to the common elastic, tension and CG axis and integrates the nonlinear equilibrium by quaternion shooting. Its analytically linearized spatial equations retain initial forces, initial moments, axial extension, both bending directions, torsion, rotary inertia and optional fluid inertia. Midpoint collocation supplies a different discretization from OpenSwing’s endpoint-average assembly.

The complete twelve-variable mixed pencil has a singular inertia matrix. The reference applies A⁻¹B as an ordinary sparse operator, rather than treating the singular matrix as a positive ARPACK metric. Every computed mode is checked against that full pencil. No shape family is omitted or reduced to a fitted spring model. The [derivation](../../artifacts/isae/st2-loaded-reference-20261104/DERIVATION.md) records the equilibrium, prestress tangent, inertia and boundary equations, with citations to the ASWING technical and unsteady formulations.

All **10 focused reference tests** pass in the recorded run. They check exact upright axial shortening, direct kinetic energy in vacuum/still air, loaded tangent response against finite perturbations of the nonlinear gravity equilibrium, unloaded spectra against the separate Hermite energy reference, invariance under a global rotation, and invalid fluid-density rejection. The tangent perturbation error decreases with refinement.

All four production cases also pass the original mass, gravity force, clamp, global balance, fresh equilibrium residual and spectrum/conjugacy checks. All **160 original-pencil left/right eigenvector checks** pass; the largest production backward error is **3.367e-16**, versus **3.445e-15** for the reference. The fine vacuum/still-air production A matrices are exactly equal: added fluid inertia enters M.

## Native comparison and remaining scope

The original real and imaginary printed eigenvalue intervals are still evaluated without rounding, snapping or changing tolerances. The fine vacuum/still-air runs pass **0/28 repeated native component intervals**. Fine vacuum frequency error against the archived ASWING file has median **0.21263%**, maximum **0.70006%**; still-air median **0.07974%**, maximum **0.93774%**. The tiny real components retain their original absolute bounds.

This is consistent with the separate [documented-node study](isae-st2-documented-mesh-20261104.md): coarse uniform forty-node still-air predictions agree with the archived frequencies within 0.012611%, while finer meshes converge toward the independent continuum reference. That is evidence for a historical discretization/setup difference, not proof of the original node array or break bookkeeping. The registered 0/490 score is retained.

Remaining ST-2 work includes the historical mesh and discontinuity interpretation, unresolved exact native comparisons, and the original static files with active out-of-domain attachment stations. The present reference is specific to the common-axis modal wing; it does not establish behavior for all offsets, joints, point attachments, damping, mean airflow or moving frames.

All eight jobs completed serially with one BLAS thread and a 512 MiB address-space cap. The sum of recorded child-process elapsed times is **275.0 seconds**. Production N320 jobs peak below 217 MiB RSS. Assessment reuses the retained outputs and does not rerun solves. This increment changes validation/reference code and documentation; production kernels and the browser bundle are unchanged.

## Evidence

- [Portable assessment with all comparisons and source hashes](isae-st2-loaded-reference-20261104.json).
- [Fixed plan](../../artifacts/isae/st2-loaded-reference-20261104/plan.json), [serial receipts](../../artifacts/isae/st2-loaded-reference-20261104/serial-receipt.json), [reference test log](../../artifacts/isae/st2-loaded-reference-20261104/reference-tests.log), and [saved-result assessment](../../artifacts/isae/st2-loaded-reference-20261104/assess.py).
- [Reference tests](../../tests/test_isae_st2_loaded_reference.py).
- All original requests, full production outputs/matrices, reference shapes/bases and verification reports are retained under `artifacts/isae/st2-loaded-reference-20261104/jobs/`.
