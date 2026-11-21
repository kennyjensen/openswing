# ST-1 thin-blade modes and corrected mode identification

**Nine of ten thin-blade report entries now match**, bringing the primary
modal comparison to **20/22**. Static comparisons remain **201/201**, for
**221/223** primary matches. These are sampled observables, not 223 independent
models. The original **9/200 archive inventory** remains separate and intact.

Both ideal face orientations were computed on nominal 40/80 meshes using
positive physical mass and the documented coupling stiffness. Accepted
fine-grid frequency errors are below **1.071%**. No production solver equation
or material parameter was fitted to a reference output.

| Label | Report, Hz | OpenSwing N80, Hz | Error | Result |
|---|---:|---:|---:|---|
| 1B, both faces | 1.4 | 1.403270 | 0.234% | Both pass |
| 2B, both faces | 8.14 | 8.138413 | 0.0195% | Both pass |
| 3B, face up | 21.8 | 21.759896 | 0.184% | Pass |
| 3B, face down | 218 | 21.759896 | 90.018% | Printed-value conflict retained |
| 1T, both faces | 59 | 59.631759 | 1.071% | Both pass after identification correction |
| 1F, both faces | 7.6 | 7.623662 | 0.311% | Both pass |

The two face orientations have frequency differences below 1.6×10⁻¹²
relative. Their equilibrium positions are mirrored to within 1.8×10⁻¹⁵ m.
They are two required report rows, not independent tests of two different
material models. Tip sag is 205.69 mm versus the report's 210 mm, a 2.05%
difference. Sag corroborates the setup and adds no extra counted target.

## Physical reconstruction

The [material-source review](isae-st1-material-source-review-20261109.md)
documents the conflicting files and tables. The physical distributed mass is
0.0238 kg/m, supported by ISAE Part III Table 9 and Minguet Table 5.2(a).
The archived negative weight scale is replaced explicitly with positive
gravity scaling. The bend–twist magnitude is 0.00632 N m², consistent with
the original raw ASW entries and Minguet p. 124. The ISAE/raw-file shear
stiffness and axis inertias are retained even where the thesis differs.

The ideal face change is represented by reversing the coupling sign in fixed
axes. A half-turn about span has R=diag(−1,1,−1); transforming the bending
stiffness matrix by R K Rᵀ reverses the c/s coupling and preserves its diagonal
entries. For this straight, centered beam with no other coupling, the two
inputs represent that ideal orientation change. The assignment of a sign to
the historical face names remains unproven, but their identical ideal spectra
make that assignment immaterial to these frequency comparisons. Manufacturing
asymmetry in the experiments is not fitted into the ASWING model.

All raw table values are unchanged. An explicit `End` terminates the empty
Engine block. The model is clamped at its original endpoint, with zero point
mass and zero root twist, then solved under self-weight before fixed-frame
vacuum linearization. Exact historical executable/input reproduction is not
claimed.

## Why the torsion check needed correction

![First torsional mode and its root sign change](../../artifacts/isae/st1-thin-modal-reconstruction-20261109/first-torsion-shape.png)

[SVG](../../artifacts/isae/st1-thin-modal-reconstruction-20261109/first-torsion-shape.svg).

The initial identification rule required the first torsional mode to have
zero internal twist sign changes. That is too restrictive for this bent,
coupled blade. Minguet's discussion on pp. 127–128 explicitly describes a
small negative portion near the root of its first torsional mode. The current
shape exhibits that feature on both meshes. About 77.3% of its structural
shape activity is torsional; 22.1% is in-plane bending.

The reviewed rule selects the lowest torsion-dominant mode without imposing
the straight-beam zero-crossing rule. It keeps the pre-existing activity
threshold and all residual/mesh checks. No reference frequency enters the
selection. The three bending modes retain their zero/one/two normal shape
zeros, and the first in-plane mode retains zero internal displacement zeros.

This is an explicit **post-solve correction to the validation rule**, not a
claim that the original rule passed. Original per-job reports still show
seven accepted thin-blade cells. The [identification review](../../artifacts/isae/st1-thin-modal-reconstruction-20261109/identification-review.json)
documents why the two torsional entries are accepted in the final nine.
No eigenvalue, source target, tolerance or production algorithm changed.

## Numerical verification and remaining work

All ten compared shapes agree across meshes with weighted MAC above
0.9998679. Frequency changes are below 0.545%. A fresh replay of the saved
sparse matrices and both eigenvectors checks 96 eigen-equations, with maximum
action-relative residual 8.57×10⁻¹⁴. All nonlinear equilibria converge.
The four solves took 2.57–4.05 seconds after imports, with one BLAS thread
and the same 512 MiB address-space, 15 s CPU, 25 s wall limits. All 141
production modules are unchanged; browser/build testing remains held.

Two primary modal comparisons remain unresolved:

* **Coupled blade, 1T=95 Hz:** the frequency is reproduced at 95.026 Hz but
  is an in-plane-dominant mixed mode. The literal torsion-family comparison
  is 137.09 Hz, 44.305% different. Native mode shapes are unavailable.
* **Thin blade, face-down 3B=218 Hz:** the report prints 218, while its original
  postprocessor and face-up row say 21.8. The printed 9% error relative to a
  20 Hz experiment also supports 21.8. The literal 218 cell remains retained
  and unpassed; this is not evidence that OpenSwing predicts a physical
  third bending mode an order of magnitude too low.

All five report modal configurations now have computed comparisons. The
remaining work is resolving those reference correspondences and integrating
the mechanics comparisons into the recurring validation workflow. The
existing static and modal agreement strongly supports the implemented beam
mechanics; these results alone do not validate other structural cases or the
browser runtime.

[Runner](../../scripts/verify_st1_thin_modal.py) ·
[saved-result verifier](../../scripts/summarize_st1_thin_modal.py) ·
[plotter](../../scripts/plot_st1_thin_modes.py) ·
[summary](../../artifacts/isae/st1-thin-modal-reconstruction-20261109/summary.json) ·
[plan](../../artifacts/isae/st1-thin-modal-reconstruction-20261109/plan.json).
