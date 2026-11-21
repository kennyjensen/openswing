# Daedalus: motion driving the loads near the yaw dip

The Bode discrepancy remains unresolved. A new decomposition of the accepted
1.157378 Hz response identifies **motion carried by the fin attachment** as
the largest part of the fin's motion-induced aerodynamic moment. Fin bending
and twist relative to that attachment contribute less. Ordinary wing lift has
substantial contributions from both aircraft-frame and wing elastic motion.
These findings narrow the investigation; they are not new native-reference
passes or evidence that a particular parameter should be changed.

The subsequent [coupled feedback diagnostic](daedalus-root-feedback-20261113.md)
recomputes the full response after deleting only those fin-root aerodynamic
feedback terms. It quantifies their yaw suppression at 0.2 Hz and 1.157378 Hz;
the present report remains the prescribed-motion load decomposition.

![Complex load contributions](../../artifacts/daedalus-motion-loads-20261113/plot-v2/motion-loads.png)

[Vector figure](../../artifacts/daedalus-motion-loads-20261113/plot-v2/motion-loads.svg),
[all load components](../../artifacts/daedalus-motion-loads-20261113/report/result.json),
[CSV](../../artifacts/daedalus-motion-loads-20261113/report/yaw-moments.csv),
[fin transport split](../../artifacts/daedalus-motion-loads-20261113/fin-report/result.json).

## Calculation and limits

The case is the unchanged 6.7 m/s, SEGSPL, current source-equation model with
108 structural nodes, 82 circulation unknowns and 2,044 dynamic coordinates.
It uses the accepted full harmonic state from the
[load sensitivity study](daedalus-load-sensitivity-20261113.md), not a new trim
or a new Bode prediction. Yaw is still **0.074218 deg/s/F3**, against
**0.033986** in the drawing. The later
[full mesh refinement](daedalus-structural-resolution-20261113.md) remains a
separate observation and does not establish convergence of every channel.

For the full harmonic matrix `K = iωM − A`, split the non-circulation motion
into aircraft-frame variables and the geometry/velocity/rate coordinates of
each beam. The direct control is a separate contribution. For each motion `zj`,
solve the complete aerodynamic block:

```text
KΓΓ Γj = Bj − KΓq qj
```

This retains all surfaces' induced-flow coupling, engine-flow feedback and
circulation lag. The summed circulation reproduces the actual full solution
within **1.180e−17** in scaled coordinates. The omitted internal-load/reaction
columns have exactly zero effect in these circulation rows. No circulation
mode, force term or structural coordinate was removed from the original solve.

The prescribed group states and their rates `iωzj` are passed through the full
nonlinear physical load path. Fourth-order real/imaginary directional stencils
at widths 1e−3 and 5e−4 recover every component's force and moment. The same
conservative endpoint transfer used by the full aircraft preserves moments.
These parts obey linear aerodynamic tangency but do **not** individually
satisfy the aircraft's structural and joint equations. They are an accounting
of the existing coupled motion, not independent aircraft responses or affine
parameter sensitivities.

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Drela's unsteady Eqs. 29–36 specify the moving force
point and circulation/rate lift, Eqs. 41–44 the apparent loads, and Eqs. 48–56
the circulation lag. The [primary unsteady description](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf)
and [local copy](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf)
remain the governing references. This diagnostic partitions their implemented
loads; it is not another independent implementation of those equations.

## Fin moment cancellation

Values below are **ASWING body-z aerodynamic moments**, in lb ft per native F3,
with the `exp(iωt)` convention. Both components matter. They must not be read
as separate yaw-rate amplitudes. All fin aerodynamic terms are included:
circulation and circulation-rate lift, profile force, section moment and
apparent loads.

| Source of prescribed motion/input | Real moment | Imaginary moment |
| --- | ---: | ---: |
| Direct rudder control | +15.70353 | −0.43830 |
| Aircraft-frame motion | −1.10653 | +0.16792 |
| Fin-root translation | −3.27765 | −6.96922 |
| Fin-root rotation | −3.70207 | +0.23992 |
| Fin deformation relative to root | −1.16650 | +0.67721 |
| Other beams, through induced flow | −0.00899 | +0.00955 |
| **Sum** | **+6.44178** | **−6.31291** |

The last three fin-motion terms together give **−8.14623 − 6.05209i**. Their
individual magnitudes are approximately 7.70, 3.71 and 1.35 lb ft/F3, respectively.
Magnitudes cannot be added to obtain a contribution percentage because their
phases differ.

The split uses the actual loaded fin root at beam 3, material `t=0`, joined
to the boom at beam 4, `t=20`. Root translation is applied uniformly to the
fin. Rigid rotation adds `δθroot × (r − rroot)` to node positions, and the
matching angular-velocity transport to velocities. The remaining motion is
fin deformation relative to that root. The three states reproduce the entire
original fin-motion state within **5.486e−18**, including their re-solved
circulations; local velocity definitions close within **7.758e−18**.

At this frequency, the fin-root lateral displacement amplitude is
**0.024998 ft/F3**, and its body-z rotation amplitude is **0.18194°/F3**.
These are relative to the aircraft frame. They are predictions, not measurements
extracted from the native animation.

The separate `beam4` group has only a small direct aerodynamic influence on
the fin. That does **not** mean boom mechanics are unimportant: the boom-driven
transport of the fin is contained in the fin node motion and appears in the
root-translation/rotation rows above.

## Wing lift

The wing's ordinary circulation-lift moment is **2.56800 + 4.96311i**:

| Source | Real moment | Imaginary moment |
| --- | ---: | ---: |
| Aircraft-frame motion | +2.07190 | +2.21865 |
| Wing elastic motion | +0.49760 | +2.74192 |
| Control and other beams | −0.00151 | +0.00254 |

This shows why a local boom-bending check alone cannot settle the yaw dip.
The wing's phase-dependent loading is also substantial. Direct wing-to-fin
induced-flow changes from wing motion are small in this particular partition;
the complete aircraft still couples these surfaces through its motion and
force/moment balances.

## Verification and retained attempts

The full-state load replay is **bit-identical** to the saved component loads
and wrenches from the earlier sensitivity study. All seven motion/input groups
sum to that replay within **1.244e−13** in scaled load residuals and
**6.186e−9** in physical wrench components. The fin subpartition sums within
**1.028e−13 / 2.645e−9**, respectively. Maximum two-width differences are
**9.629e−14** for scaled loads and **2.963e−9** for physical wrenches; maximum
harmonic circulation residual is **1.431e−11**. The unchanged gates are
2e−8 for scaled load/tangency checks and 2e−6 for physical wrench checks.
The 82-coordinate circulation block has condition number **75.51**.

The [bounded driver](../../scripts/check_daedalus_motion_loads.py) retains all
plans, source snapshots, input hashes, arrays, logs and terminal receipts.
Every numerical child uses one BLAS thread, 512 MiB address space, 15 CPU
seconds and 25 wall seconds, with its parent reaping it. Across 18 jobs,
maximum observed use is **4.221 CPU seconds, 13.345 wall seconds and
106.122 MiB RSS**. Seventeen jobs exit successfully. The initial `full` job
failed only in its reporting loop, which incorrectly called beam 4 the fin;
the file defines beam 3 as the rudder and beam 4 as the boom. The corrected
`full-v2` reruns every check and supplies the accepted comparison. The first
figure let equal-aspect axis adjustment clip vectors; `plot-v2` preserves the
full limits and was visually checked. Both earlier artifacts remain retained.

The [evidence audit](../../artifacts/daedalus-motion-loads-20261113/verification.json)
checks the final reports, job receipts and source/input hashes without rerunning
the numerical work. Production physics, aircraft inputs, ISAE completion
fractions and progress history are unchanged. Browser/build jobs remain held.

## Next discriminating check

Prior image work supports local boom curvature at 1 Hz, while
[absolute fin motion remains unresolved](daedalus-animation-20261113.md).
The present results make the fin-root translation/rotation phase relative to
wing loading a more specific next target than another generic mesh increase.
The GIFs' different publication date and uncertain camera/mean-shape calibration
remain relevant; neither those images nor this decomposition establishes the
historical Bode operating point. No stiffness, mass, damping or lag coefficient
has been fitted to deepen the dip.
