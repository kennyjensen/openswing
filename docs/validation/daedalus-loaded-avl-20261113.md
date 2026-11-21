# Daedalus loaded wing and fin: native AVL rate comparison

The actual loaded wing and fin now have independent, native AVL comparisons
at their accepted geometry. Wing vertical force differs by **0.556%** at zero
body rate. The principal lateral moment derivatives differ by **0.84–8.42%**
for the wing and **3.72–5.21%** for the fin. These are isolated, steady
circulatory-load comparisons; they do not establish full-aircraft unsteady
phase or resolve the rudder Bode discrepancy. No production physics or
aircraft parameters were changed.

This follows the [wing-paper comparison](daedalus-wing-paper-20261113.md)
and [load sensitivity study](daedalus-load-sensitivity-20261113.md). The
authoritative [AVL source and conversion policy](aswing-authoritative-references.md#avl)
applies: matching vortex endpoints does not establish identical receiver
locations, section normals or force conventions.

## Setup and independent checks

The input is the accepted moving-airflow/SEGSPL equilibrium at 6.7 m/s,
alpha **3.0563625°**, beta **0.0180183°**, with the literal public `dae.asw`
properties and equilibrium control settings. Its nonlinear residual is below
1e−9. Each selected lifting surface is held rigid in its actual loaded shape
and evaluated separately. Bodies, engines, other lifting surfaces and their
mutual influences are omitted from both comparisons.

The diagnostic uses Mach zero, unit speed and density, body-axis rotation
rates and a body-x wake. A uniform velocity offset in the OpenSwing call
preserves the accepted incident-flow direction while keeping that wake fixed.
Native AVL's operating options explicitly select geometric axes and body
rotation rates. This is not a new full-aircraft equilibrium.

Each original mesh interval is one AVL span interval and one chordwise vortex.
Streamwise chord is obtained from normal chord using the actual local span
direction. Section incidence includes elastic orientation, the literal
incidence and the accepted control's lift-slope increment. CLAF transfers
the declared section lift slope. The exported vortex endpoints agree with
OpenSwing's endpoints to **1.12e−16 ft**. The maximum coordinate difference
between their receivers is **0.248480 ft** for the wing and **0.020359 ft** for
the fin. Original beam/material-frame receivers are retained in OpenSwing;
native AVL uses its standard SECTION interpolation. Those conventions are
measured rather than silently equated.

For each native result, a separate calculation reconstructs circulation from
the exported control-point normals and induced-velocity matrix. It includes
the exact imposed rotation term `r × omega`. Native forces and moments are
also reconstructed from its circulation, induced velocity, bound-vortex
vectors and force locations. Across **14 numerical jobs**:

| Numerical check | Maximum error |
| --- | ---: |
| Reconstructed native circulation, relative | 2.05e−15 |
| Reconstructed native induced velocity / freestream | 3.65e−17 |
| Reconstructed native force/moment coefficients, absolute | 4.45e−16 |

AVL's small same-component core must be included in that native replay.
`VSRF` assigns `0.0001 * transverse_strip_width`; `VORVELC` uses the quartic
Leishman expression and its rounded `PI4INV`. See
[native aic.f](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/aic.f)
and the existing [independent transcription](../../scripts/avl_vorvelc_reference.py).
The separate zero-core replay differs from native velocity by up to
**2.464e−6** times freestream. This is the same documented distinction found
in the [curved SA-11 audit](isae-sa11-curved-extension-20261108.md); it is not
evidence to replace ASWING's zero same-beam core. Production remains unchanged.

## Rate derivatives

Central perturbations use `omega/V = ±0.0001 rad/ft`. The table compares
the derivative of the isolated circulatory moment about the common reference
point. Percentages are `(OpenSwing − AVL) / AVL`; a negative percentage
therefore means a smaller magnitude when the signs agree. Both signs and all
six force/moment components are retained in the linked machine results.
The wing's yaw-moment derivative with yaw rate is positive in these axes;
it must not be interpreted as a stabilizing damping contribution by itself.

| Surface | Moment | Body-rate input | Difference from AVL |
| --- | --- | --- | ---: |
| Wing | Roll | Roll | −0.974% |
| Wing | Yaw | Roll | −1.872% |
| Wing | Roll | Yaw | −0.840% |
| Wing | Yaw | Yaw | −8.423% |
| Fin | Roll | Roll | −5.213% |
| Fin | Yaw | Roll | −4.282% |
| Fin | Roll | Yaw | −3.724% |
| Fin | Yaw | Yaw | −4.773% |

Halving the yaw-rate perturbation changes each six-component derivative
vector by less than **2.84e−14 relative to its largest component**. The yaw
moment itself changes by less than **5.6e−12%**. Thus finite-difference step
size does not explain these yaw comparisons. The roll perturbation was not
repeated at half step.

Some much smaller cross-axis force components have large relative errors:
the wing's vertical-force derivative with roll rate differs by **86.0%**, and
the fin's axial-force derivative with yaw rate by **97.1%**. Their absolute
derivatives, respectively 0.03795 versus 0.07059 and −0.01693 versus −0.03337
in the diagnostic's unit-speed/density convention, are retained alongside
the dominant components. This is not a claim that every output agrees within
8.43%.

The direct comparison also retains native bound-vector forces and OpenSwing
beam-length forces, with their own documented application points. These and
the receiver/section-normal conventions must be separated before calling a
remaining difference an OpenSwing physics error. The native-coordinate replay
already rules out a vortex arithmetic or body-rate sign discrepancy for its
matched operator. It does not establish exact ASWING/native-AVL equivalence.

## Evidence, limits and next work

The [complete result](../../artifacts/daedalus-wing-paper-20261113/avl-summary/result.json)
includes every baseline and perturbed wrench, geometry difference, native
reconstruction error, half-step comparison and resource summary. Each case
directory retains its actual `.avl`, commands, native output, exported fields,
OpenSwing output, immutable runner, input checksums and process receipts.

The [bounded driver](../../scripts/check_daedalus_wing_paper.py) supports, for
example:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/check_daedalus_wing_paper.py avl \
  --tag fresh-wing-roll-plus --beam 1 --axis x --rate 0.0001
```

Run one fresh tag at a time. All jobs retained the 512 MiB address-space,
15 CPU-second and 25 wall-second limits, with one BLAS thread. The numerical
jobs used at most **3.970 CPU seconds, 13.621 wall seconds and 91.516 MiB
peak resident memory**. All native children and diagnostic parents were reaped.
The separate summary job also completed within those limits.

Two initial attempts are retained as failures: `avl-wing-base` failed the
report-label parser; `avl-wing-base-v2` incorrectly required the zero-core
field to equal native AVL's finite-core field. The corrected native replay
uses the documented core, preserves the zero-core discrepancy, and keeps the
original numerical acceptance thresholds. `avl-wing-base-v3` is the accepted
baseline. Neither failed attempt was counted as a comparison pass.

The [subsequent convention replay](daedalus-avl-conventions-20261113.md)
separates the remaining lateral derivative difference on these actual loaded
surfaces and projects the isolated steady rate-load difference into the full
dynamic operator. Receiver locations dominate the differences; the limited
rate-load correction changes dip-frequency yaw by only −0.187%. Neither a rigid
surface rate derivative nor the older paper supplies the circulation-rate,
apparent-inertia and structural phase needed to validate the Bode dip. Current
Bode mismatch, unknown original settings and all ISAE completion fractions
remain unchanged.
