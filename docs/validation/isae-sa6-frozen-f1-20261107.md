# SA-6: control sensitivity with the documented frozen default

2026-11-07. The complete registered F1 scope passes **370/528** original
ASWING comparisons at 5%, using frozen influences, stall strength 40 and
width 0.05. All **88 analytic states** are numerically valid. These are
additional derivative targets; the primary static comparison stays
**470/528**. No production equations, input properties, tolerance or
accepted parameter changes are made by this study.

The subsequent [independent section reference](frozen-stall-reference-20261107.md)
verifies the frozen/current upper and lower smooth transitions and their
control/incidence derivatives. It found no production equation error and
does not change either native-reference pass count.

| Original derivative | Passing checks | Failed-check median error | Maximum failed error |
| --- | ---: | ---: | ---: |
| Axial force CXdF1 | 14/88 | 7.28% | 25.77% |
| Side force CYdF1 | 88/88 | — | — |
| Lift CLdF1 | 78/88 | 6.12% | 7.16% |
| Rolling moment CldF1 | 62/88 | 7.29% | 17.01% |
| Pitching moment CmdF1 | 78/88 | 6.30% | 7.41% |
| Yawing moment CndF1 | 50/88 | 5.52% | 5.94% |
| **Total** | **370/528** | **6.27%** | **25.77%** |

The scope covers the four paired literal models, all eleven original F1
settings and both 64/128 requested meshes. Original zero references and
printed-precision absolute gates remain required. Derivatives are per file
control unit, with fixed base stability axes and reference dynamic pressure.
Historical producer/frame/startup settings remain qualified as in the
registered adapter; this is not a declaration of complete SA-6 validation.

![Native roll and control sensitivity](../../artifacts/isae/sa6-frozen-f1-20261107/roll-control-comparison.svg)

## What the comparison isolates

The roll discrepancy is present in the control sensitivity, not just a
constant moment offset. At the finest mesh, the 15%-chord aileron's CldF1
is 8.04% below the native value at F1=4, then approaches a 3.39% deficit at
F1=44. For the 35%-chord model, the deficit first decreases to about 3.3%,
then grows to **16.87%** at F1=44. Its coarse-mesh counterpart is 17.01%.
That small mesh difference cannot account for the high-deflection discrepancy.

The native static-roll increments also track the printed F1 derivatives.
For each four-unit interval, the audit compares its Cl secant with the
average of its two endpoint CldF1 values. Median absolute differences are
0.026–0.084% across the four native curves. The largest difference is 2.95%
in the sharply curved 35%-chord tail; OpenSwing's corresponding maximum is
2.90%. These finite-interval quadrature diagnostics are not new acceptance
gates or proof of the historical exporter convention. They give no sign of
a gross control-unit or static/derivative pairing mismatch.

## The lower stall transition is a useful lead

A solver-free reader reconstructs each section's circulation coefficient
from the captured bound-vortex velocity and reads the two constant lift
limits directly from every original model: CLmin=-0.4 and CLmax=1.4.
For the published smooth leakage function, its derivative splits into

`f'(cl) = sigmoid((cl - CLmax)/width) + sigmoid((CLmin - cl)/width)`.

Both terms act before the coefficient reaches either printed limit. The
35%-chord model's finest-mesh results illustrate the lower term's onset:

| F1 | Minimum section cl | Maximum lower-term contribution to f' | CldF1 error |
| ---: | ---: | ---: | ---: |
| 32 | -0.01750 | 0.000476 | -3.39% |
| 36 | -0.13930 | 0.005411 | -5.13% |
| 40 | -0.25520 | 0.052355 | -13.32% |
| 44 | -0.31708 | 0.159977 | -16.87% |

These are **OpenSwing section fields**, not recovered native fields. The
correlation locates a sensitive part of the model; it does not identify the
native stall coefficient or prove that the lower term is implemented
incorrectly. The earlier strength-20 agreement remains a separate,
unauthenticated setup hypothesis. Neither coefficient nor width is fitted.

## Independent checks and execution

All 88 derivative bases reproduce the separately retained static solutions
within **4.45e-16** in coefficient value. Scalar matrix replay verifies the
full circulation response and integrated wrench: maximum normalized linear
residual **2.07e-16**, coefficient reconstruction error **6.94e-18**. The
existing direct separation-force checks and numerical gates also pass.
Each completed analytic state uses one cold base and one derivative
factorization, without perturbed production solves.

Four predeclared finest-mesh controls cover the 15% and 35% chord models at
F1=4 and 44. Two centered perturbation steps, 0.001 and 0.0005 file units,
require **16 fresh nonlinear solves**. All **48 scalar derivative checks**
and **eight circulation-vector checks** pass the existing absolute-plus-relative
gates. The largest coefficient-gate ratio is 0.000247, and the largest
circulation-gate ratio is 0.000120. This rules out a derivative/nonlinear
inconsistency at those controls; it does not independently validate the
underlying ASWING model choice.

All work is serial with one BLAS thread and a 768 MiB address-space cap.
The initial eleven-state batch reaches its 60-second limit after saving ten
valid results. Its unpublished attempt may have made one additional physical
call; that uncertainty is retained. After that process exits, smaller chunks
reuse the verified files and finish every missing result. The recorded batch
timings total 262.45 seconds including the initial timeout; the four
perturbation jobs add 14.36 seconds. All worker processes are terminal.
There are 88 completed analytic calls and 16 completed perturbation calls,
plus zero or one unpublished interrupted analytic call.

The [subsequent independent finite-wing check](isae-sa6-frozen-independent-20261107.md)
now verifies all 88 current static/F1 states and isolates a derived native
profile-force discrepancy. Use that constraint to investigate historical setup
and load conventions while retaining all six static and F1 channels.
A correction needs independent mathematical or historical evidence; neither
a new control gain nor a moment scaling is supported by these results.

- [Declared plan and source identities](../../artifacts/isae/sa6-frozen-f1-20261107/plan.json)
- [All comparisons, curve diagnostics and finite differences](../../artifacts/isae/sa6-frozen-f1-20261107/analysis.json)
- [Section transition decomposition](../../artifacts/isae/sa6-frozen-f1-20261107/stall-transition.json)
- [Independent reader](../../artifacts/isae/sa6-frozen-f1-20261107/audit.py)
- [Execution and verification receipt](../../artifacts/isae/sa6-frozen-f1-20261107/verification.json)
