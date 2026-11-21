# AE-2: geometry derivative accuracy and a longer verified branch

The negative-coupling wing at IAS 17 m/s now has verified positive-deflection
states through **2.6875°**, on nominal 160 / actual 161 intervals. The new work
identifies a shared error in the original one-sided geometry derivatives. Using
the existing fourth-order centered calculation reduces the measured directional
error from **19.83% to below 0.003%** at the captured difficult trial.

This is a diagnostic improvement, not a completed native comparison. Both
centered attempts at 2.75° still stall. The 5° mismatch remains open, production
sources/defaults are unchanged, and the primary count remains **708/2,200 at 5%**.
No stiffness, airfoil, incidence, geometry or force law was fitted to the target.

![Derivative accuracy, damping and branch continuation](../../artifacts/isae/ae2-centered-audit-20261110/derivatives-and-branch.png)

## What the derivative checks establish

The [earlier trace](isae-ae2-incidence-staged-20261110.md) reached 2.5° but stalled
on the next quarter-degree step. Its saved 2.75° trial has full residual
**1.1587853e−4**, far above the unchanged **1e−12** physical acceptance gate.
It is explicitly retained as an unconverged diagnostic, never an accepted seed.

At that trial, the original full-pose forward stencil and the complete moving-
geometry decomposition have relative matrix difference **1.966e−10**, yet their
Newton directions differ by **0.01844%**. That exceeds the predeclared 0.01%
direction gate; its failed comparison is preserved. Both linear systems are
solved accurately, with maximum linear residual below 1e−14.

Agreement between these two assemblies was insufficient because they share
one-sided geometry differences. Independent centered differences of the full
physical residual along their Newton directions reveal about **19.83% relative
directional derivative error**, stable across perturbation sizes 1e−4–1e−6.
Perturbing the unknown blocks separately locates almost all of that derivative
defect in **geometry columns feeding nodal force and moment equations**. The
circulation, internal-wrench and reaction columns have much smaller defects.

The geometry-block defect is only about **0.00936%** of that block's derivative
norm. Cancellation between the large block contributions amplifies its impact
on the much smaller full Newton derivative. This explains why a tiny relative
matrix difference does not guarantee a useful Newton direction here.

The candidate uses the existing complete geometry decomposition with a
fourth-order centered stencil and the same 1e−6 geometry step. It retains the
moving induced-field derivatives, all matrix blocks and the exact beam
elimination. Independent checks on its resulting direction give:

| Independent directional perturbation | Original forward error | Centered geometry error |
|---:|---:|---:|
| 1e−3 | 19.8340% | 0.0001356% |
| 1e−4 | 19.8303% | 0.0000584% |
| 1e−5 | 19.8303% | 0.0003308% |
| 1e−6 | 19.8303% | 0.0029850% |

The centered candidate passes its declared 0.01% relative gate on the two
smallest perturbations. Error growth at the smallest perturbations is consistent
with cancellation/roundoff. This checks these directions at this trial; it does
not establish every column at every state.

The resulting Newton direction norm drops from **4.1833 to 0.2899**. At the
same trial, the original direction first decreases the physical residual after
**11 halvings**, outside the original search's zero-through-eight range. The
centered direction first passes after **four halvings**, an allowed 1/16 step.
No merit threshold or search limit was changed. Centered assembly takes
**1.013 CPU seconds and 74 residual calls**, versus **6.517 CPU seconds and 974
calls** for the original full-pose stencil at this trial. These are local Python
assembly measurements, not browser or complete-solve benchmarks.

## Verified continuation and retained failures

Both iteration matrices and the separately assembled final matrix use the
centered option in this diagnostic runner. A converged checkpoint is accepted
only after the original full-matrix rank check and independent physical checks.
The 2.5° control reproduces its earlier complete state and all four sensor
outputs; **21 control/physical checks** pass. Two new states each pass **19
physical checks**, for **59 checks in this centered continuation study**.

| Commanded beta | Sensor Earth Y (m) | Heading (degrees) | Sensor speed (m/s) | Sensor flow angle (degrees) | Full residual |
|---|---:|---:|---:|---:|---:|
| 2.5° repeated control | +0.186472992 | +14.3207523 | 16.9918029 | −12.7982527 | 4.214e−14 |
| 2.625° | +0.192973288 | +14.8077058 | 16.9911598 | −13.2076607 | 7.061e−14 |
| 2.6875° | +0.197020303 | +15.1095508 | 16.9908345 | −13.4738098 | 9.000e−15 |
| Archived ASWING at **5°** | +0.191155 | +14.8018 | 16.9703 | −11.6441 | Unavailable |

The new intermediate states have no paired native rows. Similar deflection or
heading at different commanded conditions does not count as a match. The plot
also retains the opposite-branch original cold result at 5°.

The centered **2.5°→2.75°** attempt stalls near residual **1.49458e−4**.
A second attempt, **2.6875°→2.75°**, also stalls, near **1.48666e−4**.
Both then enter the existing dense recovery, where a 33.8 MiB allocation fails
under the unchanged 512 MiB address-space limit. Neither writes an accepted
result. Smaller incidence steps extend the verified branch, but do not yet
cross this interval. This does not prove a physical fold, termination, uniqueness
or stability. The fallback still uses the original forward geometry stencil;
the centered diagnostic has not replaced that recovery path.

At the earlier captured trial the maximum absolute section CL is 0.94457 and no
strip exceeds the declared ±1.1 limits. The smooth stall leakage law still acts
below those limits. Nonlinear full-step residual growth is concentrated in the
circulation equations, whereas the measured derivative defect is mainly in
mechanical force rows. These are separate observations, not a justification for
changing the stall law.

All **22 supervised numerical children** in this investigation are terminal and
reaped: **18 successful and four failed**. Two failures were capture-stage
diagnostics: a strict replay-history rejection, then a mistaken assertion about
an internal snapshot's convergence flag. The latter's raw trial was subsequently
restored and independently checked with a fresh residual; it was explicitly
labelled unconverged. The other two failures are the 2.75° solves above. All
original receipts remain available. Runs stayed serial with one BLAS thread,
15 CPU seconds and a 25-second supervisor deadline per numerical stage.

## Remaining work and scope

The next numerical investigation should check the centered tangent at the later
stalled trial and distinguish remaining derivative/conditioning error from
nonlinear continuation behavior. The measured improvement supports testing the
centered calculation as a production change, but it has not yet been promoted
or established as a complete convergence fix. Original sweeps and unresolved
native executions remain required. Browser/build tests remain held.

Primary accounting is unchanged: **708 passes, 12 computed mismatches, 40
unresolved execution outputs, 1,344 finite unrun values and 96 unavailable
reference values**. The twelve 5° opposite-branch mismatches have median error
249.161%, range 227.303–356.704%. These derivative checks are separate from the
primary 3,240 physical checks and 87 passing mesh pairs.

The [authoritative index and source catalog](aswing-authoritative-references.md)
were consulted and the Jan Part IV and Drela steady PDF/text hashes rechecked.
Jan Part IV §3.2, pp. 8–12, Figure 3 defines the three laminates and four incidence
sweeps and labels the native results ASWING 5.96. Its discussion of negative-
coupling local stall and experimental limitations does not remove any native
comparison. Drela's steady §3.8 describes eliminating beam variables from the
coupled Newton system; the diagnostic retains that full-system treatment.

[Saved-only audit](../../artifacts/isae/ae2-centered-audit-20261110/assessment.json) ·
[Derivative comparison](../../artifacts/isae/ae2-stalled-saved-20261110/assessment.json) ·
[Block isolation](../../artifacts/isae/ae2-stalled-blocks-20261110/assessment.json) ·
[Centered directional check](../../artifacts/isae/ae2-centered-tangent-20261110/assessment.json) ·
[Centered runner](../../scripts/probe_isae_ae2_centered_incidence.py) ·
[Audit/plot script](../../scripts/summarize_isae_ae2_centered.py)
