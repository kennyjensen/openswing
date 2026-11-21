# SA-12 matched native AVL ground controls

Observed 2026-11-09 UTC. **Four matched controls agree with native AVL to
better than 0.000002% in CL, near-field CD and Trefftz CDi.** The circulation
and local velocity fields agree as well. This supports the current-influence
ground-image operator under the declared wind-parallel conditions. It does
not recover the historical ISAE pose or K/F setting, validate stall/profile
drag, or add passes to the original SA-12 comparison.

The [preceding paired flap study](isae-sa12-flap-pose-20261109.md) showed that
switching universally to frozen influences is not an established correction:
it improves close-ground drag but worsens agreement at the nominal-infinity
height. These native controls therefore check the existing current-influence
implementation independently before changing any aerodynamic equation.

## Common problem and source basis

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog were consulted. Jan Part I **p.38 and Figure 23,
p.40**, and the original SA-12 models establish the straight rectangular
planform and equivalent flapped section. The controls retain span 1.524 m,
chord 0.254 m, Sref 0.3871 m², Cref 0.254 m and Bref 1.524 m. The no-flap
section has slope 6/rad and zero incidence; the flapped section has slope
7.44/rad and equivalent incidence 12.5°. Ground heights are 0.127 m and
1000 m. No geometry or section slope is fitted.

Both solvers use Mach zero, speed 1 m/s, zero profile drag and no stall.
This isolates a common inviscid problem; it is deliberately separate from
the archived nonlinear, viscous ASWING targets. The production control parses
the original model, sets Cdf to zero and disables stall explicitly. Cdp is
already zero. The reported CD below is therefore inviscid near-field drag.

For each point, OpenSwing uses pitch equal to flight alpha and current
influences. Rotating into wind axes makes both the physical wind and the
ground plane parallel to native AVL's fixed-x wake. AVL uses alpha zero,
section AINC equal to original section incidence plus flight alpha, and a
solid symmetry plane at Zsym = −height. No reflected ray is omitted or
redirected independently of its image plane.

AVL source checks establish the conversion:

- `reference/third_party/avl/src/aic.f`, lines 113–162, reflects both endpoints about
  Zsym, retains the image bound segment and uses the fixed-x trailing rays.
  The alternative alpha-dependent ZOFF expression is commented out.
- `src/sgutil.f::CSPACER`, lines 325–344, gives the needed receiver offset
  for **one uniform chord row**: CP−QC = 0.5 × CLAF × chord, with
  CLAF = dCLda/(2π). Cosine chord spacing uses a different nonlinear CLAF
  mapping and is not interchangeable here.
- `src/amake.f`, lines 491–522 and 1078–1095, places vortex/receiver
  coordinates along x and incorporates section incidence in the normals.
  The exported endpoints, bound receivers, control points and normals are
  all checked against the production geometry.

There are 100 cosine span intervals. The rigid production diagnostic uses
the exact exported native lattice. Native AVL's center is about −3.4e−11 m;
the normal OpenSwing mesh constructor would also insert the required exact
center attachment at zero. Preserving the native lattice avoids that extra
interval in this comparison. This does not change the default or structural
mesh. Geometry and normals agree within 1.12e−16 in their respective units.

## Results

| Original model / point | OpenSwing CL | Native AVL CL | OpenSwing near-field CD | Native AVL near-field CD |
|---|---:|---:|---:|---:|
| No flap, h/c=0.5, alpha=8° | 0.686208521673 | 0.686208517758 | 0.0134792069534 | 0.0134792068765 |
| Flap, h/c=0.5, alpha=−5° | 0.794180748948 | 0.794180744417 | 0.0179811895885 | 0.0179811894859 |
| Flap, h/c=0.5, alpha=2° | 1.404935344440 | 1.404935336424 | 0.0638952982181 | 0.0638952978535 |
| Flap, h=1000 m, alpha=5° | 1.469512218735 | 1.469512210351 | 0.1157053361805 | 0.1157053355203 |

Raw relative differences are approximately 5.706e−7% for CL/CD and
1.1412e−6% for CDi. These uniform differences follow from AVL's rounded
`PI4INV = 0.079577472` in `aic.f:523`. The source-derived factor is
k = 4π × 0.079577472 = 1.0000000057057898. Multiplying native circulation
and near-field forces by k, and native CDi by k², accounts for that constant;
no parameter was estimated from the results. Raw coefficients remain recorded
alongside this diagnostic. Neither solver's source constant was changed.

After accounting for that known constant, the maximum relative circulation
difference is 8.35e−15, local velocity difference 1.38e−14 m/s, force-coefficient
difference 3.11e−15 and CDi difference 2.92e−16. Reconstructing native forces
directly from its exported circulation and velocity agrees within 3.34e−16.
These results support the image-field and force accumulation for this
specific geometry and setup; they do not establish mesh convergence or
undocumented behavior of the ISAE-modified ASWING executable.

## Ground regression test

The existing height/far-limit/rigid-coupled test inherited the global frozen
default while assuming a wind-parallel wake. Its pitch=alpha plane is oblique
to the frozen body-x wake, so the solver correctly returned unavailable
Trefftz CDi and the test attempted to divide `None`.

The test now explicitly selects current influences. A companion regression
asserts that oblique frozen wakes retain converged loads but no stationary
Trefftz result, while the aligned current-wake case has available CDi. Both
targeted tests pass: **2 passed in 12.85 s**. No production algorithm, default,
availability guard or acceptance tolerance changed.

## Evidence and remaining work

- [Four-case analysis and 218 verified source/artifact hashes](../../artifacts/isae/sa12-avl-ground-r2-20261109/analysis.json)
- [Immutable plan](../../artifacts/isae/sa12-avl-ground-r2-20261109/plan.json)
  and [serial driver](../../scripts/verify_sa12_avl_ground.py)
- [Test before receipt](../../artifacts/isae/sa12-ground-test-20261109/before.json)
  and [passing receipt](../../artifacts/isae/sa12-ground-test-20261109/after.json)
- [Superseded first adapter attempt](../../artifacts/isae/sa12-avl-ground-20261109/superseded.json):
  one native run completed, then the extra-center-interval assertion stopped
  comparison before any production solve. Its evidence is retained.

The existing instrumented AVL binary was reused without rebuilding. Four
native calls and four production comparisons completed in separate serial
foreground invocations. Native calls took 0.12–0.51 s with about 27 MiB peak
RSS; production calls took 2.91–5.35 s with peak RSS below 200 MiB. Each job
used one BLAS thread, 512 MiB address-space, 15 CPU-second and 25 wall-second
limits. No browser, background solver or build job was started.

The historical **2,324/4,080 at 3%** remains unchanged; this is not a full
5% rerun. The next issue is to reconcile the archived ground/pose/wake and
raw-drag conventions with the report and original drivers. The native
agreement gives no reason to replace the physical reflected-wake operator
with the endpoint-only alternative that previously failed the ground
boundary condition. A supported common setup must precede a full SA-12
rerun; picking the best setup separately for each point would not validate
the case. Post-stall repairs remain deferred.
