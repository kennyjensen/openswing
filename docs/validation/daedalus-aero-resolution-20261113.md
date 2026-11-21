# Daedalus: aerodynamic resolution at the yaw dip

At **1.157378 Hz**, refining the lifting-line discretization from **82 to 164
to 328 panels**, while prescribing the same loaded structure and harmonic
motion, produces small changes in the dominant wing/fin yaw loads. The last
refinement changes their complex yaw moments by **0.211% /0.430%**, with phase
changes of **0.0903° /0.0783°**. This weakens aerodynamic panel resolution as
an explanation for the much deeper published dip. It does not establish
convergence of the complete coupled aircraft response.

![Wing and fin yaw loads under aerodynamic refinement](../../artifacts/daedalus-aero-resolution-20261113/comparison-v2/resolution.png)

[Vector figure](../../artifacts/daedalus-aero-resolution-20261113/comparison-v2/resolution.svg)
and [comparison data](../../artifacts/daedalus-aero-resolution-20261113/comparison-v2/result.json).
The surface colors follow the application's VibeLattice sequence.

## What is held fixed and what is solved

The accepted 6.7 m/s source-equation/SEGSPL equilibrium and full 2,044-coordinate
rudder response supply the structural geometry, local velocities/accelerations,
frame motion and control perturbation. Structural nodes, physical parameters,
body mesh and point/engine attachments remain fixed. Each lifting interval is
split uniformly in its **whole-beam Glauert angle**. The original structural
position and rotation interpolants are sampled at the new locations, and the
original current interval measure is partitioned conservatively. The adapter
checks the literal file's straight, linearly parameterized undeformed segments.

For each grid, steady circulation is re-solved at that fixed shape, retaining
the nonlinear stall law and circulation-dependent propeller inflow/plume.
No structural retrim follows, so the refined steady aerodynamic loads are not
claimed to be a new aircraft equilibrium. Normal lift slope, incidence,
control derivatives and all other properties use the same SEGSPL input.

The harmonic circulation equations are then solved for the **prescribed actual
aircraft motion and F3 input**. They include the full circulation Jacobian,
engine feedback and the circulation-rate lag diagonal. Fresh fourth-order
directional evaluations supply the remaining geometry/motion forcing. Finally,
the solved circulation and its `i*omega*Gamma` rate produce the full strip and
total aerodynamic force/moment derivatives, including apparent loads, profile
drag, pitching moments, local motion and frame accelerations.

The spacing-dependent mutual vortex core changes with refinement according
to the documented `max(chord/4, interval_width)` rule. Thus this is convergence
of the declared discrete aerodynamic model, including that core prescription,
not a test with fixed smoothing while only adding vortex samples.

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Relevant primary equations are Drela's steady
**Eqs. 150–161, pp. 31–33**, for sampling and vortex influence, and unsteady
**Eqs. 33–49**, for circulation-rate loading, apparent inertia and lag. The
original manual's **K/W** discussion explicitly connects core radius to
interval width. No alternative unsteady model or fitted coefficient is used.

## Results and limits

Complex changes below are `100*abs(H_fine-H_coarse)/abs(H_fine)`. They retain
both magnitude and phase differences; they are not errors against native
ASWING. Moment amplitudes use lb ft per native F3 unit.

| Quantity | 82-panel magnitude | 164-panel magnitude | 328-panel magnitude | 82→164 complex change | 164→328 complex change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Wing roll moment | 6.602905 | 6.634378 | 6.634409 | 0.561% | 0.326% |
| Wing yaw moment | 6.083217 | 6.101770 | 6.110385 | 0.405% | 0.211% |
| Fin roll moment | 0.139853 | 0.140706 | 0.139014 | 0.823% | 1.232% |
| Fin yaw moment | 9.019394 | 9.065233 | 9.102336 | 0.533% | 0.430% |
| Total aerodynamic yaw moment | 9.562173 | 9.631195 | 9.674055 | 0.718% | 0.450% |

Wing yaw phase is **58.6264°, 58.4730°, 58.3828°**. Fin yaw phase is
**−44.4211°, −44.3252°, −44.2470°**. The smaller fin roll moment is not
monotonically convergent in magnitude and changes by 1.232% on the last step.
Every force/moment component is retained; there is no claim that all weak
components agree within 0.5% or that this establishes an asymptotic order.

These are loads under a fixed response shape, not new yaw-rate predictions.
The subsequent [coupled sensitivity calculation](daedalus-aero-feedback-20261113.md)
transfers their complete differences back to the original structural equations.
It finds a **+0.592% / +0.865% first variation of yaw amplitude** for 164/328
panels through the full aircraft descriptor. Higher feedback orders and retrim
remain untested, so this does not establish a converged fine-grid Bode response.
Structural spatial resolution and the unknown historical operating settings
remain separate questions. The baseline Bode
value remains **0.074218 deg/s/F3 versus 0.033986** in the drawing; no new
reference pass or ISAE completion increment is claimed.

## Checks of the adapter and numerics

The unrefined adapter first reproduces the original aerodynamic base **before**
polishing circulation. The original accepted circulation residual is
1.902e−10; the diagnostic's tighter circulation solve reduces it to 2.539e−16.
That tiny adjustment changes the largest baseline moment component by
7.796e−7 lb ft. This is disclosed rather than requiring the polished state to
be identical to the unpolished input.

At nonzero real and imaginary response perturbations, the adapter's force,
moment and circulation residual are checked directly against the full network
path with identical supplied circulation/rate. Their largest differences are
**4.16e−15, 3.40e−13 and 1.44e−16**, respectively. The unrefined harmonic
circulation agrees with the saved full-aircraft solution within **4.462e−10
relative**. All five beams' complete complex wrenches also reproduce the
earlier [full load decomposition](daedalus-load-sensitivity-20261113.md), with
maximum absolute difference **1.712e−9** in their respective force/moment units.

Across the three accepted grids:

| Check | Largest difference or residual |
| --- | ---: |
| Steady circulation residual | 7.816e−11 |
| Analytic circulation block versus fresh directional probes | 3.649e−11 |
| Circulation-rate block versus fresh probes | 6.506e−19 |
| Geometry/motion forcing: halving stencil width | 1.412e−9 |
| Solved harmonic circulation residual | 3.871e−16 |
| Load derivative: halving stencil width | 1.834e−9 |

The four-point stencils use widths **1e−3 and 5e−4**. The unchanged acceptance
gates are 1e−10 for steady/harmonic circulation residuals, 2e−8 for circulation
block and shape-stencil checks, 2e−6 for load-stencil changes and unrefined
circulation-response relative error. The force-path comparison uses 2e−8
absolute plus 2e−10 relative. These are numerical consistency checks, not
reference-aircraft accuracy tolerances.

The three accepted jobs use **39, 41 and 43 direct aerodynamic evaluations**,
with two additional full-network probes on the unrefined case. All jobs use
one BLAS thread and the existing 512 MiB address-space, 15 CPU-second and
25 wall-second caps. Maximum accepted numerical-job use is **9.288 CPU
seconds, 10.923 wall seconds and 189.426 MiB resident memory**. All children
and parents were reaped; browser/build jobs remain held.

## Retained failures and reproduction

The original `dip-1` attempt failed on the new adapter's incorrect TimeState
attribute name. `dip-1-v2` wrongly compared the polished base moment to the
unpolished input with an equality gate. The corrected gate tests identical
circulation first and separately reports the polishing change.

`dip-1-v3` and `dip-2` completed but are **superseded**: a cross-check against
the earlier full load decomposition found that the adapter had not applied
the six acceleration operating slots to its flight condition. Circulation
was unaffected, but apparent-load derivatives were incomplete. The adapter
now uses the same operating-condition application as the network, with the
fresh force-path comparisons above. No production equation or reference
target changed. The first comparison figure was also superseded to adopt
the requested VibeLattice surface colors.

Accepted immutable records are
[82 panels](../../artifacts/daedalus-aero-resolution-20261113/dip-1-v4/result.json),
[164 panels](../../artifacts/daedalus-aero-resolution-20261113/dip-2-v2/result.json)
and [328 panels](../../artifacts/daedalus-aero-resolution-20261113/dip-4/result.json).
Each directory retains the runner, input hashes, log, terminal receipt and
complex arrays. Use [the bounded driver](../../scripts/check_daedalus_aero_resolution.py)
with one fresh tag at a time:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/check_daedalus_aero_resolution.py \
  --factor 2 --tag fresh-dip-2
```

The `report` stage regenerates the figure from the three explicitly named
accepted observations. No prior evidence or progress event is rewritten.
