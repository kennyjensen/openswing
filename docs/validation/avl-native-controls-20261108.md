# Native AVL reference: finite-chord loads and winglet junctions

2026-11-08 UTC. Drela and Youngren's complete AVL 3.52 now builds and runs
locally. **29 small serial cases complete**, providing original native force,
moment, strip and element output. This removes the need to treat our earlier
custom all-edge force calculation as an AVL equivalent.

The main finding is a distinction between integrated and local behavior.
Doubling the simple winglet control's span resolution changes total lift by
**0.0966%**, but its maximum strip normal-force coefficient increases by
**32.81%**. Native finite-chord results therefore do not, by themselves,
validate a local junction field or justify relaxing OpenSwing's Mach guard.

Production aerodynamics and the registered ISAE scope are unchanged. SA-11
remains **163/4,592 at 5%**. These are independent AVL controls, not ASWING
reference passes or a replacement for the authoritative ISAE reports.

![Native AVL control results](../../artifacts/isae/avl-native-controls-20261108-review/native-controls-vibelattice.png)

## Native build and force conventions

The [official AVL source](https://web.mit.edu/drela/Public/web/avl/) supplies
the complete Fortran/C program, plotting library and bundled numerical routines.
The retained `avl3.52.tgz` SHA-256 is
`0b588ecea9222f5b625d0af0c87ae31daf3cdba1532cf0bbb36f93d6e854849b`.
The resulting binary SHA-256 is
`4a1f68e17e53265d4717db1773bb0578e793eaec8c66dee6f96587a4f60cc5b5`.

Only two source constants change: the matching vortex capacities in
`ADIMEN.INC` and `avl_heap_inc.f90`, from 5,000 to 1,024. Numerical algorithms
are unchanged. The working source contains 395 pinned files. The build uses
49 compilation units in serial batches, `-O1`, legacy argument compatibility,
bounds checking, and upstream-prescribed real precision. Bundled LAPACK/BLAS
and EISPACK retain their explicit precision. The real X11 library is linked;
no custom plotting or aerodynamic stubs are substituted. PDF plotting uses
the upstream optional-library stubs. X11 headers were extracted locally,
without a system package installation.

Cumulative compiler subprocess time is 138.42 seconds, excluding verification
and orchestration. The binary starts and exits successfully. These controls
use at most 768 vortices, one thread and a 768 MiB address-space ceiling.
This establishes the exercised console aerodynamic workflow, not every AVL
feature or plot mode.

Direct source inspection establishes three relevant differences:

- [`aero.f`, SFFORC](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/aero.f)
  evaluates bound-vortex forces with induced velocity. Its optional forces on
  the surface portions of trailing legs use freestream plus rotation only;
  the comment explicitly excludes their induced contribution.
- [`avl.f`](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/avl.f)
  initializes `LTRFORCE=.FALSE.`. The one option-on control leaves the swept
  fixture's total force and pitching moment unchanged but changes its geometric
  yaw coefficient by **+0.00142781219**. Force convention matters for moments
  even when lift and drag agree.
- [`aic.f`](../../reference/avl-native-20261108/source/AVL3.52rel09032025/src/aic.f)
  retains a same-component core of `0.0001 × strip width`. The native fixed-x
  wake also differs from the wind-aligned construction in Drela's ASWING
  steady description, §4.2, equations 155–157 and the following discussion.

Consequently, the [previous all-edge diagnostic](isae-sa11-force-quadrature-20261107.md)
is not a reproduction of native AVL. Nor can AVL's optional force convention
simply be transferred into ASWING. The [continuous attached-force identity](continuous-attached-drag-20261108.md)
remains a separate mathematical control with different geometry and loading.

## Fixtures and numerical results

All fixtures have 10 m projected horizontal span, 1 m streamwise chord, flat
sections, zero Mach and sideslip, no rotation, and reference point `(0.25,0,0)`.
The swept fixture is a straight parallelogram with `x_LE = y tan(30°)`.
It is not a symmetric V-shaped planform or the earlier local-chord oblique wing.
The winglet fixture has a continuous horizontal wing and 1 m upward vertical
tips, represented as one surface/component. It has no SA-11 offsets or fork.
The winglet strips each number one quarter of the horizontal-wing count.

Cosine spacing is used in chord and within each span segment. The primary
sequence varies chord rows 1, 2, 4, 8 at 16 horizontal strips, then uses
8 rows/32 strips. Separate 8/64 and 16/32 refinements check sensitivity in each
direction. Supplementary cases check zero incidence, reversed sweep, ±1° and
negative winglet incidence, and the native trailing-leg force switch.

Representative 5° results at **8 chord rows / 32 horizontal strips**:

| Geometry | CL | Native near-field CDind | Trefftz CDff | Pitching Cm | Near-field/Trefftz difference |
|---|---:|---:|---:|---:|---:|
| Rectangle | 0.4211694 | 0.005877411 | 0.005898903 | +0.00259978 | −0.3643% |
| Swept parallelogram | 0.3755151 | 0.004736451 | 0.004798834 | −0.03279861 | −1.3000% |
| Joined vertical winglets | 0.4511058 | 0.005591607 | 0.005452252 | +0.00138333 | +2.5559% |

`CDind` and `CDff` above are AVL's distinct output labels. They are not assumed
to match an identically named ASWING quantity. The native user guide explicitly
prefers Trefftz drag for performance estimation.

Changes from the 8/32 fixture to **8/64**:

| Geometry | CL change | Near-field CD change | Trefftz CD change | Cm change | Peak strip normal-force change |
|---|---:|---:|---:|---:|---:|
| Rectangle | +0.00329% | −0.01536% | −0.00397% | +0.06290% | +0.02083% |
| Swept | −0.01391% | +0.23903% | −0.00194% | +1.48749% | +0.00938% |
| Winglets | +0.09658% | +0.08866% | −0.11327% | +0.32799% | **+32.81234%** |

The finer winglet peak is on the first horizontal strip beside the junction,
at `y≈−4.99849 m`, with normal-force coefficient **0.64410** and local pitching
coefficient **0.027202**. At 8/32 the maximum normal coefficient is 0.48497;
that run's first horizontal strip has 0.37084. These receivers move closer to
the corner under refinement. This is not a fixed-position velocity comparison,
and the normal-force coefficient is not an airfoil stall coefficient.

Increasing chord resolution instead, to 16/32, changes winglet lift by
−0.0540%, near-field drag by −0.3520% and Cm by −1.1133%; its peak normal
coefficient remains 0.48497. Combined refinement beyond this sequence remains
necessary before claiming local convergence. Swept-wing pitching moment also
retains measurable span sensitivity.

## Angle checks, evidence and next action

The one-row rectangle's near/far drag ratio agrees with `cos(5°)` to about
`5.7e-9`. This is a diagnostic of the fixed-x wake/force projection in this
control, not a correction applied to any solver. At multiple chord rows a
discretization difference remains. At 1°, the 8/32 rectangular near/far
difference is +0.00103%, while the swept case still differs by −0.9380%.
The latter cannot be explained by the cosine factor alone.

The nonplanar fixture has both odd and even terms in its geometric-axis loads.
The source equations imply terms proportional to `sin(alpha) cos(alpha)` and
`sin(alpha)^2`. The ±5° results predict the independently run ±1° body loads
and moments within **4.17e-17** absolute coefficient error. Trefftz drag scales
as `sin(alpha)^2` for these fixed linear fixtures. This checks native output
interpretation and angle dependence, not physical accuracy.

All 29 native processes exit successfully, taking **0.12–0.92 seconds each**,
8.32 seconds cumulatively, including native process startup but excluding the
Python harness and review. Zero-incidence loads are zero. Reversed-sweep
symmetry agrees within **2.40e-12**. Reconstructing total force and moment from
the rounded native body-strip export agrees within **3.42e-6**; full-precision
total, strip and element exports are also retained. All 143 production/status/
scope hashes remain unchanged.

The subsequent [matched field comparison](avl-matched-fields-20261108.md)
completes nine one-row rectangle, swept and winglet controls with native
circulation and actual receiver locations exported. Original near-field
lift/drag agree within 0.000000571%; native AVL also reproduces the junction
velocity growth. Actual SA-11 discretization and junction treatment remain
unresolved. Stable total forces alone cannot establish a local-Mach repair. The
[ISAE report's own junction limitation](aswing-authoritative-references.md)
continues to govern interpretation of the native ASWING target.

- [Build driver](../../scripts/build-avl-reference.py) and [build verification](../../artifacts/isae/avl-native-build-20261108/verification.json)
- [Serial control driver](../../scripts/verify-avl-native-controls.py)
- [Independent output audit](../../scripts/analyze-avl-native-controls.py) and [results](../../artifacts/isae/avl-native-controls-20261108-review/analysis.json)
- [Standalone SVG](../../artifacts/isae/avl-native-controls-20261108-review/native-controls-vibelattice.svg)

Inputs, exact command streams, original output, timing and checksums are in
`artifacts/isae/avl-native-controls-20261108/` and its `-refinement/` companion.
Historical build/source paths still resolve through the `.reference` compatibility
symlink after the user's requested move to the visible `reference/` directory.
