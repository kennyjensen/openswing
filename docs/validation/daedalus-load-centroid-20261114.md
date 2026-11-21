# Daedalus: spanwise aerodynamic force application

Changing the spanwise application point of non-profile aerodynamic forces to
the structural interval midpoint changes the fully coupled yaw amplitude by
only **−0.16082%** at 1.157378 Hz. The result remains **0.0740984 deg/s per F3**,
versus **0.0339862** in Drela's drawing. This conditional quadrature diagnostic
does not explain the Bode discrepancy or establish a production correction.

![Original and conditional responses, and initial component variations](../../artifacts/daedalus-load-centroid-20261114/report/load-centroid.png)

## Source question and diagnostic scope

The [steady description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf)
uses structural interval averages in Eqs. 55–56, printed p. 13. Its aerodynamic
interpolation uses Glauert midpoint coordinates in Eqs. 150–154, pp. 31–32;
Eq. 155 explicitly defines the wind-aligned quarter-chord receiver from that
position. Equations 188–189, p. 38, require consistent global moments and ground
reactions. These statements do not by themselves establish an alternative
finite-grid load centroid.

Current `steady_lifting_wrenches` in `openswing/source_coupled.py` conserves
forces and moments about the aerodynamic sample position when transferring
loads to structural endpoints. The diagnostic adds, for each strip,

```
span_arm = (r0 + r1)/2 - rm
delta_couple = span_arm × force_component
```

Half the added couple goes to each endpoint; the same total goes into global
moment balance. Only moment rows change. Ordinary lift, circulation-rate lift
and apparent force are included on lifting beams 1, 2, 3 and 5. Profile drag is
excluded because its moment already includes this spanwise arm. Aerodynamic
sampling, circulation equations, force magnitudes, intrinsic section couples
and chordwise moment arms remain as in the original model. In particular,
moving apparent-force application without changing its kinematic sampling is
a quadrature experiment, not an independently established physical model.

The original equilibrium is retained with a constant residual offset. The
baseline shift is nonzero: the wing's added pitch couple is 0.380323 lb ft.
Consequently this is not a physical retrim. Moving arms multiplying mean loads
are included by evaluating the added couples at every perturbed state.

An independent constant-force control integrates unit transverse load on a
straight span with nodes `[0, 2, 10]`. Eight-point Gaussian integration and
arithmetic-centroid integration both give moment 50; lumping interval forces
at the Glauert receivers gives 58.944272. This demonstrates a quadrature
distinction on a deliberately coarse control. It is not a native ASWING run
or proof that its aerodynamic samples should be moved.

## Complete feedback and numerical checks

The saved source-airflow/SEGSPL aircraft has 2,044 coordinates. The existing
exact beam/velocity elimination gives a 748-dimensional factor and recovers
the complete state. With `K0 = iω M - A`, each iteration evaluates

```
r = K0 z - B0 - delta_R(z, iω z, 1)
dz = K0^-1 (-r)
```

The additional residual uses fourth-order directional differences at real
and imaginary motions, including native F3 forcing, with step 0.0005.
Acceptance requires absolute residual below 2e−11, relative residual below
2e−8, and next-output relative correction below 2e−7. The gates were not relaxed.

| Evaluated candidate after corrections | Absolute residual | Next-output relative correction | Accepted |
| --- | ---: | ---: | --- |
| 0 | 5.04430e−8 | 3.77706e−3 | No |
| 1 | 1.41476e−10 | 3.11760e−5 | No |
| 2 | 7.29233e−13 | 2.83496e−7 | No |
| 3 | 4.55081e−15 | 3.12407e−9 | Yes |

The accepted state is `update-2/arrays.npz`, independently evaluated by
`loads-3`. The correction calculated by `update-3` measures its remaining
defect; that unevaluated next state is not substituted into the report.
At the same accepted state, step 0.001 gives residual 5.17760e−15 and
next-output correction 3.08536e−9. The two steps' load corrections differ by
9.63357e−16; their output corrections differ by at most 5.25978e−11 relative
to the accepted outputs. All baseline correction replays agree exactly.

## Reference comparison

All numbers below are magnitudes at **1.15737773741517 Hz**. Rate units are
deg/s per native F3 unit; sideslip and bank are degrees per native F3 unit.

| Output | Original | Midpoint diagnostic | Published reference | Amplitude change | Diagnostic reference error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Yaw rate | 0.07421777 | 0.07409842 | 0.03398619 | −0.16082% | +118.025% |
| Roll rate | 0.02421862 | 0.02418038 | 0.03685267 | −0.15789% | −34.386% |
| Sideslip | 0.03031630 | 0.03030749 | 0.02517766 | −0.02905% | +20.375% |
| Bank | 0.00309191 | 0.00308789 | 0.00507383 | −0.12997% | −39.141% |

The plot's component bars are first amplitude variations from 12 separate
right-hand sides at the original response. They are not separate converged
component models. The left panel uses the complete converged feedback above.
This investigation covers one frequency and one mesh, and makes no browser
default claim: the saved source-airflow/SEGSPL policy is explicitly selected
by the diagnostic, whereas the ordinary browser default remains different.

## Consequence and retained evidence

The small effect lowers the priority of further spanwise-centroid experiments.
The next source question is distinct: the unsteady description, printed p. 8,
Eqs. 29–31, defines the physical quarter-chord velocity with an arm along the
section chord, while the steady vortex construction uses a wind-aligned
receiver. Their reconciliation, including self-bound induction, needs review
before any production change. Unsteady Eq. 36 explicitly places both steady
and circulation-rate lift at quarter-chord; that moment arm is already used.

The [driver](../../scripts/check_daedalus_load_centroid.py),
[report and complete numbers](../../artifacts/daedalus-load-centroid-20261114/report/result.json)
and [verification receipt](../../artifacts/daedalus-load-centroid-20261114/verification.json)
retain the calculation. Twelve serial bounded jobs succeeded and were reaped,
with one BLAS thread, 512 MiB address space, 15 CPU seconds and 25 wall seconds
per child. Observed maxima were 2.396 CPU seconds, 4.715 wall seconds and
115.024 MiB peak RSS. There were 46 native residual evaluations. Earlier
jobs retain their original runner snapshots; the main driver subsequently
gained only the report stage. Production modules, literal `dae.asw`, ISAE
fractions and the authoritative source catalog are unchanged. No native
ASWING passes are added.
