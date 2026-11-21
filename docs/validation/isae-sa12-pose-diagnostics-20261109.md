# SA-12 ground-pose and influence-state diagnostics

Observed 2026-11-09 UTC. **The unchanged production solver matches all 12
sampled CL/CD/CDi values within 5% under a disclosed zero-pitch, frozen-influence
alternative.** The largest error is 2.92%. This is evidence of setup sensitivity,
not proof that these were the archived settings. No production algorithm,
default, input file, tolerance or primary completion count changed.

The four points retain their original models, speed, density, Mach correction,
100-interval mesh reconstruction, stall law, heights and raw native targets.
Only pitch (zero instead of alpha) and frozen influences (true instead of false)
change from the existing adapter's declared reconstruction.

| No-flap point | CL error | Raw CD error | Trefftz CDi error | CL/CD/CDi at 5% |
|---|---:|---:|---:|---:|
| h/c=0.5, alpha=8° | −0.625% | +2.920% | −0.267% | 3/3 |
| h/c=0.5, alpha=−5° | +0.920% | −2.012% | −2.139% | 3/3 |
| h/c=0.5, alpha=5° | +0.021% | +0.850% | +0.208% | 3/3 |
| h/c=2, alpha=8° | −1.641% | −1.190% | −2.527% | 3/3 |

Signed error is `(prediction − reference) / abs(reference)`. Four exactly zero
Cm predictions still fail the unchanged printed gates for tiny archived Cm
residuals. The alternative therefore has **12/16 checks**, including **12/12
lift/drag checks**. These overlap existing targets and must not be added to
the historical 2,324/4,080 count or to the earlier six-point pilot.

## What the controlled calculation separates

The first four independently solved diagnostics share the closest-ground
no-flap alpha=8° point:

| Pose / influence interpretation | CL | CD | CDi | Maximum induced normal speed at sampled ground points |
|---|---:|---:|---:|---:|
| Pitch=alpha, current, complete reflected image | 0.685991 | 0.0224968 | 0.0134789 | 9.15e−16 m/s |
| Pitch=0, current, complete reflected image | 0.695155 | 0.0186762 | Unavailable | 5.94e−14 m/s |
| Pitch=0, current, image endpoints reflected but wake direction shared | 0.710774 | 0.0164887 | 0.0143661 | **0.994 m/s** |
| Pitch=0, frozen, complete reflected image | 0.706913 | 0.0173153 | 0.0143587 | 0 m/s |
| Archived ASWING | 0.711360 | 0.0168240 | 0.0143971 | Not archived |

Zero pitch alone reduces the raw-CD error from 33.72% to 11.01%; it does not
remove it. A common stationary Trefftz trace is unavailable when the real
and fully reflected wakes are not parallel. No near-field value is substituted
for that missing CDi.

Keeping both trailing rays in the same direction while reflecting only their
origins gets close to the archive too. Its four-point follow-up keeps all 12
lift/drag differences within 2%, including the positive/negative-alpha
asymmetry. However, that construction fails the induced no-through-flow
condition on the physical ground plane. It is a diagnostic of a possible
historical approximation, **not an acceptable default physics correction**.
Its formal parallel-wake CDi is not evidence of a valid ground-image solution.

The frozen alternative also reproduces much of the archive's asymmetry:
native CL is −0.490291 at −5° and +0.452982 at +5°, while production returns
−0.485782 and +0.453076. This supports further setup investigation rather
than changing section properties or stall parameters. Direct stall-pressure
drag stays below 1.22e−10 across the ten diagnostic states.

There is a further distinction between matching an archived calculation and
reconstructing the tunnel: **zero pitch at nonzero alpha gives freestream
normal to the board** (4.977 m/s at 8°). The frozen image system cancels its
induced normal velocity, but this does not cancel the freestream component.
Consequently these alternatives must not be presented as recovered physical
tunnel conditions. The baseline pitch=alpha remains the declared
wind-parallel reconstruction.

## Reconciliation with authoritative sources

The [authoritative reference index](aswing-authoritative-references.md) and
the [original SA-12 source audit](isae-sa12-sources.md) remain controlling.

- Drela steady §4.5, Eqs.165–173, reflects the image geometry. Eqs.160–161
  integrate the complete vortex path. A claim that only bound endpoints should
  reflect while a tilted trailing ray should not reflect is not established
  by these equations. The independent ground-boundary check rejects that as
  a general image construction.
- Drela steady §4.6 describes freezing influences at undeformed geometry and
  zero wind angles. The extended user manual **p.81**, and original
  `aswing_doc.txt` lines 2293–2312, describe K/F's fast/frozen versus
  slow/wind-aligned options. The sample K menu at original lines 2243–2255
  shows freeze=T and Mach=0.
- Each original SA-12 script toggles K/F once. If its initial state was the
  sample menu's T, the final state would be current, not frozen. The archived
  startup `.set` state and Euler attitude are unavailable. The invoked
  executable path is `ASWING_ISAE_ENAC/bin/aswing`; its modified defaults
  cannot be inferred from the directory name. Close agreement does not resolve
  this conflict, so the adapter is not changed to frozen/zero pitch.
- Jan Part I **p.38 and Figure 23, p.40** describe the ground-effect case and
  post-stall drag limitation. The original MATLAB display correction
  `0.01 + CDi` remains separate from raw CD. No plotting correction, incidence
  offset, altered drag coefficient or fitted parameter was applied here.

Two different interpretations agreeing at 5% means these samples cannot
identify the historical implementation uniquely. The next useful discriminator
is the flapped model at nonzero incidence, keeping the same predeclared setup
choices and excluding post-stall repairs. Any eventual primary-scope change
must explicitly reconcile the command script and the assumed initial state.

## Verification and retained evidence

Ten independent diagnostic equilibrium solves preceded four unchanged
production calls. Jobs were serial, foreground and single-threaded, with
512 MiB address-space, 15 CPU-second and 25 wall-second limits. Each diagnostic
uses the independently transcribed AVL segment/ray kernel with zero core and
the exact 1/(4π) factor, analytic nonlinear tangency Jacobian and a separate
infinite-wake drag calculation. A finite-difference check verifies the
Jacobian. The baseline reproduces the preceding production circulation within
9.83e−12; all four frozen production states reproduce the independent
circulation, velocities and force vectors within 1.83e−13 absolute.

Every production state converges below 5.47e−16 normalized residual. All 16
comparison decisions were independently checked using exact-decimal reference
tokens and gates. Production calls took 2.89–8.34 seconds with peak RSS below
184 MiB. No browser, build, background solver or parallel agent was started.

- [Four-interpretation diagnostic and immutable plan](../../artifacts/isae/sa12-image-pose-20261109/plan.json)
- [Predeclared three-point follow-up](../../artifacts/isae/sa12-pose-followup-20261109/plan.json)
- [Production comparisons, full fields and 212 verified source/artifact hashes](../../artifacts/isae/sa12-frozen-pose-20261109/analysis.json)
- [Diagnostic driver](../../scripts/diagnose_sa12_image_pose.py),
  [follow-up driver](../../scripts/diagnose_sa12_pose_followup.py), and
  [production verifier](../../scripts/verify_sa12_frozen_pose.py)

Each driver prepares an immutable plan and runs one indexed job per
invocation. Receipts use exclusive creation; new runs need new output paths.
The goal remains incomplete and active; this update narrows a validation
discrepancy without redefining the requested ASWING implementation.
