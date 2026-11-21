# SA-12 flapped-model pose controls

Observed 2026-11-09 UTC. Eight fresh production solves and eight independent
saved-field replays are complete. The paired controls **do not establish frozen
influences as a general correction**: the frozen/zero-pitch alternative improves
close-ground raw drag, while current influences match the higher-altitude
reference more closely. No production algorithm, default, source model or
primary completion fraction changed.

Four points were selected before running: the original flapped model at
h/c=0.5 and alpha=−5°/+2°, h/c=2 at +5°, and the nominal-infinity height at
+5°. All four archived stall flags are zero. Each point uses both the existing
wind-parallel/current setup and the previously disclosed zero-pitch/frozen
alternative. Section properties, stall strength/width, raw reference values,
100-interval mesh reconstruction and all other settings remain unchanged.

| Flapped point | Setup | CL error | Raw CD error | CDi error | CL/CD/CDi at 5% |
|---|---|---:|---:|---:|---:|
| h/c=0.5, −5° | Wind-parallel/current | +2.162% | **−7.859%** | +4.626% | 2/3 |
| h/c=0.5, −5° | Zero-pitch/frozen | +0.905% | −0.541% | +1.728% | 3/3 |
| h/c=0.5, +2° | Wind-parallel/current | −1.279% | **+6.725%** | −2.082% | 2/3 |
| h/c=0.5, +2° | Zero-pitch/frozen | −1.106% | −0.510% | −1.454% | 3/3 |
| h/c=2, +5° | Wind-parallel/current | −0.666% | +1.498% | −1.445% | 3/3 |
| h/c=2, +5° | Zero-pitch/frozen | −3.022% | −3.349% | **−5.028%** | 2/3 |
| Nominal infinity, +5° | Wind-parallel/current | +0.135% | +0.014% | +0.019% | 3/3 |
| Nominal infinity, +5° | Zero-pitch/frozen | −2.836% | −4.015% | −4.554% | 3/3 |

Each setup has twelve lift/drag targets and four tiny-Cm targets. The baseline
passes **10/12 lift/drag, 10/16 overall**; the alternative passes **11/12
lift/drag, 11/16 overall**. All eight exactly zero Cm predictions retain their
original printed absolute gates and fail against the tiny native residues.
The 5.028% induced-drag error remains a failure; the tolerance is unchanged.
The nominal-infinity height is 1000 m with images still enabled.

Together with the preceding four no-flap states, the same frozen/zero-pitch
alternative now passes **23/24 sampled lift/drag comparisons, 23/32 including
Cm**, across eight distinct states. That expands a qualified alternative,
not the primary full-family score. It must not be summed with another setup
or the historical 2,324/4,080 total. The earlier 12/12 no-flap result remains
true for its original scope; it is not a claim about every SA-12 condition.

## What changed the interpretation

The far-height control is especially useful: current influences reproduce
native CL/CD/CDi within 0.135%, while frozen influences shift the same fields
by 2.84–4.55%. Thus the earlier no-flap agreement at 5% was insufficient to
identify the archived K/F state. The new result supports retaining the
current-influence baseline while investigating the ground-image/pose treatment.
It does not prove the archived Euler attitude or eliminate other setup errors.

At the two close-ground points, the raw-CD changes from the baseline to the
alternative are +0.0042413 and −0.0064747. Independent force decomposition puts
94.11% and 97.73% of those changes in the near-field circulation force. Changes
in friction account for almost all the remainder. The direct stall-pressure
terms are tiny: at +2° they are 3.44e−7 and 6.24e−7 respectively, and at −5°
they are about 2e−25. This is not evidence for changing the stall model.
Indirect circulation changes from soft stall leakage remain part of the full
nonlinear solution and have not been removed. The minimum section margin over
the eight runs is 5.36 transition widths; no post-stall repair was attempted.

## Source reconciliation

The [authoritative reference index](aswing-authoritative-references.md), its
source catalog, and [SA-12 source audit](isae-sa12-sources.md) were consulted.
Jan Part I **p.38 and Figure 23, p.40** specifies the flapped equivalent through
section alpha=12.5°, slope=7.44 and drag coefficient=0.04. The original model
sets zero geometric twist and no flap-control derivative. These values were
not refitted. No experimental curve or MATLAB drag display correction was
substituted for raw archived ASWING outputs.

The ground-image description in **Part I p.20, Figure 8 p.21** explicitly
requires impermeability of the ground plane. Drela steady **§4.5, Eqs.165–173
and Figure 17 p.35** describes the reflected image geometry. Both figures
were visually checked, with [ISAE](../../artifacts/isae/sa12-flap-pose-20261109/reference-figures/isae-part-1-aerodynamics.png)
and [Drela](../../artifacts/isae/sa12-flap-pose-20261109/reference-figures/drela-aswing-steady.png)
page renders retained. They provide no basis for promoting the earlier
endpoint-only image-wake diagnostic, which failed the induced ground
boundary-condition check.

The K/F and Euler-pose qualifications from the
[preceding pose study](isae-sa12-pose-diagnostics-20261109.md) remain: a single
K/F toggle does not establish its final state without the initial setting,
and the scripts do not record Euler attitude. The manual's `% A D` sequence
selects anchored constraints and then exits the constraint editor (`D` means
DONE); it does not independently reveal the initial numerical pitch. Zero
pitch also must not be equated to the stationary-board, wind-parallel tunnel
reconstruction at nonzero alpha.

The next investigation should isolate ground-image and pose conventions
under current influences using matched source/operator controls. The results
do not justify selecting a different setup independently for each point.

## Verification and artifacts

All eight states converge, with normalized circulation residuals at most
8.18e−15. The independent replay reconstructs the complete real/image vortex
field, section cl and nonlinear tangency, each force contribution, force and
moment normalization, and the separate infinite-wake CDi. Maximum force-vector
discrepancy is 3.56e−15 N and maximum coefficient discrepancy is 8.89e−16.
All 32 reference decisions are separately checked from original decimal
tokens. Each setup remains separate in the aggregate artifact.

Each job was foreground and serial with one BLAS thread, 512 MiB address-space,
15 CPU-second and 25 wall-second limits. Production calls took 2.76–3.70 seconds,
with peak RSS below 185 MiB. No browser or build jobs were started.

- [Complete results, paired drag decompositions and 199 verified source/artifact hashes](../../artifacts/isae/sa12-flap-pose-20261109/analysis.json)
- [Immutable eight-job plan](../../artifacts/isae/sa12-flap-pose-20261109/plan.json)
- [Production driver and decimal comparison checks](../../scripts/verify_sa12_flap_pose.py)
- [Reusable independent image-field replay](../../scripts/sa12_image_replay.py)

The driver prepares an immutable plan, runs one indexed production job per
invocation, and replays one saved state per verification invocation. Existing
receipts cannot be overwritten; new runs require new output paths.
