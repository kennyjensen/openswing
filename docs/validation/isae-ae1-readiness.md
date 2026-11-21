# ISAE AE-1: Pazy steady-deflection setup

Primary incidence, speed and observation data were identified in this source
review, before any AE-1 solve. The subsequent [eight-state pilot](isae-ae1-pilot.md)
now uses an independently checked explicit mirror to represent the ideal
tunnel wall. The historical preflight failures below are preserved; general
production wall-root support remains unfinished.

The [source-readiness record](isae-ae1-source-readiness.json) pins the supplied
experimental files, which match the authors' primary dataset byte-for-byte,
and locates the existing corrected primary skin-on stiffness/mass conversion.
It retains a separate accounting of the literal ISAE model and archived outputs.

## Matched conditions and observations

The primary static comparison uses skin-on Technion Test 2 at incidences 5°
and 7°. Riso and Cesnik's author preprint, section IV.C, p.18, describes an
upright configuration with gravity effects neglected. That is a documented
modeling assumption, not a claim that an upright real wing has no gravitational
preload. The literal ISAE output's initial gravity sag is preserved separately.

At 5°, the midchord displacement is measured directly; at 7°, it is estimated
from the mean leading- and trailing-edge displacements. Twist uses their
differential motion. Exact coordinates, signs, baselines and source locations
are retained in the source record rather than equating these observables with
an arbitrary beam-axis displacement or local rotation component.

The primary descriptions disagree about the 10 g tip-rod mass: Avin places it
at the trailing edge; Riso places it 10 mm behind the trailing edge. Its position
does not affect the declared zero-gravity static equilibrium, but the conflict
remains relevant to gravity and dynamic comparisons.

## Tunnel-wall image and current construction gaps

The archived `alpha5.sh` and `alpha7.sh` use `OPER G`, flag 1 and normal
`(0,1,0)`. The ASWING guide defines this as a solid-ground **aerodynamic image**,
separately from the gravity command. At zero Earth position and attitude, the
corresponding OpenSwing condition is `ground_effect=1`,
`ground_normal=(0,1,0)`, with its plane through the span root.

Two distinct current limitations are retained:

- The literal model's out-of-domain Weight attachment causes full mesh
  construction to reject before any aerodynamic evaluation.
- An isolated mesh of its lifting geometry has a root exactly on the requested
  image plane. The current clearance rule rejects contact as well as crossing.
  This was verified by a separate geometry-only call; it is not a successful
  construction or solve of the full literal model.

The [preflight record](isae-ae1-wall-root-preflight.json) preserves both terminal
results and their scopes. No epsilon offset, dropped image or altered source
file has been substituted. A declared wall-root boundary treatment or a full
mirrored-wing reconstruction needs independent equivalence checks before the
coupled comparison can proceed.

## First comparison after setup is resolved

The proposed initial batch uses the already corrected primary skin-on model,
30/60 requested intervals per half wing, and three measured conditions:
5°/30 m/s, 5°/40 m/s and 7°/30 m/s. Together with a zero-flow baseline on each
mesh, this gives eight states. It is a bounded initial comparison, not the
complete speed sweep or an experimental acceptance claim.

The proposed batch is now completed in the [pilot](isae-ae1-pilot.md), with both
root-normal and wind-normal displacement conventions retained because the
processed experimental export does not explicitly settle its axes. The source
record above remains the unchanged pre-run proposal. AE-1 remains pending
beyond this pilot; the ledger stays **17 partial / 24 pending / 0 fully validated**.
