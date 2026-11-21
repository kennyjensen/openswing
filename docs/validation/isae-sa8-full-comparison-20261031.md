# SA-8 complete comparison and remaining drag discrepancy

2026-10-31. Both literal archived models, all 18 incidence angles and both
registered cosine meshes have completed the fixed stall-strength-20 comparison.
The 3% acceptance policy and numerical validity requirements are unchanged.

Follow-up: [isolating body-induced velocity](isae-sa8-body-volume-20261031.md)
raises the full-aircraft diagnostic to 244/252. Independent integration
verifies the published body field; its omission remains a diagnostic and
does not change the counts below or production physics.

| Model | Registered strength 40 | Strength 20 diagnostic |
|---|---:|---:|
| Full aircraft | 211/252 | **220/252** |
| Isolated fore wing | 162/252 | **212/252** |
| Total | 373/504 | **432/504** |

There are 62 gained scalar checks and three losses. The full comparison has
72 successful outcomes: 61 new physical solves and 11 exact, hash-verified
pilot reuses. Strength 20 was fixed before this full comparison, following the
earlier factor-of-two diagnostic. Its native value remains unverified; the
published approximate strength 40 remains the production default. Registered
acceptance counts remain 373/504.

## What remains

The isolated wing passes **every lift, CL, CDi, CM and efficiency check** at
strength 20. Its 40 failed checks are dimensional drag and CD at ten angles
on both meshes, from −6° through 4° with no archived 1° row. Among failed
fine-mesh CD checks, median error is **11.29%**, maximum **15.66%**, all low.
At 0°, CD is 0.01164090 versus 0.0127966, **9.03% low**. Its induced drag
already matches closely; that discrepancy is in the remaining total force.

The full aircraft passes every total-drag check. Its 32 remaining failed
checks occur at −6°, −5°, −4° and −3°. Failed fine-mesh medians are CL 4.81%,
CDi 15.14%, CM 8.78% and efficiency 5.54%. Near-zero lift at −4° makes some
relative errors large: CL is −0.0101855 versus −0.00643162, while CDi is
0.0000174356 versus 0.00000151247. Both values and relative errors are
retained in the [complete results](../../artifacts/isae/sa8-full-strength20-20261031/analysis.json).

![SA-8 full and fore-only comparisons](../../artifacts/isae/sa8-full-strength20-20261031/comparison.svg)

## Force and setup evidence

A scalar implementation of equations (67), (69), (70), (72), (203) and (204)
checks all 10,368 retained lifting-strip states. Maximum normalized force
and moment differences are 2.98e−18 and 1.44e−18; maximum local circulation
equation defect is 5.37e−13. The capture worker separately reconstructs the
complete aircraft force and moment including body loads. These checks use
retained velocity and geometry fields; they do not independently authenticate
the native setup or resolve its induction problem.

The fore-wing deck has constant Cdf=0.006 and Cdp=0.014. The published
force law describes their sum as section profile drag for an unswept wing.
The earlier stall-off control reproduces its analytic CD exactly. In the
seven archived fore-wing rows from −4° through 3°, the inferred remainder
CD−CDi instead follows approximately

`0.012065558 − 0.003203904 × CL`

with maximum regression residual 5.39e−7. This is a descriptive diagnostic
of the archived columns. It is not a fitted correction to OpenSwing and
does not establish that the archived remainder is a separately defined CDp.
A constant omitted drag alone does not reproduce that shape. The conditional
moment/Trefftz identity issue identified earlier also remains unresolved.

The accompanying report, Part 1, PDF page 32, specifies **40 circulation
nodes with cosine clustering** and says the airframe influence was neglected.
The retained full-aircraft deck nevertheless includes a constant-radius body:
radius 0.0645 m, axis x=−0.1 to 0.95 m, z=−0.0645 m. Its fore-only deck has
no body. The two archived shell drivers toggle F; the guide's displayed
initial F=T setting supports the current-influence registered reconstruction.
Actual producing executable defaults and node arrays remain unavailable.

Two bounded setup tests cover both models at −6°, −4°, 0° and 12°, keeping
strength 20 and every other physical input fixed:

| Setup test | Matching current-influence, 128-interval sample | Candidate | Gains / losses |
|---|---:|---:|---:|
| Frozen influences, 128 intervals | 43/56 | 35/56 | 1 / 9 |
| Current influences, 40 intervals | 43/56 | 41/56 | 0 / 2 |

All 16 additional solves converge and terminate successfully. Forty OpenSwing
intervals are a documented-size diagnostic; the report does not recover the
exact native station array or settle native node-versus-interval counting.
Frozen influences reduce several negative-incidence discrepancies but worsen
high-incidence comparisons. For the longitudinal constant-radius body, the
zero-angle frozen flow makes the source and doublet densities vanish under
equation (162). The same option also changes vortex geometry, so this test
does not isolate a body implementation defect. Neither option supplies a
general correction.

## Remaining work

For SA-8, isolate body-volume and wake contributions to the full-aircraft
negative-incidence differences, then reconcile the fore-wing total-drag
definition or producing inputs. Preserve the documented force law while
testing those explanations. For the broader SA-6–SA-10 focus, the SA-6
derivative differences, SA-7 low-lift efficiency and historical fore pairing,
and SA-10 moment convention and tip-flow issues remain open. SA-9 is absent
from the public archive.

Reproducible artifacts:

- [Complete fixed-strength run and force audit](../../artifacts/isae/sa8-full-strength20-20261031/report.md)
- [Frozen-influence and 40-interval samples](../../artifacts/isae/sa8-setup-followup-20261031/report.md)
- [Previous force-law and stall-strength work](isae-sa6-sa10-stall-strength-20261031.md)

No production equations, geometry, native targets or registered pass counts
changed in this investigation. The full project remains incomplete.
