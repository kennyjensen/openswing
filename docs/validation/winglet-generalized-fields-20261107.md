# Connected generalized lifting-line field audit

2026-11-07. Nine prescribed-circulation field evaluations compare the existing
unswept winglet control with the connected effective lifting-line geometry in
the retained MachUpX reference. There are **no new circulation solves** and no
ASWING-reference passes. Production modules, inputs, defaults and tracking
fractions remain unchanged.

## What was executed

The reference is [MachUpX](https://github.com/usuaero/MachUpX), pinned at
`9935476395b205e74612b6dc53d931eb1cad8d5e`, with its original MIT license.
All seven retained source-file hashes were verified. The driver compiles and
executes these intact method AST bodies from those files:

- `Airplane._calculate_geometry`
- `Airplane._sort_segments_into_wings`
- `Airplane._sort_segments_left_to_right`
- `WingSegment.is_continuation`

The rest of MachUpX is not installed or executed. Explicit section fixtures
supply the already-saved physical nodes, arithmetic force samples, chord and
section frames. Main left/right halves and their attached winglets form the
segment tree. The unmodified grouping methods recognize one connected lifting
line. A separate diagnostic deliberately overrides grouping into left winglet,
main wing and right winglet while keeping all physical coordinates fixed.

The method uses a different effective source geometry for each receiver,
locally straightening the connected lifting line with Gaussian blending and
placing finite near-wake segments perpendicular to its tangent. Its documented
defaults are retained: joint length **0.15 chord**, blending distance **1.0**.
The fixture main-half semispan is 0.5 m and each winglet semispan 0.2 m; these
enter the dimensional blending parameter. No parameter is selected by matching
ASWING output. [Official method documentation](https://machupx.readthedocs.io/en/latest/developer_notes.html)
and [input documentation](https://machupx.readthedocs.io/en/latest/creating_input_files.html)
describe the formulation and settings.

Independent stable finite-segment and ray kernels integrate the resulting
polylines at each receiver. A separate transcription of the retained
`scene.py` formulas gives the same tensor within **4.98e-14**. Its ray-denominator
cutoff never activates: the smallest denominator is 6.25e-6 m², compared with
the source threshold 1e-13. The reduction observed below therefore does not
come from that cutoff. The only omitted bound contribution is the explicitly
identified own segment, matching the source convention.

## Fixed-circulation comparison

For each grid all three variants use **identical Gamma, physical geometry and
receiver locations** from the earlier
[unswept control](unswept-winglet-junction-20261107.md). Main-wing interval
counts are 50, 100 and 200, with N/5 intervals on each winglet. Unit freestream
speed is retained; no PG, core or stall treatment is introduced.

| Main-wing intervals | Original horseshoes: peak speed / freestream | Generalized, connected | Generalized, separate groups |
|---:|---:|---:|---:|
| 50 | 1.424025 | 1.109219 | 1.367204 |
| 100 | 1.849900 | 1.113948 | 1.724012 |
| 200 | 2.699538 | 1.116842 | 2.443313 |

Turning the corrections off reproduces the saved original force-point field.
Connecting the surfaces before constructing the effective geometry markedly
changes the refinement behavior. Applying the generalized construction to
separate groups leaves most of the growth. This supports investigating the
complete connected-surface construction, rather than treating it as an
interchangeable vortex-core adjustment.

These are field comparisons, not converged generalized lifting-line states.
For example, the connected N200 state has a maximum circulation defect of
**0.02906 m²/s** under the in-plane section closure
`Gamma = 0.5 * chord * |V_perp| * (2*pi*alpha_eff)`.
The original ASWING-style tangency solution also does not satisfy that distinct
closure. The driver retains diagnostic Kutta–Joukowski loads and closure
defects; those loads must not be presented as predictions from a solved
MachUpX model or as reference validation.

## Adjacent near-wake joints are not identical

The connected construction preserves coincident effective **bound** endpoints
exactly in this fixture. It does not give the adjacent horseshoes exactly the
same **near-wake joint** coordinates at the sharp bend. The maximum joint gap
is 0.522, 0.548 and **0.560 mm** on the three grids. With separate groups it is
3.362 mm on each grid. These are computed geometric differences, not a core
radius or a distance-merging threshold.

At N200 the largest connected gap belongs to a receiver at material station
−0.3275 m viewing the left root. Its common effective bound endpoint is the
original root, but the adjacent joint positions differ. The source computes
joint directions using separate endpoint gradients and source-section axial
vectors. The gap is retained in the field calculation; no joint snapping or
extra connector is silently added. This observation is not a claim that the
entire MachUpX method is invalid, but it matters when comparing exact wake
cancellation and when considering adoption into another force formulation.

![Field refinement and receiver-specific source geometry](../../artifacts/isae/winglet-generalized-fields-20261107/generalized-field-comparison.png)

The lower panels illustrate that the same physical corner has different
effective shapes when viewed from a main-wing receiver and a winglet receiver.
Green lines are effective bounds; orange segments are the finite near-wake
connections. This construction is not a single globally moved aircraft geometry.

## Consequence for the ASWING implementation

The generalized method supplies an explicit alternative to the singular
sharp-corner field. The prescribed-field result is consistent with the
[finite-chord comparison](winglet-finite-chord-20261107.md) in showing that the
local representation of vorticity matters. It does not recover native ASWING's
implementation or justify substituting this geometry into the existing solver.

The subsequent [nonlinear section-equation study](winglet-generalized-solve-20261107.md)
solves all nine variants and independently checks the source residual and
Jacobian. The connected treatment retains stable velocities and loads under
refinement, but its lift and drag differ from the finite-chord control.
A complete ASWING-compatible change would
also require evidence for the original force law, wake treatment and derivatives;
stable prescribed velocities alone do not supply that evidence.

## Reproduction and checks

The numerical driver requires a fresh directory and uses foreground serial
jobs with one BLAS thread. Its dependency pins include the saved unswept
results and the earlier independent finite-segment reference.

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/verify-winglet-generalized-fields.py --output artifacts/isae/winglet-generalized-fields-new
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 timeout 60s prlimit --as=805306368 .venv/bin/python scripts/analyze-winglet-generalized-fields.py --study artifacts/isae/winglet-generalized-fields-new
```

The analysis verifies artifact pins, all nine requested variants, identical
prescribed circulation/physical geometry, force reconstruction, field-component
sums, joint-gap locations and inactive source cutoffs. The Gaussian geometry
equation is independently reconstructed within 1.12e-16 m. It does not repeat
field evaluations or execute a circulation solve. All 141 production module
hashes and the ISAE status/scope hashes remain unchanged.

- [Plan](../../artifacts/isae/winglet-generalized-fields-20261107/plan.json)
- [Field results and grouping](../../artifacts/isae/winglet-generalized-fields-20261107/results.json)
- [Independent audit](../../artifacts/isae/winglet-generalized-fields-20261107/analysis.json)
- [Plot as SVG](../../artifacts/isae/winglet-generalized-fields-20261107/generalized-field-comparison.svg)
