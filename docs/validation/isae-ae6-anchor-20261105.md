# AE-6: first declared airflow comparison

AE-6 now has a current-code conditional comparison: **22/24 scalar components
pass the 5% native-reference allowance**, across nominal cosine32/64 meshes.
This covers six archived complex roots at one commanded speed and one nacelle
position. All twelve distinct native scalar cells are computed on both meshes;
no missing output is omitted from this anchor's denominator.

The two failures are the lowest oscillatory frequency. The archive gives
**3.3632329/s**; OpenSwing gives **2.0334215/s** on the coarse mesh and
**1.9370836/s** on the fine mesh, errors of **39.54%** and **42.40%**.
Every other fine-mesh component is within **0.682%**, with the zero imaginary
component of the real pole passing its original absolute precision gate.

| Native ordinal | ASWING real, imaginary (/s) | Fine OpenSwing real, imaginary (/s) | Components within allowance |
|---:|---|---|---:|
| 1 | −25.040334, 3.3632329 | −25.1096151, 1.9370836 | 1/2 |
| 2 | −4.4256715, 101.75452 | −4.4445266, 101.6966379 | 2/2 |
| 3 | −3.4571733, 187.75428 | −3.4336161, 187.5945922 | 2/2 |
| 4 | −8.3639375, 355.56460 | −8.3788175, 355.5359492 | 2/2 |
| 5 | −396.44617, 0 | −394.4981081, 4.39e−13 | 2/2 |
| 6 | −8.3065192, 542.51439 | −8.3284670, 541.5769331 | 2/2 |

## Original files and scope

The immutable archive contains six AE-6 modal tables: Weight0, Weight7a,
Weight7c, Weight7d, Weight7e and Weight7f. Their **1,674 complex rows / 3,348
scalar cells** are retained in the plan. The anchor compares twelve distinct
cells; **3,336 other native cells remain outside this comparison**. Other
nacelle model variants and aggregate CSV outputs also remain to be covered.

All eighteen model/driver/modal-export files for those six tables are
**byte-identical to the corresponding ST-4 files**. The Weight0 copies correspond
to ST-4's root simulation directory. Thus the previous ST-4 airflow work and
this AE-6 anchor share native evidence; counting both families does not make
these independent targets. The full AE-6 source inventory is also pinned in
the machine-readable report.

The original Weight7a driver invokes `7a_b17.asw`, explicitly sets IAS120 on
point1 and IAS120.5 on point2, selects anchored constraints, commands all-point
execution, and requests `NN16` near `0+300i`. This anchor preserves the literal
model, including its **zero reference area**; dimensional loads and modes are
valid while area-normalized coefficients remain unavailable.

Declared current choices are fixed perturbation frame, zero alpha/beta and
Earth attitude, density1.0771417304, gravity9.81 toward −z, PG Mach zero,
pointwise circulation, lag enabled, current influences, stall40/0.05 and the
existing quarter-chord wake core. Exact historical startup, node placement,
aerodynamic flags and native mode shapes remain unrecovered.

The comparison uses the same injective minimum complex-distance correspondence
as the previous identical ST-4 airflow pilot. It does not authenticate native
mode identity. All sixteen selected roots, full matrices and left/right vectors
remain available, including real and negative-frequency roots.

## Numerical verification and remaining work

Both fresh solves pass **39/39 numerical/source checks**, including the full
left/right eigenvalue equations, mass normalization, root-clamp motion, original
inputs and implementation pins. A separate verifier repeats **64 full-pencil
residual checks and 32 mass-pair checks**, and independently reconstructs the
native decimal comparisons. All checks pass.

The existing **0.1% numerical component mesh criterion passes only 5/12**.
The 5% native allowance does not establish spatial convergence. The slow mode's
frequency discrepancy and the remaining mesh changes stay open. These results
do not validate a flutter boundary or a whole family.

Nine new source/setup tests pass. Separately, six [frame-equation tests](isae-ae4-frame-constraints-20261105.md)
show that adding prescribed-acceleration coordinate integrators preserves
nonzero wing poles under the stated assumptions. These fifteen tests establish
their respective invariants and source contracts, without changing production
equations.

The coarse solve saved its complete result before a final hash-check bookkeeping
typo interrupted reporting. The original helper and failure log are retained.
The corrected assessment uses that saved result with **zero repeated solves**.
The fine run completes normally; its recorded solver-call time is **20.82 s**,
excluding startup, export and auditing. The coarse solver time was not retained
and is not reconstructed. Each numerical job ran serially with one BLAS thread,
a 90-second cap and a 512/768 MiB address cap for coarse/fine jobs. There were
no new browser runs or production-kernel changes.

The shared AE-6 adapter remains unfinished. The next coverage task is to carry
the complete inventory and declared executable scopes into the shared runner,
preserving original rows, duplicate-source qualifications and missing settings.
Eleven families still lack shared adapters. Full ASWING implementation remains
active and incomplete.

- [Machine-readable independent audit](isae-ae6-anchor-20261105.json)
- [Reproducible anchor helper](../../scripts/verify-isae-ae6-anchor.py)
- [Coarse report](../../artifacts/isae/ae6-anchor-20261105/n32/report.json)
- [Fine report](../../artifacts/isae/ae6-anchor-20261105/n64/report.json)
- [Independent verifier](../../artifacts/isae/ae6-anchor-20261105/verify-evidence.py)
- [Source/setup tests](../../tests/test_isae_ae6_anchor.py)
