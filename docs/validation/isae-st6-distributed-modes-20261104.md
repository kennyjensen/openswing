# ST-6 distributed-mass modal supplement

**8/8 independent mode-branch comparisons pass**: the first four branches of the uniform self-weight column at half and one-and-a-half times its continuous critical gravity. Both pole partners are checked. Maximum fine pole error is **0.022439%**, maximum production mesh change **0.067345%**, and every shape comparison passes the declared gates.

This extends the earlier [self-weight study](isae-st6-self-weight-20261104.md), which checked the static divergence threshold and the lowest modal pair near it. It adds three higher distributed-mass modes at each of two loads. It remains an analytical supplement: the [original ST-6 archive](isae-st6-readiness-20261027/report.md) has no `.asw` models or attributable native ASWING outputs. Its five specimen curves are generated from Euler’s formula in `Analysis.m`; they are not native solver results.

## Model and independent reference

The unchanged [self-weight column](../../examples/self-weight-column.asw) is a 1 m clamped/free beam with EIcc=100 N m² and line mass 1 kg/m. Extension, shear, torsion and the other bending direction are exactly rigid. There is no tip mass, intrinsic rotary inertia, airflow or damping. A body-axis gravity vector [0,-g,0] applies compression along the straight +y beam without introducing a transverse trigonometric component.

The independently established Airy threshold is gcr=783.734743894349 m/s². The two declared loads are 0.5 gcr and 1.5 gcr. Compression varies continuously as N(s)=-mu*g*(L-s), reaching zero at the free tip. The upper load is linearized about the unstable straight equilibrium; it is not a post-buckled solution.

The new [independent reference](../../scripts/self_weight_modal_reference.py) integrates cubic Hermite displacement/slope fields using the bilinear forms

```text
K(w,v) = integral[ EI w'' v'' - mu*g*(L-s) w' v' ] ds
M(w,v) = integral[ mu*w*v ] ds
K q = omega² M q,       lambda² = -omega²
```

The root displacement and slope are fixed and the free-tip conditions are natural. Four-point Gauss integration evaluates these element integrals exactly for the stated constant properties and linear preload. No production matrix or solver is imported. All reference displacement/slope coordinates remain in the symmetric energy pencil; consistent distributed mass is retained.

All **eight reference tests** pass: the four exact unloaded cantilever frequencies, the independent Airy buckling threshold, physical scaling and stability at both loads, integrated kinetic energy of a known polynomial field, and invalid parameter rejection.

## All compared branches

Production meshes have 128/256 uniform intervals; reference meshes have 96/192. Every production request uses the full descriptor method at shift [-0.02,0], with eight roots, both eigenvector sides, physical outputs and complete sparse A/M matrices. The gates fixed before the runs are 0.1% for fine pole error and both mesh changes, and 0.999 for shape assurance.

Values below show the representative positive-imaginary or growing pole in 1/s. The complete complex values, including tiny off-axis components, remain in the machine evidence and enter the comparisons without rounding.

| Load | Branch | Character | Reference pole | OpenSwing N256 pole | Error, % | N128→N256 change, % |
|---|---:|---|---:|---:|---:|---:|
| 0.5 gcr | 1 | oscillatory | 24.88871558 i | 24.88883784 i | 0.000491 | 0.001475 |
| 0.5 gcr | 2 | oscillatory | 212.50912577 i | 212.51764878 i | 0.004011 | 0.012033 |
| 0.5 gcr | 3 | oscillatory | 608.98711810 i | 609.05409527 i | 0.010998 | 0.033001 |
| 0.5 gcr | 4 | oscillatory | 1200.64463116 i | 1200.90775265 i | 0.021915 | 0.065772 |
| 1.5 gcr | 1 | growing/decaying | 24.95051524 | 24.95031757 | 0.000792 | 0.002375 |
| 1.5 gcr | 2 | oscillatory | 195.85003931 i | 195.85920910 i | 0.004682 | 0.014047 |
| 1.5 gcr | 3 | oscillatory | 592.63570106 i | 592.70409000 i | 0.011540 | 0.034626 |
| 1.5 gcr | 4 | oscillatory | 1183.68043534 i | 1183.94604376 i | 0.022439 | 0.067345 |

Above critical load, the lowest branch has one growing and one decaying real pole. The next three branches remain oscillatory. Below critical load, all four compared branches are oscillatory. Signed omega² orders the computed branches; native targets or reference frequencies do not select them. This checks the requested eight roots per solve, not the entire finite spectrum of the distributed column.

The reference mesh changes pole magnitudes by at most **0.00001171%**. A separate one-to-one shape assignment uses both displacement and slope in the positive norm integral(w²+L² theta²) ds. Every assignment agrees with the signed-frequency ordinals, including the opposite pole partners. The smallest shape assurance is **0.9999995847**; all four rigid geometry components are exactly zero in the retained production eigenvectors.

Every production case passes fresh equilibrium, straight geometry, rotation, mass, gravity, varying axial preload and global force/moment balance checks. All **64 full-pencil left/right eigenvector checks** pass, with maximum backward error **4.606e-16**. The reference maximum is **2.014e-16**.

## Execution and remaining scope

All eight jobs completed serially with one BLAS thread and a 512 MiB address-space cap. Their recorded child-process times total **126.4 seconds**; each production solve plus verification takes 17–27 seconds inside its runner. Peak production RSS is below 146 MiB. Assessment reuses the saved results without further column solves.

This increment changes independent reference/verification code and documentation. The 137 production kernel modules are unchanged. Earlier browser checks cover the critical-mode supplement; the new four-branch comparison has been run in native Python, with no new browser or release-build claim.

Remaining verification includes post-buckling, broader mode/load coverage and general fixtures. Local skin buckling and material yielding lie outside the published ASWING beam model. Native ST-6 comparison remains unavailable because the original archive supplies no native model/output pairing; none is manufactured from experimental targets.

## Evidence

- [Portable assessment, all branches and hashes](isae-st6-distributed-modes-20261104.json).
- [Fixed plan](../../artifacts/isae/st6-distributed-modes-20261104/plan.json), [serial receipts](../../artifacts/isae/st6-distributed-modes-20261104/serial-receipt.json), [reference test log](../../artifacts/isae/st6-distributed-modes-20261104/reference-tests.log), and [saved-result assessment](../../artifacts/isae/st6-distributed-modes-20261104/assess.py).
- [Reference tests](../../tests/test_self_weight_modal_reference.py).
- Full production results, matrices and both vector sides, and independent reference shapes are retained under `artifacts/isae/st6-distributed-modes-20261104/jobs/`.
