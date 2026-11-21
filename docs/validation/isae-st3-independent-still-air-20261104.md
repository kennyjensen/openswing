# ST-3 independent still-air beam check

2026-11-04. OpenSwing's first three frequencies for all three literal layups
agree with an independent energy-based beam calculation within **0.028%** at
128 intervals. All **9/9** comparisons pass the existing 0.1% numerical check.
The ASWING workbook result remains **8/9**, with the uncoupled first frequency
2.659% above the recorded 3.7 Hz value.

| Layup | Independent frequencies, Hz | Maximum OpenSwing difference, 128 intervals |
|---|---|---:|
| `0_3_90` | 3.798340, 24.261171, 25.912003 | 0.027984% |
| `p15_0` | 3.629611, 22.520066, 26.584063 | 0.023480% |
| `m15_0` | 3.621266, 22.476653, 26.576652 | 0.023484% |

For the outstanding first frequency, OpenSwing gives **3.798389 Hz** and the
independent reference **3.798340 Hz**, a difference of **0.001298%**. Refinement
of this declared mathematical model does not account for the workbook gap.
This supports its implementation; it does not establish which historical
input, setting, version or table entry caused the remaining discrepancy.

The reference uses cubic Hermite bending, linear torsion, real rotary inertia
and compressive self-weight geometric stiffness. Its existing still-air option
adds normal inertia `pi*rho*c²/4` and spanwise pitch inertia `pi*rho*c⁴/128`,
consistent with [Drela's unsteady Eqs. 41–44](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf#page=9).
The reference mathematics imports no OpenSwing physics. The separate source
audit uses the production parser to verify original scaled properties,
geometry and axes before comparisons. No material parameters are fitted.

In the coupled files, the literal zero scale on `Xax` makes the midchord and
the mass/elastic/torsion axes coincide at +0.07 m from the reference axis.
The uncoupled axes coincide at zero. The centered independent fluid model is
therefore appropriate to all three original inputs. The reference neglects
the tiny finite axial shortening and uses a continuous energy formulation;
OpenSwing retains its source box discretization.

Six independent calculations used 96 and 192 elements. Maximum reference
mesh change is **0.001962%**. The retained OpenSwing 64-interval comparisons
pass 8/9; the uncoupled second frequency differs by **0.111839%**, falling to
**0.027984%** at 128 intervals. This coarse failure remains recorded.
Frequency-ranked modes also agree in mechanical shape: minimum fine-grid MAC
is **0.999999686**. This is an independent-model shape check, not an archived
ASWING eigenvector match or resolution of the disputed workbook labels.

All **six** reference tests pass. Two new tests check closed-form bending and
torsion frequencies with fluid inertia, and distinguish fluid inertia from real
self-weight. The full comparison took 3.28 seconds after imports/source-pin
verification, using one BLAS thread. All 172 source/evidence pins were checked
before and after. Existing production results were reused; no production solve
or equation changed. ST-3 remains partially validated.

Reproduce with one bounded serial job:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 nice -n 10 timeout --kill-after=5s 90s \
  prlimit --as=536870912 -- .venv/bin/python \
  scripts/verify-isae-st3-still-air-reference.py --output-dir /tmp/st3-independent-new
```

The output directory must be new.
[Results](../../artifacts/isae/st3-independent-still-air-20261104/assessment.json),
[source pins and settings](../../artifacts/isae/st3-independent-still-air-20261104/plan.json).
