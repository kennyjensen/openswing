# AE-4: first flutter crossing on two meshes

Both declared meshes reproduce the archived undeformed-wing **69–70 m/s
flutter bracket**: the selected oscillatory modes decay at 69 m/s and one
grows at 70 m/s. All four new modal solves pass their 56 physical/source
checks. **20/24 native eigenvalue components pass at 5%.** The four critical
real components still fail; the matching speed bracket does not erase them.

Together with the retained [40 m/s anchors](isae-ae4-refinement-20261105.md),
the conditional comparison is **32/36** across three speeds and two meshes.
These are 18 distinct native scalar targets repeated on two meshes. This is
progress on the first instability, not full AE-4 validation or a shared-runner
registration. No production equation, material property or default changed.

The literal original `2-Flutter_Undeformed/Pazy_wing.asw` and `alpha_0.sh`
remain the inputs. Nominal 40/80 cosine intervals produce 41/81 elements.
The request retains the solid wall, fixed frame, zero alpha/beta, file sea-level
density 1.23, Mach zero, aerodynamic lag, updated influences and source moving
airflow structural operator. Every solve keeps the original `NN 4` search and
complex shift `0 + 200i`, with the complete descriptor and all clamp equations.
This is a local selected spectrum, not a census of every aircraft mode.

The operating-index qualification remains important. The literal insertion
stack maps commanded IAS to native index `IAS + 1`: these comparisons use
indices 70 and 71. The author's MATLAB helper instead labels the index itself
as speed. No correspondence was selected by agreement. Historical startup,
node placement and aerodynamic flags remain unconfirmed, as recorded in the
[original setup audit](isae-ae4-wall-modes-20261105.md). At the declared density,
IAS equals TAS using the file's own sea-level reference.

| Nominal intervals | IAS (m/s) | Native critical real part (1/s) | Current critical real part (1/s) | Relative error | Components passing |
|---:|---:|---:|---:|---:|---:|
| 40 | 69 | -0.17807850 | -0.09116090 | 48.81% | 5/6 |
| 40 | 70 | +0.63928722 | +0.72824345 | 13.91% | 5/6 |
| 80 | 69 | -0.17807850 | -0.12546391 | 29.55% | 5/6 |
| 80 | 70 | +0.63928722 | +0.69693352 | 9.02% | 5/6 |

All frequencies pass; their maximum error is 0.1894%. The failed real-component
errors have median 21.73% and maximum 48.81%, corresponding to absolute
differences of 0.0526–0.0890 1/s. No near-zero tolerance, complex-root norm or
frequency-only criterion replaces those component comparisons.

Linear interpolation of the critical real part between the same two speeds
gives the following diagnostics. These are interpolated estimates, not neutral
states found by an additional solve; the observed bracket remains 1 m/s wide.

| Data | Interpolated onset IAS (m/s) | Difference from native estimate | Interpolated angular frequency (rad/s) |
|---|---:|---:|---:|
| Archived ASWING, declared index map | 69.217869 | — | 210.077302 |
| Current 41-element mesh | 69.111253 | -0.106616 m/s (0.1540%) | 210.188823 |
| Current 81-element mesh | 69.152559 | -0.065310 m/s (0.0944%) | 210.040146 |

Refinement changes the estimated onset by 0.04131 m/s. At the two sampled
speeds it changes the critical real part by 0.0313–0.0343 1/s and frequency by
at most 0.0455%. Mechanical-coordinate mode assurance across 69–70 m/s is
0.99768 on both meshes, supporting continuity of the computed critical mode.
No archived mode shape is available to establish native shape identity.
All 16 checks of the selected modes' root displacement, rotation, velocity and
angular rate pass; the largest scaled clamp defect is 7.01e-17 against 1e-8.

A separate, prospectively specified differentiation-step check repeats only
the 40-interval, 69 m/s case at `5e-6` instead of `1e-5`, keeping the full
pencil. All 14 physical/source checks pass. The maximum relative change among
the four selected roots is 1.12e-11, and the critical real part changes by
2.35e-10 1/s. This is far below its native discrepancy. The default remains
`1e-5`; the diagnostic adds no independent reference targets or credited passes.

The unstable 40-interval, 70 m/s request also passes the actual built offline
WASM worker: **10 gates and 1,281,454 numeric comparisons**, including the full
base, both complete matrices, all selected eigenvalues and independent left/
right pencil checks. There are no offline network requests or page errors.
The worker solve including matrix export took 24.24 s in this run; that is not
a controlled performance benchmark. UI control selection is outside this check.

The reproduction helper now accepts `--speed` for original commanded IAS
1–108. It pins the original sources against the manifest, verifies the literal
insertion order and keeps missing modal comparisons unavailable. A real native
pole has no authenticated branch mapping in this helper and remains required
without a guessed match. All 15 new scope tests pass.

With the original reference cache present, run one new directory at a time:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/verify-isae-ae4-wall-modes.py NEW_FOLDER \
  --panels 40 --speed 69
```

The complete fine-mesh matrix export uses the previously established 768 MiB
process address limit; the coarse jobs use 512 MiB. All jobs are serial. The
full speed/incidence sweep, later flutter branches, divergence/real-pole
mapping, finer neutral-speed resolution and shared-runner registration remain
open. The four critical damping differences and historical setup questions
remain unresolved.

- [Machine-readable comparisons, brackets and verification](isae-ae4-crossing-20261105.json)
- [Prospective four-job plan](../../artifacts/isae/ae4-crossing-20261105/plan.json)
- [Saved-result assessment](../../artifacts/isae/ae4-crossing-20261105/assess.py)
- [Difference-step diagnostic](../../artifacts/isae/ae4-crossing-20261105/step-refinement.py)
