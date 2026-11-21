# ST-2 loaded attachment dynamics and input history

**The rigid pylon and explicit rigid extension agree in loaded vibration as
well as static deformation.** Four fresh serial solves compare both models
on two meshes with the original 3 kg tip load. All six compared positive
frequencies agree to less than 7.0e−12 relative; main-wing mode shapes agree
to numerical precision. The primary native-reference result remains **91/91**.
This study adds no ASWING targets and does not establish native handling of
an attachment parameter outside its beam.

## What the public source history establishes

The original static files specify Weight anchors at t=0.558 while the beam
ends at t=0.55. Drela's user manual, Weight block, distinguishes that anchor
from the object's Cartesian coordinates. Steady §3.3, Eqs.87–96 specifies the
rigid arm and load transfer; unsteady Eqs.46–47 includes point-object inertial
forces and moments. These passages establish the physical model but do not
specify endpoint clipping for an out-of-domain input.

The four bending/torsion copies in the case root and `03_Static_Structural`
are byte-identical to their Git blobs in the
[first structural upload](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/8f368bb58255ea7c39390911b21cdae4a5e96363),
dated 26 February 2025. The bending file's old-path history contains that
upload and the
[directory rename](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/a58ec61bbafb22f9915ed4188b34bc35727e05bc)
the following day. The current-path history contains only the rename.
This search recovers no earlier corrected input; it does not prove which
private input or executable generated the archived output.

The downloaded API responses, URLs, retrieval timestamps and checksums are
retained in [the visible reference directory](../../reference/isae-st2-input-history-20261109/summary.json).
The complete initial tree was not truncated. Git blob hashes were recomputed
from the four current local files and compared with that tree. Part III and
both Drela theory documents were also checked against the authoritative
source catalog before preparing the modal study.

## Physical comparison

Both models retain the original main beam, mass distribution, stiffnesses,
clamp, source sensors and two 1.5 kg point masses. The point coordinates are
(0.05, 0.558, 0) m in the jig configuration. The two explicitly derived,
in-domain inputs are the previously reviewed:

* **Pylon:** main-wing anchor at t=0.55; rigid arm (0.05, 0.008, 0) m.
* **Extension:** a massless, infinitely stiff 8 mm beam joined rigidly to the
  original wing tip, with the same masses at its end and a 50 mm chord arm.

The earlier [static attachment study](isae-st2-attachment-interpretations-20261109.md)
showed that these models agree to roundoff and reproduce all 138 archived
internal-force/moment values at their printed precision. The new comparison
tests the gravity-loaded tangent and dynamic mass terms at the same large
deflection. It uses fixed-frame vacuum linearization with the source operator,
not the unloaded or self-weight-only modal configurations in the native scope.

The main beam has 45/90 modified-cosine intervals. The rigid extension has
4/8 uniform intervals. Every model starts a fresh equilibrium under gravity
(0, 0, −9.81) m/s² before linearization. Twelve roots are requested near
−0.1+0i using full shifted inverse iteration. All six positive returned roots
are compared in frequency order, with mutual shape correspondence checked
independently of their frequency values. This is not a complete-spectrum claim.

| Positive root | Pylon, fine mesh, Hz | Extension, fine mesh, Hz | Maximum mesh change |
|---|---:|---:|---:|
| 1 | 0.996435908 | 0.996435908 | 0.00529% |
| 2 | 2.983050280 | 2.983050280 | 0.02906% |
| 3 | 10.896739016 | 10.896739016 | 0.05169% |
| 4 | 58.727818015 | 58.727818015 | 0.13807% |
| 5 | 118.118816456 | 118.118816456 | 0.24991% |
| 6 | 166.994012418 | 166.994012417 | 0.37261% |

Main-wing equilibrium positions agree within 2.11e−15 m, and rotation matrix
entries within 2.34e−15. Both models have total mass 3.205975 kg. The minimum
coarse/fine shape MAC is 0.9999578, using common physical stations, spatial
rotation increments and translations normalized by the unchanged main span.
All predeclared equivalence and 1% mesh gates pass.

## Independent checks and limitations

The original sparse A/M matrices and full left/right eigenvectors are retained.
All 96 action-relative eigen-equation checks pass, with maximum residual
1.62e−12. Returned roots are distinct, conjugate-paired and neutral within
the declared gate. Equilibrium residuals, force/moment balance and total mass
checks pass for all four states.

A separate saved-result audit uses the rigid-arm perturbation relation
δr_point = δr_anchor + δθ × arm. Every extension node follows the main-wing tip
translation and rotation with maximum normalized error 1.58e−12. Matching only
the arbitrary amplitude/phase of the main-wing eigenvectors makes the point
motions agree within 1.70e−12. The point-velocity mass quadratic agrees within
7.88e−10 relative. This checks the 3 kg mass's motion and inertial contribution
through the alternative topology without importing the production solver.

All jobs ran serially with one BLAS thread, 512 MiB address-space, 15 CPU-second
and 25 wall-second limits. Solver time totals 17.14 seconds; complete supervised
process time totals 36.08 seconds. Peak RSS is 131,540 KiB. All children exited
successfully and have terminal receipts. An initial preparation error with a
relative output path occurred before any solve; its script and record are
preserved separately from the corrected frozen replay.

All 141 production modules remain unchanged. The results support the physical
attachment implementation; they cannot resolve the native parser's response
to invalid coordinates. The original inputs, reference targets, 91/91 primary
count, supplementary spanwise count, archive denominator and progress scopes
are unchanged. Browser/build checks remain held.

Evidence: [frozen plan](../../artifacts/isae/st2-loaded-attachment-modes-20261109/replay/plan.json),
[all numerical comparisons](../../artifacts/isae/st2-loaded-attachment-modes-20261109/replay/summary.json),
[independent attachment audit](../../artifacts/isae/st2-loaded-attachment-modes-20261109/replay/attachment-audit.json),
[study runner](../../scripts/verify_st2_loaded_attachments.py),
[saved-result audit](../../scripts/audit_st2_loaded_attachments.py).
