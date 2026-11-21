# Matched native AVL and OpenSwing fields

2026-11-08 UTC. Nine matched one-chord-row controls now compare OpenSwing
directly with native AVL 3.52: a rectangular wing, a straight swept wing,
and a continuous wing with two vertical winglets, each at three span meshes.
Original predictions agree to **0.000000571% in near-field lift/drag** and
**0.000001142% in Trefftz drag**. The remaining uniform discrepancy is
explained by native AVL's rounded `1/(4*pi)` constant.

The sharp winglet junction still develops increasing local velocity in
**both** implementations. This supports the basic horseshoe kernel and force
arithmetic at matched locations. It does not validate SA-11, identify its
original discrete setup, or establish a junction repair. Production equations,
defaults, safeguards, reference inputs and registered fractions are unchanged;
SA-11 remains **163/4,592 at 5%**.

![Original matched winglet circulation and local field](../../artifacts/isae/avl-matched-fields-review-20261108/matched-winglet-fields.png)

## Matched geometry and evaluation points

The fixtures retain the [native control study](avl-native-controls-20261108.md)
geometry: 10 m horizontal span, 1 m streamwise chord, and 1 m vertical winglets.
The swept fixture is a straight oblique parallelogram at 30 degrees, not a
mirrored V-shaped wing. Each uses one chord row and 16, 32 or 64 horizontal
strips; each winglet has one quarter as many strips. Reference area/chord/span
are 10/1/10 and the moment reference is `(0.25,0,0)`.

All cases use alpha 5 degrees, Mach zero, unit speed, no rotation, no viscosity,
no stall and a body-x wake. OpenSwing uses frozen influences to match that
native wake. For the swept fixture, the ASWING chord normal to the beam is
`cos(30 degrees)`: its streamwise chord, control offset and strip area then
match native AVL's 1 m streamwise chord. This is a geometry conversion,
not a fitted aerodynamic parameter.

Native bound endpoints and actual bound/control receiver coordinates are
exported at full precision. Explicit diagnostic meshes reproduce those
coordinates and normals within **2e-12 m / absolute normal-component error**.
The production-generated Glauert receiver on those same nodes differs from
the native receiver by at most **2.21e-11 m**. The diagnostic adjusts only that
tiny coordinate discrepancy; it does not use arithmetic-midpoint sampling or
change the production mesh recipe.

Native `FE` prints `(RV1+RV2)/2`, but `SFFORC` uses the separately stored
**RV** location. The actual force receiver follows Glauert sampling in these
fixtures. Treating the printed element midpoint as its force receiver would
compare different points. Native velocity **VV**, circulation **GAM**, control
normal **ENC**, and true coordinates are retained in each `native-fields.npz`.

## Native instrumentation and numerical agreement

Only extra `WRITE` statements were added to a copied `MRFELE` routine. All
native numerical object files and the original executable are unchanged. The
three overlapping 16-strip cases reproduce the earlier native total, strip
and body-strip files **byte for byte**. Exported circulation, bound velocity
and segment vectors reconstruct native forces and moments within the declared
1e-12 coefficient gate.

The uniform discrepancy follows directly from
[`aic.f`, VORVELC](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/aic.f):
`DATA PI4INV / 0.079577472 /`.
Relative to mathematical `1/(4*pi)`, the kernel multiplier is
**k = 1.0000000057057898**. In these fixed linear controls, native circulation
is OpenSwing circulation divided by k; the kernel and circulation factors
cancel in induced velocity. Near-field force/moment coefficients differ by k,
while the independently evaluated Trefftz drag differs by k squared.

This is a source-derived identity, not a fitted correction. Accounting for it
in the audit leaves maximum relative circulation error **1.42e-13**,
bound-velocity error **1.53e-12 times freestream**, and absolute coefficient
error **8.61e-15**. Neither code's predictions were rescaled or changed.
AVL retains its tiny same-component fourth-power core; OpenSwing retains
zero core on the shared physical surface. Their remaining effect is included
in those measured errors.

## Native junction velocity also grows

The maximum section-normal speed occurs just inside the main wing, approaching
the left winglet junction. Native values are:

| Main-wing strips | Distance to junction, m | Normal speed / freestream | Bound-induced streamwise velocity / freestream | Native CL | Native near-field CD |
|---:|---:|---:|---:|---:|---:|
| 16 | 0.0240764 | 1.42583 | 0.428418 | 0.45370714 | 0.005825072 |
| 32 | 0.00602272 | 2.82110 | 1.824293 | 0.45534854 | 0.005901563 |
| 64 | 0.00150591 | 8.50229 | 7.505896 | 0.45663368 | 0.005984725 |

The growing contribution in this unswept, coincident-root control comes from
the **bound vortex**, not the trailing rays: the latter have zero streamwise
velocity here. The full decomposition is retained. Receiver positions move
closer to the corner on finer grids; this is a failure of sampled peak
convergence, not a fixed-position convergence test.

The swept control shows a different mechanism: its straight bound line has
negligible self-induced field, while wake-induced velocity at the tip receiver
increases with refinement. Both mechanisms are reproduced by native AVL. The
actual SA-11 offsets and forked roots remain distinct from these clean fixtures.

At 64 main-wing strips, native coefficients are:

| Geometry | CL | Near-field CD | Trefftz CD | Cm |
|---|---:|---:|---:|---:|
| Rectangle | 0.4192777773 | 0.00580626945 | 0.00582844843 | effectively zero |
| Swept | 0.3741946501 | 0.00462183546 | 0.00474271235 | -0.0326697738 |
| Winglets | 0.4566336780 | 0.00598472465 | 0.00546863505 | -0.0000941532 |

Native one-row near-field and Trefftz drag also differ. This supports checking
sampling and discretization rather than overriding local forces to impose
integrated agreement. It does not determine the cause of SA-2's archived-ASWING
discrepancy.

## Verification and next work

All nine native and nine production solves complete serially with one BLAS
thread and a 768 MiB address-space ceiling. Native subprocesses take
0.16–0.31 seconds each, **1.87 seconds total**; production solve calls take
0.04–0.10 seconds each, **0.52 seconds total**. These timings exclude Python
startup, build and provenance checks. They concern tiny linear controls,
not full nonlinear SA-11 or browser runtime.

The audit passes 417 geometry, field, output and provenance checks, verifies
395 native source hashes, and preserves all 143 production/status/scope pins.
Two earlier harness errors are retained: unintended ASW automatic reflection
from a nonnegative parameter domain, and a supplemental mesh-count selector
error. Both stopped before a production solve. Corrected runs use fresh
directories; previous evidence was not overwritten.

Next, check circulation-mode mapping and force sampling at the actual SA-11
connected/offset/forked geometry. These controls narrow the search away from
an elementary kernel or vector-force bug. They do not authorize a core change,
an AVL replacement, a Mach-check bypass, or an additional ISAE pass. The
[authoritative ISAE reports](aswing-authoritative-references.md) remain the
source for the target case and original ASWING predictions.

- [Serial comparison driver](../../scripts/verify-avl-matched-fields.py)
- [Read-only audit](../../scripts/analyze-avl-matched-fields.py) and [complete results](../../artifacts/isae/avl-matched-fields-review-20261108/report.json)
- [Unswept comparison plan](../../artifacts/isae/avl-matched-fields-r1-20261108/plan.json) and [swept supplement](../../artifacts/isae/avl-matched-swept-r1-20261108/plan.json)
- [Standalone SVG](../../artifacts/isae/avl-matched-fields-review-20261108/matched-winglet-fields.svg) and [plot provenance](../../artifacts/isae/avl-matched-fields-review-20261108/plot-verification.json)
